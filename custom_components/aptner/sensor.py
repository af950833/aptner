from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, CONF_CARS, CONF_SCAN_INTERVAL_MIN, DEFAULT_SCAN_INTERVAL_MIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Aptner sensors from a config entry."""
    _LOGGER.debug("Setting up sensors for entry: %s", entry.entry_id)
    
    data = hass.data[DOMAIN][entry.entry_id]
    client = data["client"]
    
    # Get scan interval from options or config
    if entry.options:
        scan_min = entry.options.get(CONF_SCAN_INTERVAL_MIN, DEFAULT_SCAN_INTERVAL_MIN)
    else:
        scan_min = entry.data.get(CONF_SCAN_INTERVAL_MIN, DEFAULT_SCAN_INTERVAL_MIN)
    
    update_interval = timedelta(minutes=int(scan_min))
    
    entities: list[SensorEntity] = []
    
    # 1. 관리비 센서 생성 시도 (실패해도 계속 진행)
    fee_entity = None
    try:
        # Fee coordinator
        async def async_update_fee() -> dict[str, Any]:
            try:
                return await client.get_fee()
            except Exception as err:
                # 404 에러는 관리비 정보가 없는 경우로 간주
                if "404" in str(err) or "관리비 정보가 존재하지 않습니다" in str(err):
                    _LOGGER.debug("No fee information available for this account")
                    return {}  # 빈 데이터 반환
                raise UpdateFailed(f"Error fetching fee data: {err}") from err
        
        fee_coordinator = DataUpdateCoordinator(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_fee_{entry.entry_id}",
            update_method=async_update_fee,
            update_interval=update_interval,
        )
        
        # 첫 번째 업데이트 시도 (실패해도 계속 진행)
        try:
            await fee_coordinator.async_config_entry_first_refresh()
        except Exception as err:
            # 404 에러는 무시 (관리비 정보 없음)
            if "404" in str(err) or "관리비 정보가 존재하지 않습니다" in str(err):
                _LOGGER.info("This account doesn't have fee information. Skipping fee sensor.")
                # 빈 데이터로 초기화
                fee_coordinator.data = {}
            else:
                _LOGGER.warning("Failed to initialize fee coordinator: %s", err)
                # 다른 에러도 무시하고 계속 진행
        
        # 관리비 센서 생성 (데이터가 있으면 생성)
        fee_entity = AptnerFeeAmountSensor(entry, fee_coordinator)
        entities.append(fee_entity)
        _LOGGER.debug("Created fee sensor")
        
    except Exception as err:
        _LOGGER.warning("Failed to setup fee sensor: %s. Continuing with other sensors.", err)
    
    # 2. 방문차량 예약현황 센서 생성
    try:
        # Reserve coordinator
        async def async_update_reserve() -> dict[str, Any]:
            try:
                return await client.get_reserve_status()
            except Exception as err:
                raise UpdateFailed(f"Error fetching reserve data: {err}") from err
        
        reserve_coordinator = DataUpdateCoordinator(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_reserve_{entry.entry_id}",
            update_method=async_update_reserve,
            update_interval=update_interval,
        )
        
        # 첫 번째 업데이트 시도
        try:
            await reserve_coordinator.async_config_entry_first_refresh()
        except Exception as err:
            _LOGGER.error("Failed to initialize reserve coordinator: %s", err)
            # 방문차량 정보가 없을 수도 있지만, 센서는 생성
            reserve_coordinator.data = {}
        
        # 방문차량 예약현황 센서 생성
        reserve_entity = AptnerReserveOverviewSensor(entry, reserve_coordinator)
        entities.append(reserve_entity)
        _LOGGER.debug("Created reserve sensor")
        
    except Exception as err:
        _LOGGER.error("Failed to setup reserve sensor: %s", err)
        raise ConfigEntryNotReady from err
    
    # 센서 추가
    if entities:
        async_add_entities(entities)
        _LOGGER.debug("Added %d sensor entities", len(entities))
    else:
        _LOGGER.warning("No sensors were created for entry: %s", entry.entry_id)

def _device_info(entry: ConfigEntry) -> DeviceInfo:
    """Return device info."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Aptner",
        manufacturer="Aptner",
        model="v2 API",
    )

class AptnerBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Aptner sensors."""
    
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = _device_info(entry)

class AptnerFeeAmountSensor(AptnerBaseSensor):
    """Sensor for fee amount."""
    
    _attr_name = "관리비"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "KRW"

    def __init__(self, entry: ConfigEntry, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the fee amount sensor."""
        super().__init__(entry, coordinator)
        self._attr_unique_id = f"{entry.entry_id}_fee_amount"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        data = self.coordinator.data
        if not data or "fee" not in data:
            return None
        return data.get("fee")

    @property
    def extra_state_attributes(self):
        """Return additional state attributes."""
        data = self.coordinator.data
        if not data or not isinstance(data, dict):
            return {}
        return {
            "year": data.get("year"),
            "month": data.get("month"),
            "details": data.get("details", {}),
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # 데이터가 있고 fee 정보가 있으면 available
        data = self.coordinator.data
        return bool(data and isinstance(data, dict) and "fee" in data)

class AptnerReserveOverviewSensor(AptnerBaseSensor):
    """Sensor for reserve overview."""
    
    _attr_name = "방문차량 예약현황"
    _attr_icon = "mdi:car-clock"

    def __init__(self, entry: ConfigEntry, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the reserve overview sensor."""
        super().__init__(entry, coordinator)
        self._attr_unique_id = f"{entry.entry_id}_reserve_overview"

    @property
    def native_value(self):
        """Return the number of cars with future reservations."""
        data = self.coordinator.data
        if not data or not isinstance(data, dict):
            return 0
        return len(data)

    @property
    def extra_state_attributes(self):
        """Return the reservation data."""
        data = self.coordinator.data
        if not data or not isinstance(data, dict):
            return {"cars": {}}
        return {"cars": data}
