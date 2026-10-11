"""Client sincrono per l'API cloud SunPower / TCL (EMEA).

Catena di autenticazione (ricostruita dall'app ufficiale):
  login(email, password)  -> ssoToken (JWT, ~3 giorni)
  POST /v3/auth/refresh_tokens(ssoToken) -> saasToken (~28 min)
  GET /v3/solar/*  firmate con sign = MD5(timestamp + nonce + saasToken)

Il login su multi-eu-prod usa:
  - payload JSON cifrato AES-256-CBC/PKCS7 (IV = "0000000000000000"),
    chiave AES casuale di 32 char cifrata RSA/PKCS1v15 nell'header x-tcl-secret;
  - firma TCL1-HMAC-SHA256 sugli header xtcl-nonce/xtcl-timestamp.

Tutte le chiamate sono bloccanti (urllib): l'integrazione le esegue in executor.
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import hmac
import json
import re
import secrets
import time
import urllib.error
import urllib.request
import uuid

from cryptography.hazmat.primitives.asymmetric import padding as rsa_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.serialization import load_pem_public_key

from .const import (
    ACCOUNT_APP_ID,
    ACCOUNT_APP_KEY,
    ACCOUNT_BASE,
    APP_VERSION,
    DATA_APP_ID,
    DATA_BASE,
    TENANT,
    THOME_VERSION,
    USER_AGENT,
)

_IV = b"0000000000000000"
_KEY_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"


class SunPowerAuthError(Exception):
    """Credenziali rifiutate o login fallito."""


class SunPowerApiError(Exception):
    """Errore generico dell'API."""


def _b64_sha256(data: bytes) -> str:
    return base64.b64encode(hashlib.sha256(data).digest()).decode()


def _pkcs7(data: bytes) -> bytes:
    pad = 16 - len(data) % 16
    return data + bytes([pad]) * pad


def _unpad(data: bytes) -> bytes:
    return data[: -data[-1]]


def _jwt_exp(token: str) -> float:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
        return float(data.get("exp") or data.get("expiredDate") or 0)
    except Exception:  # noqa: BLE001
        return 0.0


class SunPowerTclClient:
    """Client cloud SunPower/TCL."""

    def __init__(self, email: str, password: str, country: str = "IT") -> None:
        self._email = email
        self._password = password
        self._country = country
        self._aes_key = b""
        self._sso: str | None = None
        self._sso_exp = 0.0
        self._saas: str | None = None
        self._saas_exp = 0.0

    # ---------- HTTP di base ----------
    @staticmethod
    def _read(resp) -> str:
        raw = resp.read()
        if resp.headers.get("content-encoding") == "gzip":
            raw = gzip.decompress(raw)
        return raw.decode("utf-8", "replace")

    def _request(self, url: str, *, method: str, headers: dict, data: bytes | None = None) -> str:
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                return self._read(resp)
        except urllib.error.HTTPError as err:
            raise SunPowerApiError(f"HTTP {err.code} su {url}") from err
        except urllib.error.URLError as err:
            raise SunPowerApiError(f"rete: {err}") from err

    # ---------- crypto account ----------
    def _aes_encrypt(self, text: str) -> bytes:
        enc = Cipher(algorithms.AES(self._aes_key), modes.CBC(_IV)).encryptor()
        return enc.update(_pkcs7(text.encode())) + enc.finalize()

    def _aes_decrypt(self, blob: bytes) -> bytes:
        dec = Cipher(algorithms.AES(self._aes_key), modes.CBC(_IV)).decryptor()
        return _unpad(dec.update(blob) + dec.finalize())

    @staticmethod
    def _tcl_sign(method: str, path: str, query: str, nonce: str, ts: str, body: bytes) -> str:
        canon_headers = f"xtcl-nonce:{nonce};xtcl-timestamp:{ts};"
        canon_request = "\n".join([method, path, query, canon_headers, _b64_sha256(body)])
        string_to_sign = f"TCL1-HMAC-SHA256\n{ts}\n" + _b64_sha256(canon_request.encode())
        digest = hmac.new(ACCOUNT_APP_KEY.encode(), string_to_sign.encode(), hashlib.sha256).digest()
        return base64.b64encode(digest).decode()

    def _account_headers(self, method: str, path: str, query: str, body: bytes, extra: dict | None = None) -> dict:
        nonce = uuid.uuid4().hex
        ts = str(int(time.time()))
        sig = self._tcl_sign(method, path, query, nonce, ts, body)
        headers = {
            "user-agent": USER_AGENT,
            "xtcl-nonce": nonce,
            "xtcl-timestamp": ts,
            "deviceid": "android_flutter",
            "x-tenant-id": TENANT,
            "env": "android",
            "version": THOME_VERSION,
            "xtcl-app": ACCOUNT_APP_ID,
            "requestid": uuid.uuid4().hex,
            "xtcl-authorization": (
                f"TCL1-HMAC-SHA256 Credential={ACCOUNT_APP_ID},"
                "SignedHeaders=xtcl-nonce;xtcl-timestamp;,"
                f"Signature={sig}"
            ),
        }
        if extra:
            headers.update(extra)
        return headers

    def _fetch_public_key(self):
        path = "/multi/publicKey"
        headers = self._account_headers("GET", path, "type=RSA", b"")
        raw = self._request(ACCOUNT_BASE + path + "?type=RSA", method="GET", headers=headers)
        pem = json.loads(raw)["data"]["publicKey"]
        b64 = re.sub(r"-----(BEGIN|END) PUBLIC KEY-----", "", pem)
        b64 = re.sub(r"\s+", "", b64)
        pem = "-----BEGIN PUBLIC KEY-----\n" + b64 + "\n-----END PUBLIC KEY-----\n"
        return load_pem_public_key(pem.encode())

    # ---------- login + token ----------
    def login(self) -> str:
        self._aes_key = "".join(secrets.choice(_KEY_ALPHABET) for _ in range(32)).encode()
        public_key = self._fetch_public_key()
        x_secret = base64.b64encode(public_key.encrypt(self._aes_key, rsa_padding.PKCS1v15())).decode()
        payload = json.dumps(
            {
                "countryCode": self._country,
                "loginName": self._email,
                "password": hashlib.md5(self._password.encode()).hexdigest(),  # noqa: S324
            },
            separators=(",", ":"),
        )
        enc_body = base64.b64encode(self._aes_encrypt(payload)).decode()
        path = "/identify/login"
        headers = self._account_headers(
            "POST",
            path,
            "",
            enc_body.encode(),
            extra={
                "content-type": "application/encrypted-json;charset=UTF-8",
                "x-tcl-secret": x_secret,
            },
        )
        raw = self._request(ACCOUNT_BASE + path, method="POST", headers=headers, data=enc_body.encode())
        try:
            data = json.loads(self._aes_decrypt(base64.b64decode(raw)).decode())
        except Exception as err:  # noqa: BLE001
            raise SunPowerApiError("risposta di login non decifrabile") from err
        token = (data.get("data") or {}).get("token")
        if not token:
            raise SunPowerAuthError(f"login rifiutato: {json.dumps(data)[:200]}")
        self._sso = token
        self._sso_exp = _jwt_exp(token) or (time.time() + 3 * 86400)
        return token

    def _ensure_sso(self) -> str:
        if self._sso and time.time() < self._sso_exp - 3600:
            return self._sso
        return self.login()

    def _ensure_saas(self) -> str:
        if self._saas and time.time() < self._saas_exp - 120:
            return self._saas
        sso = self._ensure_sso()
        token = self._do_refresh(sso)
        if token is None:
            # ssoToken rifiutato: nuovo login e un solo retry
            self._sso = None
            sso = self._ensure_sso()
            token = self._do_refresh(sso)
            if token is None:
                raise SunPowerApiError("refresh_tokens fallito dopo nuovo login")
        return token

    def _do_refresh(self, sso: str) -> str | None:
        body = json.dumps(
            {"userId": str(_jwt_field(sso, "i") or ""), "ssoToken": sso, "appId": DATA_APP_ID, "mac": "default"}
        ).encode()
        raw = self._request(
            DATA_BASE + "/v3/auth/refresh_tokens",
            method="POST",
            headers={"content-type": "application/json", "user-agent": USER_AGENT},
            data=body,
        )
        data = json.loads(raw)
        if data.get("code") != 0:
            return None
        token = data["data"]["saasToken"]
        self._saas = token
        self._saas_exp = _jwt_exp(token) or (time.time() + 1500)
        return token

    # ---------- chiamate dati ----------
    def _data_get(self, path: str) -> dict | list:
        token = self._ensure_saas()
        ts = str(int(time.time() * 1000))
        nonce = uuid.uuid4().hex
        sign = hashlib.md5((ts + nonce + token).encode()).hexdigest()  # noqa: S324
        headers = {
            "appid": DATA_APP_ID,
            "accesstoken": token,
            "timestamp": ts,
            "nonce": nonce,
            "sign": sign,
            "platform": "android",
            "countrycode": self._country,
            "appversion": APP_VERSION,
            "thomeversion": THOME_VERSION,
            "user-agent": USER_AGENT,
            "accept-language": "en-US",
        }
        raw = self._request(DATA_BASE + path, method="GET", headers=headers)
        data = json.loads(raw)
        if data.get("code") != 0:
            raise SunPowerApiError(f"{path}: code={data.get('code')} {data.get('message')}")
        return data["data"]

    def get_stations(self) -> list[dict]:
        return self._data_get("/v3/solar/station-list") or []

    def get_run_status(self, device_id: str) -> dict:
        return self._data_get(f"/v3/solar/station-run-status?device_id={device_id}") or {}

    def get_cumulative(self, device_id: str) -> dict:
        return self._data_get(f"/v3/solar/station-cumulative-info?device_id={device_id}") or {}

    # ---------- comodità per config flow / coordinator ----------
    def validate(self) -> list[dict]:
        """Verifica le credenziali e ritorna la lista impianti."""
        self.login()
        return self.get_stations()

    def fetch_all(self) -> dict[str, dict]:
        """Ritorna {device_id: {campi run-status + cumulative}} per ogni impianto."""
        result: dict[str, dict] = {}
        for station in self.get_stations():
            dev = station.get("deviceId")
            if not dev:
                continue
            merged = dict(station)
            try:
                merged.update(self.get_run_status(dev))
            except SunPowerApiError:
                pass
            try:
                merged.update(self.get_cumulative(dev))
            except SunPowerApiError:
                pass
            result[dev] = merged
        return result


def _jwt_field(token: str, field: str):
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload)).get(field)
    except Exception:  # noqa: BLE001
        return None
