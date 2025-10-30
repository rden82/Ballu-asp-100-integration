"""MQTT client for Ballu ASP-100 integration."""
from __future__ import annotations

import logging
import asyncio
import ssl
from typing import Callable, Any
import paho.mqtt.client as mqtt

_LOGGER = logging.getLogger(__name__)

class BalluMQTTClient:
    """MQTT client for Ballu ASP-100."""
    
    def __init__(self, hass, config):
        """Initialize MQTT client."""
        self.hass = hass
        self.config = config
        self.client = None
        self.connected = False
        self.subscriptions = {}
        
    async def connect(self):
        """Connect to MQTT broker."""
        try:
            self.client = mqtt.Client()
            self.client.username_pw_set(
                self.config.get("username"), 
                self.config.get("password")
            )
            
            # Setup TLS
            self.client.tls_set(cert_reqs=ssl.CERT_NONE)
            self.client.tls_insecure_set(True)
            
            # Setup callbacks
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            self.client.on_disconnect = self._on_disconnect
            
            # Connect
            host = self.config.get("broker_host")
            port = self.config.get("broker_port")
            
            _LOGGER.debug("Connecting to MQTT broker: %s:%s", host, port)
            
            def _connect():
                self.client.connect(host, port, 60)
                self.client.loop_start()
            
            await self.hass.async_add_executor_job(_connect)
            
            # Wait for connection
            for _ in range(10):
                if self.connected:
                    _LOGGER.debug("Successfully connected to MQTT broker")
                    return True
                await asyncio.sleep(0.5)
            
            _LOGGER.error("Timeout connecting to MQTT broker")
            return False
            
        except Exception as e:
            _LOGGER.error("Error connecting to MQTT broker: %s", e)
            return False
    
    async def disconnect(self):
        """Disconnect from MQTT broker."""
        if self.client:
            def _disconnect():
                self.client.loop_stop()
                self.client.disconnect()
            
            await self.hass.async_add_executor_job(_disconnect)
            self.connected = False
    
    def _on_connect(self, client, userdata, flags, rc):
        """Handle MQTT connection."""
        if rc == 0:
            self.connected = True
            _LOGGER.debug("MQTT connected successfully")
            
            # Resubscribe to topics
            for topic, callback in self.subscriptions.items():
                client.subscribe(topic)
                _LOGGER.debug("Resubscribed to: %s", topic)
        else:
            _LOGGER.error("MQTT connection failed with code: %s", rc)
            self.connected = False
    
    def _on_message(self, client, userdata, msg):
        """Handle MQTT messages."""
        topic = msg.topic
        payload = msg.payload.decode()
        
        _LOGGER.debug("Received MQTT message: %s = %s", topic, payload)
        
        # Call registered callbacks
        for sub_topic, callback in self.subscriptions.items():
            if self._topic_matches(sub_topic, topic):
                callback(topic, payload)
    
    def _on_disconnect(self, client, userdata, rc):
        """Handle MQTT disconnection."""
        self.connected = False
        _LOGGER.debug("MQTT disconnected")
    
    def subscribe(self, topic: str, callback: Callable):
        """Subscribe to MQTT topic."""
        self.subscriptions[topic] = callback
        
        if self.connected and self.client:
            self.client.subscribe(topic)
            _LOGGER.debug("Subscribed to: %s", topic)
    
    async def publish(self, topic: str, payload: str, qos: int = 0, retain: bool = False):
        """Publish MQTT message."""
        if not self.connected:
            _LOGGER.error("Cannot publish, MQTT not connected")
            return False
        
        def _publish():
            self.client.publish(topic, payload, qos, retain)
        
        try:
            await self.hass.async_add_executor_job(_publish)
            _LOGGER.debug("Published: %s = %s", topic, payload)
            return True
        except Exception as e:
            _LOGGER.error("Error publishing to %s: %s", topic, e)
            return False
    
    def _topic_matches(self, subscription: str, topic: str) -> bool:
        """Check if topic matches subscription pattern."""
        if subscription == topic:
            return True
        
        # Simple wildcard matching
        if '+' in subscription or '#' in subscription:
            sub_parts = subscription.split('/')
            topic_parts = topic.split('/')
            
            for i, sub_part in enumerate(sub_parts):
                if i >= len(topic_parts):
                    return False
                if sub_part == '+':
                    continue
                if sub_part == '#':
                    return True
                if sub_part != topic_parts[i]:
                    return False
            
            return len(sub_parts) == len(topic_parts)
        
        return False