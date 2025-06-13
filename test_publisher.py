#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from Libraries import Publisher
import time


class test:
    def __init__(self, clientID, broker, port):
        self.clientID = clientID
        self.broker = broker
        self.port = port
        self.client = Publisher(
            clientID, broker, port, self
        )  # Initialize Publisher client

    def start(self):
        """Start the MQTT client."""
        self.client.start()
        time.sleep(1)

    def publish(self, topic, message, QoS):
        """Publish a message to the specified topic."""
        self.client.publish(topic, message, QoS)

    def stop(self):
        """Stop the MQTT client."""
        self.client.stop()


settings = json.load(open("mqtt_settings.json"))  # Load MQTT settings from JSON file
publisher = test(
    "Publisher", settings["broker"], settings["port"]
)  # Create an instance of the test class
message = {"message": "Test message for IoTail project"}
publisher.start()
while True:
    try:
        time.sleep(1)
        publisher.publish(
            settings["baseTopic"], message, 2
        )  # Publish a message to the base topic with QoS 2
    except KeyboardInterrupt:  # wait for a keyboard interrupt to stop the publisher
        break
publisher.stop()  # Stop the publisher client gracefully
