from gpiozero import LED
from Libraries import Subscriber
import time
import json
import signal


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
        print(topic, message)
        if message["message"].lower() == "on":
            self.led.on()
        elif message["message"].lower() == "off":
            self.led.off()

    def subscribe(self, topic, QoS):
        self.client.subscribe(topic, QoS)

    def stop(self):
        self.client.stop()


def signal_handler(sig, frame, *leds):
    """Handles Ctrl+C to stop the LEDs cleanly"""
    print("\nStopping MQTT LED service...")
    for led in leds:
        led.stop()


if __name__ == "__main__":
    settings = json.load(open("mqtt_settings.json"))
    redled = Led(21, "RedLED", settings["broker"], settings["port"])
    greenled = Led(26, "GreenLED", settings["broker"], settings["port"])
    yellowled = Led(16, "YellowLED", settings["broker"], settings["port"])
    redled.start()
    greenled.start()
    yellowled.start()
    redled.subscribe(settings["baseTopic"] + "/kennel1/leds/redled", 0)
    greenled.subscribe(settings["baseTopic"] + "/kennel1/leds/greenled", 0)
    yellowled.subscribe(settings["baseTopic"] + "/kennel1/leds/yellowled", 0)
    # Wait for keyboardinterrupt
    signal.signal(signal.SIGINT, signal_handler)

    # Keep the script running without a while loop
    signal.pause()
