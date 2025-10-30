"""Config flow for Ballu ASP-100 integration."""
from __future__ import annotations

import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
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

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        
        if user_input is not None:
            # Basic validation
            device_mac = user_input[CONF_DEVICE_MAC].strip().lower()
            client_id = user_input[CONF_CLIENT_ID].strip().lower()
            
            if not device_mac or len(device_mac) != 12:
                errors[CONF_DEVICE_MAC] = "invalid_mac"
            if not client_id or len(client_id) != 32:
                errors[CONF_CLIENT_ID] = "invalid_client_id"
            if not user_input[CONF_BROKER_HOST]:
                errors[CONF_BROKER_HOST] = "invalid_host"
            if not 1 <= user_input[CONF_BROKER_PORT] <= 65535:
                errors[CONF_BROKER_PORT] = "invalid_port"
            
            if not errors:
                # Create unique ID and check if already configured
                unique_id = f"ballu_asp100_{device_mac}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                
                _LOGGER.info("Creating Ballu ASP-100 config entry: %s", device_mac)
                
                # Create the config entry
                return self.async_create_entry(
                    title=f"Ballu ASP-100 ({device_mac})",
                    data={
                        CONF_DEVICE_MAC: device_mac,
                        CONF_CLIENT_ID: client_id,
                        CONF_BROKER_HOST: user_input[CONF_BROKER_HOST],
                        CONF_BROKER_PORT: user_input[CONF_BROKER_PORT],
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
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
                "device_mac": "a0dd6c0b3cd8",
                "client_id": "bb2791f30a28776d6fe45943f1b68928"
            }
        )