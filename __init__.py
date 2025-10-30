"""The Ballu ASP-100 integration."""
from __future__ import annotations

import logging
import asyncio
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .mqtt_client import BalluMQTTClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ballu ASP-100 from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Create MQTT client
    mqtt_client = BalluMQTTClient(hass, entry.data)
    
    # Store MQTT client in hass data
    hass.data[DOMAIN][entry.entry_id] = {
        "data": entry.data,
        "mqtt_client": mqtt_client
    }
    
    # Connect to MQTT broker
    try:
        if not await mqtt_client.connect():
            _LOGGER.error("Failed to connect to MQTT broker")
            return False
    except Exception as e:
        _LOGGER.error("Error connecting to MQTT broker: %s", e)
        return False

    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Disconnect MQTT client
    if entry.entry_id in hass.data.get(DOMAIN, {}):
        mqtt_client = hass.data[DOMAIN][entry.entry_id].get("mqtt_client")
        if mqtt_client:
            await mqtt_client.disconnect()
    
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        
        if not hass.data[DOMAIN]:  # If no entries left, remove the domain
            hass.data.pop(DOMAIN)
            
    return unload_ok