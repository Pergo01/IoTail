import json
from Libraries import PublisherSubscriber
import time
import signal
import requests
import threading


class DataAnalysis:
    def __init__(self, clientID, broker, port):
        self.clientID = clientID
        self.broker = broker
        self.port = port
        self.client = PublisherSubscriber(clientID, broker, port, self)
        self.settings = json.load(open("settings.json"))
        self.catalog_url = self.settings["catalog_url"]
        time.sleep(10)  # WAITING FOR RESERVATION_MANAGER TO START
        self.get_data()

    def get_data(self):
        self.get_breeds()
        self.get_dogs()
        self.get_reservations()

    def get_breeds(self):
        headers = {
            "Authorization": f"Bearer data_analysis",
            "Content-Type": "application/json",
        }
        response = requests.get(
            self.settings["catalog_url"] + "/breeds", headers=headers
        )
        if response.status_code != 200:
            raise Exception("Failed to get breeds")
        self.breeds = response.json()

    def get_dogs(self):
        headers = {
            "Authorization": f"Bearer data_analysis",
            "Content-Type": "application/json",
        }
        response = requests.get(
            self.settings["catalog_url"] + "/users", headers=headers
        )
        if response.status_code != 200:
            raise Exception("Failed to get dogs")
        self.dogs = []
        for user in response.json():
            if user["Dogs"]:
                self.dogs.extend(user["Dogs"])

    def get_reservations(self):
        headers = {
            "Authorization": f"Bearer data_analysis",
            "Content-Type": "application/json",
        }
        response = requests.get(
            "http://reservation_manager:8083/status", headers=headers
        )
        if response.status_code != 200:
            raise Exception("Failed to get reservations")
        self.reservations = response.json()

    # self.broker_info = self.get_broker_info()
    """
    def get_broker_info(self):
        response = requests.get(f"{self.catalog_url}/broker")
        return json.loads(response.text)
    """

    def start(self):
        self.client.start()
        time.sleep(1)

    def notify(self, topic, msg):
        data = json.loads(msg)
        self.analyze_data(data)

    def subscribe(self, topic, QoS):
        self.client.subscribe(topic, QoS)

    def analyze_data(self, data):
        # Implement data analysis logic here
        if data["temperature"] > 30 or data["temperature"] < 15:
            self.publish("Temperature out of range")
        if data["humidity"] > 80 or data["humidity"] < 20:
            self.publish("Humidity out of range")
        if data["motion"] == 1:
            self.publish("Dog is agitated")

    def publish(self, topic, message, QoS):
        alert = {"timestamp": time.time(), "message": message}
        self.client.publish(topic, alert, QoS)

    def stop(self):
        self.client.stop()

    def refresh(self):
        while True:
            self.get_data()
            time.sleep(60)


def signal_handler(sig, frame):
    """Handles Ctrl+C to stop the LEDs cleanly"""
    print("\nStopping MQTT Data Analysis service...")
    analysis.stop()


if __name__ == "__main__":
    settings = json.load(open("mqtt_settings.json"))
    analysis = DataAnalysis("DataAnalysis", settings["broker"], settings["port"])

    refresh_thread = threading.Thread(target=analysis.refresh)
    refresh_thread.daemon = True  # Il thread terminerà quando il programma termina
    refresh_thread.start()

    analysis.start()
    analysis.subscribe(settings["baseTopic"] + "/kennel1/sensors", 0)
    # Wait for keyboardinterrupt
    signal.signal(signal.SIGINT, signal_handler)

    # Keep the script running without a while loop
    signal.pause()
