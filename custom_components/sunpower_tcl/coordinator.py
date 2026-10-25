"""DataUpdateCoordinator per SunPower (TCL EMEA)."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SunPowerApiError, SunPowerAuthError, SunPowerTclClient
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SunPowerCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Coordina il polling cloud e mantiene i dati per impianto."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: SunPowerTclClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.entry = entry
        self.client = client

    async def _async_update_data(self) -> dict[str, dict]:
        try:
            return await self.hass.async_add_executor_job(self.client.fetch_all)
        except SunPowerAuthError as err:
            # credenziali rifiutate: HA sospende il polling e propone la riautenticazione
            raise ConfigEntryAuthFailed(str(err)) from err
        except SunPowerApiError as err:
            raise UpdateFailed(str(err)) from err
