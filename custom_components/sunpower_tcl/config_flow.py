"""Config flow per SunPower (TCL EMEA)."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import SunPowerApiError, SunPowerAuthError, SunPowerTclClient
from .const import (
    CONF_COUNTRY,
    CONF_EMAIL,
    CONF_PASSWORD,
    DEFAULT_COUNTRY,
    DOMAIN,
)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL)
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Optional(CONF_COUNTRY, default=DEFAULT_COUNTRY): str,
    }
)


class SunPowerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Gestisce il config flow dell'integrazione."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            await self.async_set_unique_id(email.lower())
            self._abort_if_unique_id_configured()

            client = SunPowerTclClient(
                email, user_input[CONF_PASSWORD], user_input.get(CONF_COUNTRY, DEFAULT_COUNTRY)
            )
            try:
                stations = await self.hass.async_add_executor_job(client.validate)
            except SunPowerAuthError:
                errors["base"] = "invalid_auth"
            except SunPowerApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                title = "SunPower"
                if stations:
                    title = stations[0].get("stationName") or title
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_COUNTRY: user_input.get(CONF_COUNTRY, DEFAULT_COUNTRY),
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )
