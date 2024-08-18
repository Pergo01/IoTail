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
        self.client = Subscriber(clientID, broker, port, self)

    def start(self):
        self.client.start()
        time.sleep(1)

    def notify(self, topic, msg):
        message = json.loads(msg)
        print(message)

    def subscribe(self, topic, QoS):
        self.client.subscribe(topic, QoS)

    def stop(self):
        self.client.stop()


settings = json.load(open("mqtt_settings.json"))
subscriber = test("Subscriber", settings["broker"], settings["port"])
subscriber.start()
subscriber.subscribe(settings["baseTopic"], 0)
while True:
    try:
        time.sleep(1)
    except KeyboardInterrupt:
        break
subscriber.stop()
