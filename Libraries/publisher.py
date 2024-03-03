#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Feb 23 10:12:44 2023

@author: alessandro
"""

import json
import paho.mqtt.client as PahoMQTT


class Publisher:
    def __init__(self, clientID, broker, port, notifier):
        self.clientID = clientID
        self.broker = broker
        self.port = port
        self.notifier = notifier
        self._isSubscriber = False
        self._paho_mqtt = PahoMQTT.Client(clientID, True)
        self._paho_mqtt.on_connect = self.connectNotification

    def connectNotification(self, paho_mqtt, userdata, flags, rc):
        print(f"Connected to {self.broker} with result code {rc}")

    def publish(self, topic, msg, QoS):
        self._paho_mqtt.publish(topic, json.dumps(msg), QoS)
        print(f"Message published on topic {topic}")

    def start(self):
        self._paho_mqtt.connect(self.broker, self.port)
        self._paho_mqtt.loop_start()

    def stop(self):
        self._paho_mqtt.loop_stop()
        self._paho_mqtt.disconnect()
        print(f"Disconnected from {self.broker}")
