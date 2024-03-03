#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from Libraries.publisher_subscriber import *
import time


class test:
    def __init__(self, clientID, broker, port):
        self.clientID = clientID
        self.broker = broker
        self.port = port
        self.client = PublisherSubscriber(clientID, broker, port, self)

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
c = 0
while c < 5:
    time.sleep(1)
    c += 1
publisher.publish("IoT_sample", message, 2)
while c < 10:
    time.sleep(1)
    c += 1
publisher.stop()
