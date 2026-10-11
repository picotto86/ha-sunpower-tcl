"""Sensori SunPower (TCL EMEA)."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SunPowerCoordinator

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="inputPower", name="Potenza FV", native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER, state_class=SensorStateClass.MEASUREMENT),
    SensorEntityDescription(
        key="loadPower", name="Potenza carico", native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER, state_class=SensorStateClass.MEASUREMENT),
    SensorEntityDescription(
        key="meterPower", name="Potenza rete", native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER, state_class=SensorStateClass.MEASUREMENT),
    SensorEntityDescription(
        key="battChargeAndDischargePower", name="Potenza batteria",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER, state_class=SensorStateClass.MEASUREMENT),
    SensorEntityDescription(
        key="battSOC", name="Batteria", native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY, state_class=SensorStateClass.MEASUREMENT),
    SensorEntityDescription(
        key="dailyPowerGeneration", name="Energia oggi",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY, state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2),
    SensorEntityDescription(
        key="monthlyPowerGeneration", name="Energia mese",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY, state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2),
    SensorEntityDescription(
        key="annualPowerGeneration", name="Energia anno",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY, state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2),
    SensorEntityDescription(
        key="dailyEarnings", name="Guadagno oggi",
        device_class=SensorDeviceClass.MONETARY, state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2),
    SensorEntityDescription(
        key="monthlyEarnings", name="Guadagno mese",
        device_class=SensorDeviceClass.MONETARY, state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2),
    SensorEntityDescription(
        key="annualEarnings", name="Guadagno anno",
        device_class=SensorDeviceClass.MONETARY, state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2),
    SensorEntityDescription(
        key="siteStatus", name="Stato impianto", icon="mdi:solar-power",
        entity_category=EntityCategory.DIAGNOSTIC),
)

_EARNINGS = {"dailyEarnings", "monthlyEarnings", "annualEarnings"}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: SunPowerCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SunPowerSensor] = []
    for device_id in coordinator.data:
        for desc in SENSORS:
            entities.append(SunPowerSensor(coordinator, device_id, desc))
    async_add_entities(entities)


class SunPowerSensor(CoordinatorEntity[SunPowerCoordinator], SensorEntity):
    """Sensore di un impianto SunPower."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SunPowerCoordinator, device_id: str, desc: SensorEntityDescription) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self.entity_description = desc
        self._attr_unique_id = f"{device_id}_{desc.key}"
        station = coordinator.data.get(device_id, {})
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": station.get("stationName") or "SunPower",
            "manufacturer": "SunPower / TCL",
            "model": (station.get("subDeviceInfos") or [{}])[0].get("deviceName", "Solar"),
            "serial_number": (station.get("subDeviceInfos") or [{}])[0].get("sn"),
        }

    @property
    def native_unit_of_measurement(self):
        if self.entity_description.key in _EARNINGS:
            return self.coordinator.data.get(self._device_id, {}).get("currencyUnit") or "EUR"
        return self.entity_description.native_unit_of_measurement

    @property
    def native_value(self):
        return self.coordinator.data.get(self._device_id, {}).get(self.entity_description.key)

    @property
    def available(self) -> bool:
        return super().available and self._device_id in self.coordinator.data
