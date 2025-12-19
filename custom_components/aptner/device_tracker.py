from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_CARS, CONF_SCAN_INTERVAL_MIN, DEFAULT_SCAN_INTERVAL_MIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Aptner device trackers from a config entry."""
    _LOGGER.debug("Setting up device trackers for entry: %s", entry.entry_id)
    
    data = hass.data[DOMAIN][entry.entry_id]
    client = data["client"]
    
    # Get scan interval from options or config
    if entry.options:
        scan_min = entry.options.get(CONF_SCAN_INTERVAL_MIN, DEFAULT_SCAN_INTERVAL_MIN)
    else:
        scan_min = entry.data.get(CONF_SCAN_INTERVAL_MIN, DEFAULT_SCAN_INTERVAL_MIN)
    
    update_interval = timedelta(minutes=int(scan_min))
    
    # Car status coordinator - 새로운 get_car_status 메서드 사용
    async def async_update_car_status() -> dict[str, dict[str, Any]]:
        try:
            if entry.options:
                cars: list[str] = entry.options.get(CONF_CARS, []) or []
            else:
                cars: list[str] = entry.data.get(CONF_CARS, []) or []
            
            if not cars:
                return {}
            
            # 여러 차량의 상태를 한 번에 가져오기 위해 carno=None 사용
            all_cars_data = await client.get_car_status(carno=None)
            result = {}
            
            for carno in cars:
                if carno:
                    if carno in all_cars_data:
                        result[carno] = all_cars_data[carno]
                    else:
                        # 차량 정보가 없으면 not_home으로 간주
                        result[carno] = {
                            "carNo": carno,
                            "isExit": True,
                            "inDatetime": None,
                            "outDatetime": None,
                            "intime": None,
                            "outtime": None,
                            "status": "not_found"
                        }
            
            return result
        except Exception as err:
            raise UpdateFailed(f"Error fetching car status data: {err}") from err
    
    coordinator = DataUpdateCoordinator(
        hass,
        logger=_LOGGER,
        name=f"{DOMAIN}_car_status_{entry.entry_id}",
        update_method=async_update_car_status,
        update_interval=update_interval,
    )
    
    # Get initial data
    await coordinator.async_config_entry_first_refresh()
    
    # Create device tracker entities
    entities: list[TrackerEntity] = []
    
    # Get cars list
    if entry.options:
        cars: list[str] = entry.options.get(CONF_CARS, []) or []
    else:
        cars: list[str] = entry.data.get(CONF_CARS, []) or []
    
    _LOGGER.debug("Creating device trackers for cars: %s", cars)
    
    for carno in cars:
        if carno:
            entities.append(AptnerCarTracker(entry, coordinator, carno))
    
    async_add_entities(entities)
    
    _LOGGER.debug("Added %d device tracker entities", len(entities))

def _device_info(entry: ConfigEntry, carno: str) -> DeviceInfo:
    """Return device info for a specific car."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{carno}")},
        name=f"Aptner - {carno}",
        manufacturer="Aptner",
        model="차량 트래커",
        via_device=(DOMAIN, entry.entry_id),
    )

class AptnerCarTracker(CoordinatorEntity, TrackerEntity):
    """Device tracker for Aptner cars."""
    
    _attr_has_entity_name = True
    _attr_icon = "mdi:car"
    _attr_should_poll = False  # coordinator가 업데이트를 처리하므로 False

    def __init__(self, entry: ConfigEntry, coordinator: DataUpdateCoordinator, carno: str) -> None:
        """Initialize the car tracker."""
        super().__init__(coordinator)
        self._entry = entry
        self._carno = carno
        
        # entity_id가 중복되지 않도록 설정
        # 방법 1: name을 비워두고 has_entity_name=True 사용
        self._attr_name = None  # 비워둠
        self._attr_has_entity_name = False  # False로 설정
        
        # 방법 2: 명시적으로 name 설정
        # self._attr_name = f"Aptner {carno}"
        
        # unique_id는 필수
        self._attr_unique_id = f"{entry.entry_id}_tracker_{carno}"
        self._attr_device_info = _device_info(entry, carno)
        
        # entity_id를 명시적으로 설정 (선택사항)
        # device_tracker는 entity_id가 중요하므로 명시적으로 설정
        self.entity_id = f"device_tracker.aptner_{carno}"

    @property
    def name(self) -> str:
        """Return the name of the device."""
        # device_info의 name을 반환하거나 간단한 이름 설정
        return f"Aptner {self._carno}"

    @property
    def source_type(self) -> str:
        """Return the source type of the device."""
        return "gps"

    @property
    def state(self) -> str:
        """Return the state of the device (home/not_home)."""
        data = self.coordinator.data
        if not data or self._carno not in data:
            return "not_home"
        
        car_data = data[self._carno]
        is_exit = car_data.get("isExit")
        
        # isExit가 False면 주차 중(Home), True면 외출 중(Not home)
        if is_exit is False:
            return "home"
        elif is_exit is True:
            return "not_home"
        else:
            # 값이 없으면 not_home으로 처리
            return "not_home"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        data = self.coordinator.data
        if not data or self._carno not in data:
            return {
                "car_number": self._carno,
                "status": "unknown",
                "is_exit": None,
            }
        
        car_data = data[self._carno]
        attributes = {
            "car_number": self._carno,
            "status": car_data.get("status", "unknown"),
            "is_exit": car_data.get("isExit"),
        }
        
        # 입출차 시간 정보 추가
        if car_data.get("inDatetime"):
            attributes["in_datetime"] = car_data.get("inDatetime")
        if car_data.get("outDatetime"):
            attributes["out_datetime"] = car_data.get("outDatetime")
        
        return attributes