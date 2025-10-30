"""Climate platform for Ballu ASP-100 Breezer."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.climate.const import (
    PRESET_ECO,
    PRESET_BOOST,
    PRESET_SLEEP,
    PRESET_COMFORT,
    PRESET_NONE,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, CONF_DEVICE_MAC, CONF_CLIENT_ID, MANUFACTURER, MODEL, TOPIC_PREFIX, DEVICE_TYPE

_LOGGER = logging.getLogger(__name__)

# Custom presets for Yandex Smart Home compatibility
PRESET_AUTO = "auto"

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ballu ASP-100 breezer from config entry."""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    device_mac = config_entry.data[CONF_DEVICE_MAC]
    client_id = config_entry.data.get(CONF_CLIENT_ID, "")
    
    _LOGGER.debug("Setting up Ballu ASP-100 Breezer: MAC=%s, Client=%s", device_mac, client_id)
    
    # Build topic prefix
    topic_prefix = f"{TOPIC_PREFIX}/{DEVICE_TYPE}/{client_id}"
    
    entity = BalluASP100Breezer(entry_data, device_mac, topic_prefix, config_entry.title)
    async_add_entities([entity])

class BalluASP100Breezer(ClimateEntity):
    """Representation of a Ballu ASP-100 Breezer device."""

    _attr_has_entity_name = True
    _attr_name = "Ballu ONEAIR ASP-100 Breezer"
    
    # Supported features - updated for breezer
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE |
        ClimateEntityFeature.FAN_MODE |
        ClimateEntityFeature.PRESET_MODE |
        ClimateEntityFeature.TURN_OFF |
        ClimateEntityFeature.TURN_ON
    )
    
    # HVAC modes - simplified for breezer
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.FAN_ONLY]
    
    # Preset modes for Yandex Smart Home compatibility
    _attr_preset_modes = [
        PRESET_COMFORT,  # "comfort" - Ручной режим
        PRESET_AUTO,     # "auto" - Авто по CO2
        PRESET_SLEEP,    # "sleep" - Ночной режим  
        PRESET_BOOST,    # "boost" - Турбо режим
        PRESET_ECO,      # "eco" - Эко режим
        PRESET_NONE      # "none" - Без пресета
    ]
    
    # Fan modes - based on the example
    _attr_fan_modes = ["Off", "S1", "S2", "S3", "S4", "S5", "S6", "S7"]
    
    # Temperature settings
    _attr_min_temp = 5
    _attr_max_temp = 25
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1

    def __init__(self, entry_data: dict, device_mac: str, topic_prefix: str, name: str) -> None:
        """Initialize the breezer device."""
        self._entry_data = entry_data
        self._device_mac = device_mac
        self._topic_prefix = topic_prefix
        self._mqtt_client = entry_data["mqtt_client"]
        self._attr_unique_id = f"ballu_asp100_{device_mac}_breezer"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_mac)},
            "name": "Ballu ONEAIR ASP-100 Breezer",
            "manufacturer": MANUFACTURER,
            "model": MODEL,
        }
        
        # State attributes - initialize as unknown
        self._hvac_mode = HVACMode.OFF
        self._target_temperature = 20
        self._current_temperature = None
        self._fan_mode = None  # Start as None to indicate unknown state
        self._preset_mode = PRESET_NONE
        self._current_mode = 0  # 0=Off, 1=Manual, 2=Auto CO2, 3=Night, 4=Turbo, 5=Eco
        self._current_speed = None  # Start as None
        
        # Track if we've received initial state
        self._state_received = {
            "mode": False,
            "speed": False,
            "temperature": False,
            "current_temp": False
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT topics when entity is added to HA."""
        await self._subscribe_topics()
        
        # Request current state from device
        await self._request_current_state()

    async def _request_current_state(self):
        """Request current state from the device by publishing to command topics."""
        _LOGGER.debug("Requesting current state from device")
        
        # Publish empty messages to trigger state updates
        topics_to_trigger = [
            f"{self._topic_prefix}/control/mode",
            f"{self._topic_prefix}/control/speed", 
            f"{self._topic_prefix}/control/temperature",
        ]
        
        for topic in topics_to_trigger:
            try:
                await self._mqtt_client.publish(topic, "")
                _LOGGER.debug("Triggered state request for: %s", topic)
            except Exception as e:
                _LOGGER.error("Error triggering state request for %s: %s", topic, e)

    async def _subscribe_topics(self) -> None:
        """Subscribe to MQTT topics."""
        
        topics = {
            "mode": f"{self._topic_prefix}/state/mode",
            "speed": f"{self._topic_prefix}/state/speed", 
            "temperature": f"{self._topic_prefix}/state/temperature",
            "current_temp": f"{self._topic_prefix}/state/sensor/temperature",
        }

        @callback
        def message_received(topic: str, payload: str):
            """Handle incoming MQTT messages."""
            try:
                _LOGGER.debug("Received MQTT message: %s = %s", topic, payload)
                
                if "mode" in topic:
                    self._state_received["mode"] = True
                    self._update_mode_from_payload(payload)
                elif "speed" in topic:
                    self._state_received["speed"] = True
                    self._update_fan_from_payload(payload)
                elif "temperature" in topic and "sensor" not in topic:
                    self._state_received["temperature"] = True
                    self._update_temperature_from_payload(payload)
                elif "sensor/temperature" in topic:
                    self._state_received["current_temp"] = True
                    self._update_current_temp_from_payload(payload)
                    
                # Log state synchronization status
                if all(self._state_received.values()):
                    _LOGGER.debug("All state synchronized: mode=%s, speed=%s, temp=%s, current_temp=%s",
                                 self._current_mode, self._fan_mode, self._target_temperature, self._current_temperature)
                
                self.async_write_ha_state()
                
            except Exception as e:
                _LOGGER.error("Error processing MQTT message: %s", e)

        for topic_attr, topic in topics.items():
            self._mqtt_client.subscribe(topic, message_received)
            _LOGGER.debug("Subscribed to: %s", topic)

    def _update_mode_from_payload(self, payload: str) -> None:
        """Update mode from payload."""
        try:
            mode_value = int(payload)
            self._current_mode = mode_value
            
            # Update HVAC mode
            if mode_value == 0:
                self._hvac_mode = HVACMode.OFF
            else:
                self._hvac_mode = HVACMode.FAN_ONLY
            
            # Update preset mode for Yandex compatibility
            if mode_value == 1:
                self._preset_mode = PRESET_COMFORT  # "comfort"
            elif mode_value == 2:
                self._preset_mode = PRESET_AUTO     # "auto" 
            elif mode_value == 3:
                self._preset_mode = PRESET_SLEEP    # "sleep"
            elif mode_value == 4:
                self._preset_mode = PRESET_BOOST    # "boost"
            elif mode_value == 5:
                self._preset_mode = PRESET_ECO      # "eco"
            else:
                self._preset_mode = PRESET_NONE     # "none"
                
            _LOGGER.debug("Updated mode: value=%s, hvac=%s, preset=%s", 
                         mode_value, self._hvac_mode, self._preset_mode)
                        
        except ValueError:
            _LOGGER.error("Invalid mode payload: %s", payload)

    def _update_fan_from_payload(self, payload: str) -> None:
        """Update fan mode from payload."""
        try:
            speed_mapping = {
                "0": "Off",
                "1": "S1", 
                "2": "S2",
                "3": "S3",
                "4": "S4",
                "5": "S5",
                "6": "S6",
                "7": "S7",
            }
            
            # Handle both string and integer payloads
            if payload.isdigit():
                self._fan_mode = speed_mapping.get(payload, "Off")
                self._current_speed = payload
            else:
                # If payload is already a string like "S2", use it directly
                self._fan_mode = payload if payload in self._attr_fan_modes else "Off"
                self._current_speed = self._fan_mode.replace("S", "") if self._fan_mode.startswith("S") else "0"
            
            _LOGGER.debug("Updated fan mode: %s (raw: %s)", self._fan_mode, payload)
            
        except Exception as e:
            _LOGGER.error("Error updating fan mode from payload '%s': %s", payload, e)
            self._fan_mode = "Off"
            self._current_speed = "0"

    def _update_temperature_from_payload(self, payload: str) -> None:
        """Update target temperature from payload."""
        try:
            self._target_temperature = float(payload)
            _LOGGER.debug("Updated target temperature: %s", self._target_temperature)
        except ValueError:
            _LOGGER.error("Invalid temperature payload: %s", payload)

    def _update_current_temp_from_payload(self, payload: str) -> None:
        """Update current temperature from payload."""
        try:
            self._current_temperature = float(payload)
            _LOGGER.debug("Updated current temperature: %s", self._current_temperature)
        except ValueError:
            _LOGGER.error("Invalid current temperature payload: %s", payload)

    # Control methods
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if temperature := kwargs.get(ATTR_TEMPERATURE):
            await self._mqtt_client.publish(
                f"{self._topic_prefix}/control/temperature",
                str(int(temperature)),
            )
            self._target_temperature = temperature
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self._mqtt_client.publish(
                f"{self._topic_prefix}/control/mode",
                "0",  # Turn off
            )
            self._hvac_mode = HVACMode.OFF
            self._current_mode = 0
            self._preset_mode = PRESET_NONE
        else:  # FAN_ONLY
            # Turn on with last used mode, or default to comfort mode
            mode_to_set = self._current_mode if self._current_mode > 0 else 1
            await self._mqtt_client.publish(
                f"{self._topic_prefix}/control/mode",
                str(mode_to_set),
            )
            self._hvac_mode = HVACMode.FAN_ONLY
            self._current_mode = mode_to_set
            
            # Update preset based on mode
            if mode_to_set == 1:
                self._preset_mode = PRESET_COMFORT
            elif mode_to_set == 2:
                self._preset_mode = PRESET_AUTO
            elif mode_to_set == 3:
                self._preset_mode = PRESET_SLEEP
            elif mode_to_set == 4:
                self._preset_mode = PRESET_BOOST
            elif mode_to_set == 5:
                self._preset_mode = PRESET_ECO
        
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        speed_mapping = {
            "Off": "0",
            "S1": "1",
            "S2": "2", 
            "S3": "3",
            "S4": "4",
            "S5": "5",
            "S6": "6",
            "S7": "7",
        }
        speed_value = speed_mapping.get(fan_mode, "0")
        
        await self._mqtt_client.publish(
            f"{self._topic_prefix}/control/speed",
            speed_value,
        )
        
        self._fan_mode = fan_mode
        self._current_speed = speed_value
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        preset_mapping = {
            PRESET_COMFORT: "1",  # Ручной режим
            PRESET_AUTO: "2",     # Авто по CO2
            PRESET_SLEEP: "3",    # Ночной режим
            PRESET_BOOST: "4",    # Турбо режим
            PRESET_ECO: "5",      # Эко режим
        }
        
        mode_value = preset_mapping.get(preset_mode, "1")
        
        await self._mqtt_client.publish(
            f"{self._topic_prefix}/control/mode",
            mode_value,
        )
        
        self._preset_mode = preset_mode
        self._hvac_mode = HVACMode.FAN_ONLY
        self._current_mode = int(mode_value)
        self.async_write_ha_state()

    # Property methods
    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation mode."""
        return self._hvac_mode

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        # Return "unknown" if we haven't received state yet
        if self._fan_mode is None:
            return "Off"  # Default to Off until we get actual state
        return self._fan_mode

    @property
    def preset_mode(self) -> str | None:
        """Return the preset setting."""
        return self._preset_mode