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
        self._paho_mqtt = PahoMQTT.Client(clientID, True)
        self._paho_mqtt.on_connect = self.connectNotification
        self._paho_mqtt.on_message = self.messageReceivedNotification

    def connectNotification(self, paho_mqtt, userdata, flags, rc):
        print(f"Connected to {self.broker} with result code {rc}")

    def messageReceivedNotification(self, paho_mqtt, userdata, msg):
        self.notifier.notify(msg.topic, msg.payload)

    def subscribe(self, topic, QoS):
        self._paho_mqtt.subscribe(topic, QoS)
        self._isSubscriber = True
        self._topic = topic
        print(f"Subscribed to {self._topic}")

    def unsubscribe(self):
        if self._isSubscriber:
            self._paho_mqtt.unsubscribe(self._topic)
            print(f"Unsubscribed from {self._topic}")

    def start(self):
        self._paho_mqtt.connect(self.broker, self.port)
        self._paho_mqtt.loop_start()

    def stop(self):
        if self._isSubscriber:
            self._paho_mqtt.unsubscribe(self._topic)
        self._paho_mqtt.loop_stop()
        self._paho_mqtt.disconnect()
        print(f"Disconnected from {self.broker}")
