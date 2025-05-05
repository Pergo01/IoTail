from gpiozero import LED
from Libraries import Subscriber
import time
import json
import signal
import threading
import requests


class Led:
    def __init__(self, pin, clientID, broker, port, deviceID):
        self.deviceID = deviceID
        self.led = LED(pin)
        self.clientID = clientID
        self.broker = broker
        self.port = port
        self.client = Subscriber(clientID, broker, port, self)
        self.catalog_url = json.load(open("settings.json"))["catalog_url"]

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

    def heartbeat(self):
        while True:
            try:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer led_connector",
                }
                url = self.catalog_url + "/heartbeat"
                payload = {
                    "category": "sensor",
                    "deviceID": self.deviceID,
                }
                response = requests.post(url, headers=headers, data=json.dumps(payload))
                if response.status_code == 200:
                    print("Heartbeat sent successfully")
                else:
                    print("Failed to send heartbeat")
            except requests.exceptions.RequestException as e:
                print(f"Error sending heartbeat: {e}")
            time.sleep(60)


def signal_handler(sig, frame):
    """Handles Ctrl+C to stop the LEDs cleanly"""
    print("\nStopping MQTT LED service...")
    redled.stop()
    greenled.stop()
    yellowled.stop()


if __name__ == "__main__":
    settings = json.load(open("mqtt_settings.json"))
    redled = Led(21, "RedLED", settings["broker"], settings["port"], 3)
    greenled = Led(26, "GreenLED", settings["broker"], settings["port"], 4)
    yellowled = Led(16, "YellowLED", settings["broker"], settings["port"], 5)
    redled.start()
    greenled.start()
    yellowled.start()

    red_heartbeat_thread = threading.Thread(target=redled.heartbeat)
    red_heartbeat_thread.daemon = (
        True  # The thread will terminate when the program ends
    )
    red_heartbeat_thread.start()

    green_heartbeat_thread = threading.Thread(target=greenled.heartbeat)
    green_heartbeat_thread.daemon = (
        True  # The thread will terminate when the program ends
    )
    green_heartbeat_thread.start()

    yellow_heartbeat_thread = threading.Thread(target=yellowled.heartbeat)
    yellow_heartbeat_thread.daemon = (
        True  # The thread will terminate when the program ends
    )
    yellow_heartbeat_thread.start()

    redled.subscribe(settings["baseTopic"] + "/kennel1/leds/redled", 0)
    greenled.subscribe(settings["baseTopic"] + "/kennel1/leds/greenled", 0)
    yellowled.subscribe(settings["baseTopic"] + "/kennel1/leds/yellowled", 0)
    # Wait for keyboardinterrupt
    signal.signal(signal.SIGINT, signal_handler)

    # Keep the script running without a while loop
    signal.pause()
