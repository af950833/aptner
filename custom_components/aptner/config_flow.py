from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .api import AptnerClient
from .const import (
    DOMAIN,
    CONF_ID,
    CONF_PASSWORD,
    CONF_CARS,
    CONF_SCAN_INTERVAL_MIN,
    DEFAULT_SCAN_INTERVAL_MIN,
)

_LOGGER = logging.getLogger(__name__)

class AptnerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            client = AptnerClient(self.hass, user_input[CONF_ID], user_input[CONF_PASSWORD])
            try:
                await client.authenticate()
            except Exception as ex:
                _LOGGER.error("Authentication failed: %s", ex)
                errors["base"] = "auth_failed"
            else:
                return self.async_create_entry(title="Aptner", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_ID): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return AptnerOptionsFlowHandler(config_entry)

class AptnerOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self.entry = entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Manage the options."""
        errors = {}
        
        if user_input is not None:
            try:
                # Normalize car list (comma / space separated)
                cars_raw = user_input.get(CONF_CARS, "")
                cars = [c.strip() for c in cars_raw.replace("\n", ",").split(",") if c.strip()]
                
                # Validate scan interval
                scan_interval = int(user_input.get(CONF_SCAN_INTERVAL_MIN, DEFAULT_SCAN_INTERVAL_MIN))
                if not (2 <= scan_interval <= 1440):
                    errors[CONF_SCAN_INTERVAL_MIN] = "invalid_interval"
                
                if not errors:
                    # Create options entry
                    options = {
                        CONF_CARS: cars,
                        CONF_SCAN_INTERVAL_MIN: scan_interval,
                    }
                    
                    _LOGGER.debug("Saving options: %s", options)
                    return self.async_create_entry(
                        title="",
                        data=options,
                    )
            except ValueError as ex:
                _LOGGER.error("Value error in options: %s", ex)
                errors["base"] = "invalid_input"
            except Exception as ex:
                _LOGGER.error("Unexpected error in options: %s", ex, exc_info=True)
                errors["base"] = "unknown"
            else:
                # 성공적으로 저장했으므로 폼을 다시 표시하지 않음
                return self.async_create_entry(title="", data=user_input)

        # Get existing values for form
        cars_existing = self.entry.options.get(CONF_CARS, [])
        if isinstance(cars_existing, list):
            cars_str = ", ".join(cars_existing)
        else:
            cars_str = str(cars_existing)
            
        scan_interval = self.entry.options.get(CONF_SCAN_INTERVAL_MIN, DEFAULT_SCAN_INTERVAL_MIN)

        schema = vol.Schema(
            {
                vol.Optional(CONF_CARS, default=cars_str): str,
                vol.Optional(CONF_SCAN_INTERVAL_MIN, default=scan_interval): vol.All(
                    vol.Coerce(int), 
                    vol.Range(min=2, max=1440)
                ),
            }
        )
        return self.async_show_form(
            step_id="init", 
            data_schema=schema, 
            errors=errors
        )