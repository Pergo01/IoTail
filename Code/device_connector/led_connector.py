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
        self.led = LED(pin)  # Initialize LED on specified GPIO pin
        self.clientID = clientID
        self.broker = broker
        self.port = port
        self.client = Subscriber(clientID, broker, port, self)  # Initialize MQTT client
        self.catalog_url = json.load(open("settings.json"))[
            "catalog_url"
        ]  # Load catalog URL from settings

    def start(self):
        """Starts the MQTT client and connects to the broker."""
        self.client.start()
        time.sleep(1)

    def notify(self, topic, msg):
        """Handles incoming MQTT messages to control the LED."""
        message = json.loads(msg)
        print(topic, message)
        if (
            message["message"].lower() == "on"
        ):  # Check if the message is to turn the LED on
            self.led.on()
        elif (
            message["message"].lower() == "off"
        ):  # Check if the message is to turn the LED off
            self.led.off()

    def subscribe(self, topic, QoS):
        """Subscribes to a specific MQTT topic."""
        self.client.subscribe(topic, QoS)

    def stop(self):
        """Stops the MQTT client and turns off the LED."""
        self.client.stop()

    def heartbeat(self):
        """Sends a heartbeat signal to the catalog service every 60 seconds."""
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
                response = requests.post(
                    url, headers=headers, data=json.dumps(payload)
                )  # Send heartbeat to catalog service
                if response.status_code == 200:  # Check if the heartbeat was successful
                    print("Heartbeat sent successfully")
                else:
                    print("Failed to send heartbeat")
            except requests.exceptions.RequestException as e:
                print(f"Error sending heartbeat: {e}")
            time.sleep(60)  # Wait for 60 seconds before sending the next heartbeat


def signal_handler(sig, frame):
    """Handles Ctrl+C to stop the LEDs cleanly"""
    print("\nStopping MQTT LED service...")
    redled.stop()
    greenled.stop()
    yellowled.stop()


if __name__ == "__main__":
    settings = json.load(
        open("mqtt_settings.json")
    )  # Load MQTT settings from a JSON file
    redled = Led(
        21, "RedLED", settings["broker"], settings["port"], 3
    )  # Initialize Red LED
    greenled = Led(
        26, "GreenLED", settings["broker"], settings["port"], 4
    )  # Initialize Green LED
    yellowled = Led(
        16, "YellowLED", settings["broker"], settings["port"], 5
    )  # Initialize Yellow LED
    redled.start()  # Start Red LED
    greenled.start()  # Start Green LED
    yellowled.start()  # Start Yellow LED

    red_heartbeat_thread = threading.Thread(
        target=redled.heartbeat
    )  # Heartbeat for Red LED
    red_heartbeat_thread.daemon = (
        True  # The thread will terminate when the program ends
    )
    red_heartbeat_thread.start()  # Start heartbeat for Red LED

    green_heartbeat_thread = threading.Thread(
        target=greenled.heartbeat
    )  # Heartbeat for Green LED
    green_heartbeat_thread.daemon = (
        True  # The thread will terminate when the program ends
    )
    green_heartbeat_thread.start()  # Start heartbeat for Green LED

    yellow_heartbeat_thread = threading.Thread(
        target=yellowled.heartbeat
    )  # Heartbeat for Yellow LED
    yellow_heartbeat_thread.daemon = (
        True  # The thread will terminate when the program ends
    )
    yellow_heartbeat_thread.start()  # Start heartbeat for Yellow LED

    redled.subscribe(
        settings["baseTopic"] + "/kennel1/leds/redled", 0
    )  # Subscribe Red LED (for now only kennel1)
    greenled.subscribe(
        settings["baseTopic"] + "/kennel1/leds/greenled", 0
    )  # Subscribe Green LED (for now only kennel1)
    yellowled.subscribe(
        settings["baseTopic"] + "/kennel1/leds/yellowled", 0
    )  # Subscribe Yellow LED (for now only kennel1)
    # Wait for keyboardinterrupt
    signal.signal(signal.SIGINT, signal_handler)

    # Keep the script running without a while loop
    signal.pause()
