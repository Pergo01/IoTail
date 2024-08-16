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
        self.client = Publisher(clientID, broker, port, self)

    def start(self):
        self.client.start()
        time.sleep(1)

    def publish(self, topic, message, QoS):
        self.client.publish(topic, message, QoS)

    def stop(self):
        self.client.stop()


settings = json.load(open("settings.json"))
publisher = test("Publisher", settings["broker"], settings["port"])
message = {"message": "Test message for IoTail project"}
publisher.start()
while True:
    try:
        time.sleep(1)
        publisher.publish(settings["baseTopic"], message, 2)
    except KeyboardInterrupt:
        break
publisher.stop()
