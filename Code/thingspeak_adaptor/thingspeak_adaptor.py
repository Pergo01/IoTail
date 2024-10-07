import json
import requests
from Libraries import Subscriber
import time


class ThingspeakAdaptor:
    def __init__(self, clientID, broker, port):
        with open("settings.json") as f:
            self.settings = json.load(f)

        self.clientID = clientID
        self.broker = broker
        self.port = port
        self.client = Subscriber(clientID, broker, port, self)

        self.catalog_url = self.settings["catalog_url"]
        self.thingspeak_api_key = self.settings["thingspeak_api_key"]
        self.thingspeak_url = (
            f"https://api.thingspeak.com/update?api_key={self.thingspeak_api_key}"
        )

        # Dizionario per tenere traccia dei valori piÃ¹ recenti
        self.latest_values = {"temperature": None, "humidity": None, "motion": None}

    def start(self):
        self.client.start()
        time.sleep(1)

    def subscribe(self, topic, QoS):
        self.client.subscribe(topic, QoS)

    def notify(self, topic, msg):
        try:
            data = json.loads(msg)
            if "e" in data:
                for entry in data["e"]:
                    if entry["n"] == "temperature":
                        self.latest_values["temperature"] = entry["v"]
                    elif entry["n"] == "humidity":
                        self.latest_values["humidity"] = entry["v"]
                    elif entry["n"] == "motion":
                        self.latest_values["motion"] = 1 if entry["v"] else 0

                self.send_to_thingspeak()
        except json.JSONDecodeError:
            print(f"Failed to parse message: {msg.payload.decode()}")

    def send_to_thingspeak(self):
        payload = {
            "field1": self.latest_values["temperature"],
            "field2": self.latest_values["humidity"],
            "field3": self.latest_values["motion"],
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


if __name__ == "__main__":
    settings = json.load(open("mqtt_settings.json"))
    adaptor = ThingspeakAdaptor(
        "ThingspeakAdaptor", settings["broker"], settings["port"]
    )
    adaptor.start()
    adaptor.subscribe(settings["baseTopic"] + "/+/sensors/#", 0)
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            break
    adaptor.stop()
