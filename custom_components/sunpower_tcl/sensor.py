"""Sensori SunPower (TCL EMEA)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, ENERGY_MAX_GAP, GRID_POSITIVE_IS_IMPORT
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


@dataclass(frozen=True, kw_only=True)
class SunPowerEnergyDescription(SensorEntityDescription):
    """Contatore di energia calcolato integrando una potenza (W) nel tempo."""

    power_key: str
    sign: int  # +1 integra la parte positiva della potenza, -1 quella negativa


_GRID_IMPORT_SIGN = 1 if GRID_POSITIVE_IS_IMPORT else -1

# L'API non espone energia di rete/batteria: la ricaviamo dalle potenze istantanee.
# battChargeAndDischargePower: positivo = scarica, negativo = carica.
ENERGY_SENSORS: tuple[SunPowerEnergyDescription, ...] = tuple(
    SunPowerEnergyDescription(
        key=key, name=name, power_key=power_key, sign=sign,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY, state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2)
    for key, name, power_key, sign in (
        ("gridImportEnergy", "Energia prelevata dalla rete", "meterPower", _GRID_IMPORT_SIGN),
        ("gridExportEnergy", "Energia immessa in rete", "meterPower", -_GRID_IMPORT_SIGN),
        ("battChargeEnergy", "Energia caricata in batteria", "battChargeAndDischargePower", -1),
        ("battDischargeEnergy", "Energia scaricata dalla batteria", "battChargeAndDischargePower", 1),
    )
)


def _device_info(coordinator: SunPowerCoordinator, device_id: str) -> dict:
    station = coordinator.data.get(device_id, {})
    return {
        "identifiers": {(DOMAIN, device_id)},
        "name": station.get("stationName") or "SunPower",
        "manufacturer": "SunPower / TCL",
        "model": (station.get("subDeviceInfos") or [{}])[0].get("deviceName", "Solar"),
        "serial_number": (station.get("subDeviceInfos") or [{}])[0].get("sn"),
    }


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: SunPowerCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []
    for device_id in coordinator.data:
        for desc in SENSORS:
            entities.append(SunPowerSensor(coordinator, device_id, desc))
        for energy_desc in ENERGY_SENSORS:
            entities.append(SunPowerEnergySensor(coordinator, device_id, energy_desc))
    async_add_entities(entities)


class SunPowerSensor(CoordinatorEntity[SunPowerCoordinator], SensorEntity):
    """Sensore di un impianto SunPower."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SunPowerCoordinator, device_id: str, desc: SensorEntityDescription) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self.entity_description = desc
        self._attr_unique_id = f"{device_id}_{desc.key}"
        self._attr_device_info = _device_info(coordinator, device_id)

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


class SunPowerEnergySensor(CoordinatorEntity[SunPowerCoordinator], RestoreSensor):
    """Energia (kWh) ottenuta integrando una potenza con il metodo dei trapezi."""

    _attr_has_entity_name = True
    entity_description: SunPowerEnergyDescription

    def __init__(
        self, coordinator: SunPowerCoordinator, device_id: str, desc: SunPowerEnergyDescription
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self.entity_description = desc
        self._attr_unique_id = f"{device_id}_{desc.key}"
        self._attr_device_info = _device_info(coordinator, device_id)
        self._attr_native_value = 0.0
        self._last_power: float | None = None
        self._last_time: datetime | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_sensor_data()) is not None:
            try:
                self._attr_native_value = float(last.native_value)
            except (TypeError, ValueError):
                pass
        self._integrate()

    def _integrate(self) -> None:
        raw = self.coordinator.data.get(self._device_id, {}).get(self.entity_description.power_key)
        now = dt_util.utcnow()
        try:
            power = max(0.0, self.entity_description.sign * float(raw))
        except (TypeError, ValueError):
            # dato mancante: ricomincia dal prossimo campione valido
            self._last_power = self._last_time = None
            return
        if self._last_power is not None and self._last_time is not None:
            elapsed = (now - self._last_time).total_seconds()
            # oltre ENERGY_MAX_GAP (cloud irraggiungibile, riavvio) non stimiamo nulla
            if 0 < elapsed <= ENERGY_MAX_GAP:
                kwh = (self._last_power + power) / 2 * elapsed / 3_600_000
                self._attr_native_value = round(self._attr_native_value + kwh, 6)
        self._last_power = power
        self._last_time = now

    @callback
    def _handle_coordinator_update(self) -> None:
        self._integrate()
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        return super().available and self._device_id in self.coordinator.data
