import json
import requests
from Libraries import Subscriber
import time
import signal
import threading


class ThingspeakAdaptor:
    def __init__(self, clientID, broker, port, serviceID):
        with open("settings.json") as f:
            self.settings = json.load(f)  # Load settings from a JSON file

        self.clientID = clientID
        self.serviceID = serviceID
        self.broker = broker
        self.port = port
        self.client = Subscriber(
            clientID, broker, port, self
        )  # Initialize the MQTT client

        self.catalog_url = self.settings["catalog_url"]  # URL of the catalog service
        self.thingspeak_write_api_key = self.settings[
            "thingspeak_write_api_key"
        ]  # API key for writing to Thingspeak
        self.thingspeak_read_api_key = self.settings[
            "thingspeak_read_api_key"
        ]  # API key for reading from Thingspeak
        self.thingspeak_url = f"https://api.thingspeak.com/update?api_key={self.thingspeak_write_api_key}"  # URL for updating Thingspeak with the write API key

    def start(self):
        """Starts the MQTT client and connects to the broker."""
        self.client.start()
        time.sleep(1)

    def subscribe(self, topic, QoS):
        """Subscribes to a given MQTT topic with the specified QoS."""
        self.client.subscribe(topic, QoS)

    def notify(self, topic, msg):
        """Handles incoming messages from subscribed topics."""
        kennelID = int(
            topic.split("/")[1].replace("kennel", "")
        )  # Extracts kennelID from the topic
        try:
            data = json.loads(msg)
            measurements = {}
            if "e" in data:  # Checks if the message contains sensor data
                measurements["kennelID"] = kennelID
                for entry in data["e"]:  # Iterates through the sensor data entries
                    if entry["n"] == "temperature":
                        measurements["temperature"] = entry["v"]
                    elif entry["n"] == "humidity":
                        measurements["humidity"] = entry["v"]
                    elif entry["n"] == "motion":
                        measurements["motion"] = 1 if entry["v"] else 0

                self.send_to_thingspeak(
                    measurements
                )  # Sends the measurements to Thingspeak
        except json.JSONDecodeError:
            print(f"Failed to parse message: {msg.payload.decode()}")

    def send_to_thingspeak(self, measurements):
        payload = {
            "field1": measurements.get("temperature", None),
            "field2": measurements.get("humidity", None),
            "field3": measurements.get("motion", None),
            "field4": measurements.get("kennelID", None),
        }

        # Sends only non-None values to Thingspeak
        payload = {k: v for k, v in payload.items() if v is not None}

        if payload:  # Checks if there is data to send
            response = requests.get(
                self.thingspeak_url, params=payload
            )  # Sends the data to Thingspeak
            print(f"Sent to Thingspeak: {response.status_code}, Data: {payload}")
        else:
            print("No data to send to ThingSpeak")

    def stop(self):
        """Stops the MQTT client."""
        self.client.stop()

    def heartbeat(self):
        """Sends a heartbeat signal to the catalog service every 60 seconds."""
        while True:
            try:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer thingspeak_adaptor",
                }
                url = self.catalog_url + "/heartbeat"
                payload = {
                    "category": "service",
                    "serviceID": self.serviceID,
                }
                response = requests.post(
                    url, headers=headers, data=json.dumps(payload)
                )  # Sends heartbeat to the catalog service
                if response.status_code == 200:  # Heartbeat sent successfully
                    print("Heartbeat sent successfully")
                else:
                    print("Failed to send heartbeat")
            except requests.exceptions.RequestException as e:
                print(f"Error sending heartbeat: {e}")
            time.sleep(60)  # Waits for 60 seconds before sending the next heartbeat


def signal_handler(sig, frame):
    """Handles keyboard interruption to stop the MQTT client gracefully."""
    print("\nStopping MQTT Thingspeak adaptor service...")
    adaptor.stop()


if __name__ == "__main__":
    settings = json.load(open("mqtt_settings.json"))  # Load MQTT settings
    adaptor = ThingspeakAdaptor(
        "ThingspeakAdaptor", settings["broker"], settings["port"], 4
    )  # Initialize the ThingspeakAdaptor with settings

    adaptor.start()  # Starts the MQTT client

    heartbeat_thread = threading.Thread(
        target=adaptor.heartbeat
    )  # Create a thread for the heartbeat function
    heartbeat_thread.daemon = True  # The thread will terminate when the program ends
    heartbeat_thread.start()  # Start the heartbeat thread

    adaptor.subscribe(
        settings["baseTopic"] + "/+/sensors/#", 0
    )  # Subscribe to the sensors topic

    # Waits for keyboard interruption
    signal.signal(signal.SIGINT, signal_handler)

    # Keeps the program running
    signal.pause()
