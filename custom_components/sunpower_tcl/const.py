"""Costanti per l'integrazione SunPower (TCL EMEA)."""
from __future__ import annotations

DOMAIN = "sunpower_tcl"

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_COUNTRY = "country"

DEFAULT_COUNTRY = "IT"
DEFAULT_SCAN_INTERVAL = 30  # secondi

# Endpoint TCL (regione EU). Gli impianti vengono scoperti dopo il login.
ACCOUNT_BASE = "https://multi-eu-prod.tcljd.com"
DATA_BASE = "https://prod-eu.aws.tcljd.com"

# Credenziali dell'app (estratte dall'APK SunPower EMEA). Non sono segreti utente:
# sono le stesse per tutti e identificano l'app verso il backend TCL.
ACCOUNT_APP_ID = "85421745223990830"
ACCOUNT_APP_KEY = "^Lj14^?K09qt4uaWDv^R23A8p2HP7*pV"
TENANT = "sunpower"
DATA_APP_ID = "iKDbEg81u0hdh1AGP5"

USER_AGENT = "Dart/3.12 (dart:io)"
APP_VERSION = "6.2.12"
THOME_VERSION = "1.3.1"
