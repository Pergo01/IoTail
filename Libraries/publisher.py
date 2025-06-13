#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import paho.mqtt.client as PahoMQTT


class Publisher:
    def __init__(self, clientID, broker, port, notifier):
        self.clientID = clientID
        self.broker = broker
        self.port = port
        self.notifier = notifier
        self._isSubscriber = False
        self._paho_mqtt = PahoMQTT.Client(
            clientID, True
        )  # Create a new MQTT client instance
        self._paho_mqtt.on_connect = (
            self.connectNotification
        )  # Set the connect notification callback

    def connectNotification(self, paho_mqtt, userdata, flags, rc):
        """Callback for when the client connects to the broker."""
        print(f"Connected to {self.broker} with result code {rc}")

    def publish(self, topic, msg, QoS):
        """Publishes a message to a specified topic."""
        self._paho_mqtt.publish(
            topic, json.dumps(msg), QoS
        )  # Publish the message to the specified topic
        print(f"Message published on topic {topic}")

    def start(self):
        """Starts the MQTT client and connects to the broker."""
        self._paho_mqtt.connect(self.broker, self.port)  # Connect to the MQTT broker
        self._paho_mqtt.loop_start()  # Start the MQTT loop to process network traffic and dispatch callbacks

    def stop(self):
        """Stops the MQTT client and disconnects from the broker."""
        self._paho_mqtt.loop_stop()  # Stop the MQTT loop to stop processing network traffic and dispatching callbacks
        self._paho_mqtt.disconnect()  # Disconnect from the MQTT broker
        print(f"Disconnected from {self.broker}")
