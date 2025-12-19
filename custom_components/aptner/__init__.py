from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import ConfigType

from .api import AptnerClient
from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_ID,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL_MIN,
    DEFAULT_SCAN_INTERVAL_MIN,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_FEE = "fee"
SERVICE_FINDCAR = "findcar"
SERVICE_GET_CAR_STATUS = "get_car_status"  # 새로운 서비스
SERVICE_GET_RESERVE_STATUS = "get_reserve_status"
SERVICE_RESERVE_CAR = "reserve_car"

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Aptner from a config entry."""
    _LOGGER.debug("Setting up Aptner entry: %s", entry.entry_id)
    
    client = AptnerClient(
        hass,
        user_id=entry.data[CONF_ID],
        password=entry.data[CONF_PASSWORD],
    )
    
    # Store client
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
    }

    # Register services (mirror pyscript services)
    async def svc_fee(call: ServiceCall):
        try:
            return await client.get_fee()
        except Exception as e:
            raise HomeAssistantError(f"Aptner fee failed: {e}") from e

    async def svc_findcar(call: ServiceCall):
        try:
            carno = call.data.get("carno")
            return await client.find_car(carno=carno)
        except Exception as e:
            raise HomeAssistantError(f"Aptner findcar failed: {e}") from e

    async def svc_get_car_status(call: ServiceCall):
        """Get current car status for device tracking."""
        try:
            entry_id = call.data.get("entry_id")
            client_to_use = client  # 기본적으로 현재 엔트리의 클라이언트 사용
            
            if entry_id and entry_id in hass.data[DOMAIN]:
                client_to_use = hass.data[DOMAIN][entry_id]["client"]
            
            carno = call.data.get("carno")
            return await client_to_use.get_car_status(carno=carno)
        except Exception as e:
            raise HomeAssistantError(f"Aptner get_car_status failed: {e}") from e

    async def svc_get_reserve_status(call: ServiceCall):
        try:
            return await client.get_reserve_status()
        except Exception as e:
            raise HomeAssistantError(f"Aptner get_reserve_status failed: {e}") from e

    async def svc_reserve_car(call: ServiceCall):
        try:
            await client.reserve_car(
                date=call.data["date"],
                purpose=call.data["purpose"],
                carno=call.data["carno"],
                days=int(call.data["days"]),
                phone=call.data["phone"],
            )
        except Exception as e:
            raise HomeAssistantError(f"Aptner reserve_car failed: {e}") from e

    hass.services.async_register(
        DOMAIN,
        SERVICE_FEE,
        svc_fee,
        schema=vol.Schema({}),
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_FINDCAR,
        svc_findcar,
        schema=vol.Schema({vol.Optional("carno"): str}),
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_CAR_STATUS,
        svc_get_car_status,
        schema=vol.Schema({
            vol.Optional("entry_id"): str,
            vol.Optional("carno"): str,
        }),
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_RESERVE_STATUS,
        svc_get_reserve_status,
        schema=vol.Schema({}),
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESERVE_CAR,
        svc_reserve_car,
        schema=vol.Schema(
            {
                vol.Required("date"): str,     # yyyy.MM.dd
                vol.Required("purpose"): str,
                vol.Required("carno"): str,
                vol.Required("days"): vol.Coerce(int),
                vol.Required("phone"): str,
            }
        ),
    )

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Add update listener for options changes
    entry.async_on_unload(
        entry.add_update_listener(async_update_options)
    )
    
    return True

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Update options - reload the entry to apply changes."""
    _LOGGER.debug("Reloading Aptner entry due to options change: %s", entry.entry_id)
    await hass.config_entries.async_reload(entry.entry_id)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Aptner entry: %s", entry.entry_id)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok