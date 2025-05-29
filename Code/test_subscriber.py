#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from Libraries import Subscriber
import time


class test:
    def __init__(self, clientID, broker, port):
        self.clientID = clientID
        self.broker = broker
        self.port = port
        self.client = Subscriber(
            clientID, broker, port, self
        )  # Initialize Subscriber client

    def start(self):
        """Start the MQTT client."""
        self.client.start()
        time.sleep(1)

    def notify(self, topic, msg):
        """Callback function to handle incoming messages."""
        message = json.loads(msg)
        print(topic, message)

    def subscribe(self, topic, QoS):
        """Subscribe to a topic with the specified QoS."""
        self.client.subscribe(topic, QoS)

    def stop(self):
        """Stop the MQTT client."""
        self.client.stop()


settings = json.load(open("mqtt_settings.json"))  # Load MQTT settings from JSON file
subscriber = test(
    "Subscriber", settings["broker"], settings["port"]
)  # Create an instance of the test class
subscriber.start()  # Start the subscriber client
subscriber.subscribe(
    settings["baseTopic"] + "/#", 0
)  # Subscribe to the base topic with QoS 0
while True:  # Keep the subscriber running
    try:
        time.sleep(1)
    except KeyboardInterrupt:  # Wait for a keyboard interrupt to stop the subscriber
        break
subscriber.stop()  # Stop the subscriber client gracefully
