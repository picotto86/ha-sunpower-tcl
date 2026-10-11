"""Binary sensor SunPower (TCL EMEA)."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SunPowerCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: SunPowerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SunPowerOnlineBinarySensor(coordinator, device_id) for device_id in coordinator.data
    )


class SunPowerOnlineBinarySensor(CoordinatorEntity[SunPowerCoordinator], BinarySensorEntity):
    """Stato online dell'inverter."""

    _attr_has_entity_name = True
    _attr_name = "Inverter online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: SunPowerCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_deviceOnline"
        station = coordinator.data.get(device_id, {})
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": station.get("stationName") or "SunPower",
            "manufacturer": "SunPower / TCL",
        }

    @property
    def is_on(self) -> bool | None:
        value = self.coordinator.data.get(self._device_id, {}).get("deviceOnline")
        if value is None:
            return None
        return int(value) == 1
