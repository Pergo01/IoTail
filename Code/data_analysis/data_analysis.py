import json
from Libraries import PublisherSubscriber
import time
import signal


class DataAnalysis:
    def __init__(self, clientID, broker, port):
        self.clientID = clientID
        self.broker = broker
        self.port = port
        self.client = PublisherSubscriber(clientID, broker, port, self)
        self.settings = json.load(open("settings.json"))
        self.catalog_url = self.settings["catalog_url"]

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


def signal_handler(sig, frame):
    """Handles Ctrl+C to stop the LEDs cleanly"""
    print("\nStopping MQTT Data Analysis service...")
    analysis.stop()


if __name__ == "__main__":
    settings = json.load(open("mqtt_settings.json"))
    analysis = DataAnalysis("DataAnalysis", settings["broker"], settings["port"])
    analysis.start()
    # Wait for keyboardinterrupt
    signal.signal(signal.SIGINT, signal_handler)

    # Keep the script running without a while loop
    signal.pause()
