"""Config flow for Ballu ASP-100 integration."""
from __future__ import annotations

import logging
import voluptuous as vol
from typing import Any

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN, CONF_DEVICE_MAC, CONF_CLIENT_ID, 
    CONF_BROKER_HOST, CONF_BROKER_PORT, CONF_USERNAME, CONF_PASSWORD,
    DEFAULT_BROKER_HOST, DEFAULT_BROKER_PORT, DEFAULT_USERNAME, DEFAULT_PASSWORD
)

_LOGGER = logging.getLogger(__name__)

class BalluConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ballu ASP-100."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            # Validate input
            if not user_input[CONF_DEVICE_MAC].strip():
                errors[CONF_DEVICE_MAC] = "device_mac_required"
            elif not user_input[CONF_CLIENT_ID].strip():
                errors[CONF_CLIENT_ID] = "client_id_required"
            else:
                # Create unique ID and check if already configured
                unique_id = f"ballu_asp100_{user_input[CONF_DEVICE_MAC].lower().replace(':', '')}"
                
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                
                _LOGGER.debug("Creating Ballu ASP-100 entry with unique_id: %s", unique_id)
                
                # Create the config entry
                return self.async_create_entry(
                    title=f"Бризер ({user_input[CONF_DEVICE_MAC]})",
                    data=user_input,
                )

        # Show the form with pre-filled values
        data_schema = vol.Schema({
            vol.Required(CONF_DEVICE_MAC, default="a0dd6c0b3cd8"): str,
            vol.Required(CONF_CLIENT_ID, default="bb2791f30a28776d6fe45943f1b68928"): str,
            vol.Required(CONF_BROKER_HOST, default=DEFAULT_BROKER_HOST): str,
            vol.Required(CONF_BROKER_PORT, default=DEFAULT_BROKER_PORT): int,
            vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
            vol.Required(CONF_PASSWORD, default=DEFAULT_PASSWORD): str,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "entity_id": "climate.ballu_oneair_asp_100_breezer"
            }
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return BalluOptionsFlowHandler(config_entry)


class BalluOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Ballu ASP-100."""
    
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        return await self.async_step_user(user_input)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            # Update config entry with new data
            new_data = {**self.config_entry.data, **user_input}
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            return self.async_create_entry(title="", data={})

        # Pre-fill form with current values
        data_schema = vol.Schema({
            vol.Required(CONF_BROKER_HOST, default=self.config_entry.data.get(CONF_BROKER_HOST, DEFAULT_BROKER_HOST)): str,
            vol.Required(CONF_BROKER_PORT, default=self.config_entry.data.get(CONF_BROKER_PORT, DEFAULT_BROKER_PORT)): int,
            vol.Required(CONF_USERNAME, default=self.config_entry.data.get(CONF_USERNAME, DEFAULT_USERNAME)): str,
            vol.Required(CONF_PASSWORD, default=self.config_entry.data.get(CONF_PASSWORD, DEFAULT_PASSWORD)): str,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )