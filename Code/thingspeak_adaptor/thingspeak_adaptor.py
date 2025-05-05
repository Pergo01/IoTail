import json
import requests
from Libraries import Subscriber
import time
import signal
import threading


class ThingspeakAdaptor:
    def __init__(self, clientID, broker, port, serviceID):
        with open("settings.json") as f:
            self.settings = json.load(f)

        self.clientID = clientID
        self.serviceID = serviceID
        self.broker = broker
        self.port = port
        self.client = Subscriber(clientID, broker, port, self)

        self.catalog_url = self.settings["catalog_url"]
        self.thingspeak_write_api_key = self.settings["thingspeak_write_api_key"]
        self.thingspeak_read_api_key = self.settings["thingspeak_read_api_key"]
        self.thingspeak_url = (
            f"https://api.thingspeak.com/update?api_key={self.thingspeak_write_api_key}"
        )

    def start(self):
        self.client.start()
        time.sleep(1)

    def subscribe(self, topic, QoS):
        self.client.subscribe(topic, QoS)

    def notify(self, topic, msg):
        kennelID = int(topic.split("/")[1].replace("kennel", ""))
        try:
            data = json.loads(msg)
            measurements = {}
            if "e" in data:
                measurements["kennelID"] = kennelID
                for entry in data["e"]:
                    if entry["n"] == "temperature":
                        measurements["temperature"] = entry["v"]
                    elif entry["n"] == "humidity":
                        measurements["humidity"] = entry["v"]
                    elif entry["n"] == "motion":
                        measurements["motion"] = 1 if entry["v"] else 0

                self.send_to_thingspeak(measurements)
        except json.JSONDecodeError:
            print(f"Failed to parse message: {msg.payload.decode()}")

    def send_to_thingspeak(self, measurements):
        payload = {
            "field1": measurements.get("temperature", None),
            "field2": measurements.get("humidity", None),
            "field3": measurements.get("motion", None),
            "field4": measurements.get("kennelID", None),
        }

        # Invia solo i campi che hanno un valore
        payload = {k: v for k, v in payload.items() if v is not None}

        if payload:
            response = requests.get(self.thingspeak_url, params=payload)
            print(f"Sent to Thingspeak: {response.status_code}, Data: {payload}")
        else:
            print("No data to send to ThingSpeak")

    def stop(self):
        self.client.stop()

    def heartbeat(self):
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
                response = requests.post(url, headers=headers, data=json.dumps(payload))
                if response.status_code == 200:
                    print("Heartbeat sent successfully")
                else:
                    print("Failed to send heartbeat")
            except requests.exceptions.RequestException as e:
                print(f"Error sending heartbeat: {e}")
            time.sleep(60)


def signal_handler(sig, frame):
    # Handles Ctrl+C signals to gracefully stop data_analysis process
    print("\nStopping MQTT Thingspeak adaptor service...")
    adaptor.stop()


if __name__ == "__main__":
    settings = json.load(open("mqtt_settings.json"))
    adaptor = ThingspeakAdaptor(
        "ThingspeakAdaptor", settings["broker"], settings["port"], 4
    )

    adaptor.start()

    heartbeat_thread = threading.Thread(target=adaptor.heartbeat)
    heartbeat_thread.daemon = True  # The thread will terminate when the program ends
    heartbeat_thread.start()

    adaptor.subscribe(settings["baseTopic"] + "/+/sensors/#", 0)

    # Waits for keyboard interruption
    signal.signal(signal.SIGINT, signal_handler)

    # Keeps the program running
    signal.pause()
