from gpiozero import LED
from Libraries import Subscriber
import time
import json


class Led:
    def __init__(self, pin, clientID, broker, port):
        self.led = LED(pin)
        self.clientID = clientID
        self.broker = broker
        self.port = port
        self.client = Subscriber(clientID, broker, port, self)

    def start(self):
        self.client.start()
        time.sleep(1)

    def notify(self, topic, msg):
        message = json.loads(msg)
        if message["message"].lower() == "on":
            self.led.on()
        elif message["message"].lower() == "off":
            self.led.off()

    def subscribe(self, topic, QoS):
        self.client.subscribe(topic, QoS)

    def stop(self):
        self.client.stop()


if __name__ == "__main__":
    settings = json.load(open("../mqtt_settings.json"))
    led = Led(21, "Subscriber", settings["broker"], settings["port"])
    led.start()
    led.subscribe(settings["baseTopic"], 0)
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            break
    led.stop()
