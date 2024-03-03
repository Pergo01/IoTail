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

    def notify(self, topic, msg):
        message = json.loads(msg)
        print(message["message"])

    def subscribe(self, topic, QoS):
        self.client.subscribe(topic, QoS)

    def stop(self):
        self.client.stop()


settings = json.load(open("settings.json"))
publisher = test("Subscriber", settings["broker"], settings["port"])
publisher.start()
publisher.subscribe("IoT_sample", 0)
c = 0
while c < 10:
    time.sleep(1)
    c += 1
publisher.stop()
