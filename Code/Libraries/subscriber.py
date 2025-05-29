#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import paho.mqtt.client as PahoMQTT


class Subscriber:
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
        self._paho_mqtt.on_message = (
            self.messageReceivedNotification
        )  # Set the message received notification callback

    def connectNotification(self, paho_mqtt, userdata, flags, rc):
        """Callback for when the client connects to the broker."""
        print(f"Connected to {self.broker} with result code {rc}")

    def messageReceivedNotification(self, paho_mqtt, userdata, msg):
        """Callback for when a message is received on a subscribed topic."""
        self.notifier.notify(
            msg.topic, msg.payload
        )  # Notify the notifier with the received message

    def subscribe(self, topic, QoS):
        """Subscribes to a specified topic with a given Quality of Service (QoS)."""
        self._paho_mqtt.subscribe(
            topic, QoS
        )  # Subscribe to the specified topic with the given QoS
        self._isSubscriber = True  # Set the subscriber flag to True
        self._topic = topic  # Store the topic for later use
        print(f"Subscribed to {self._topic}")

    def unsubscribe(self):
        """Unsubscribes from the currently subscribed topic."""
        if self._isSubscriber:  # Check if the client is a subscriber
            self._paho_mqtt.unsubscribe(self._topic)  # Unsubscribe from the topic
            print(f"Unsubscribed from {self._topic}")

    def start(self):
        """Starts the MQTT client and connects to the broker."""
        self._paho_mqtt.connect(self.broker, self.port)  # Connect to the MQTT broker
        self._paho_mqtt.loop_start()  # Start the MQTT loop to process network traffic and dispatch callbacks

    def stop(self):
        """Stops the MQTT client and disconnects from the broker."""
        if self._isSubscriber:  # Check if the client is a subscriber
            self._paho_mqtt.unsubscribe(self._topic)  # Unsubscribe from the topic
        self._paho_mqtt.loop_stop()  # Stop the MQTT loop to stop processing network traffic and dispatching callbacks
        self._paho_mqtt.disconnect()  # Disconnect from the MQTT broker
        print(f"Disconnected from {self.broker}")
