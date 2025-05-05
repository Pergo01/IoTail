import json
import time
from Libraries import PublisherSubscriber
import signal
import requests
import threading


class DisinfectionSystem:
    def __init__(self, clientID, broker, port, baseTopic, serviceID):
        self.broker = broker
        self.port = port
        self.baseTopic = baseTopic
        self.clientID = clientID
        self.serviceID = serviceID
        self.client = PublisherSubscriber(clientID, broker, port, self)
        self.catalog_url = json.load(open("settings.json"))["catalog_url"]

    def start(self):
        self.client.start()
        time.sleep(1)

    def notify(self, topic, msg):
        data = json.loads(msg)
        kennel_id = topic.split("/")[1]
        if data["message"] == "on":
            self.disinfect_kennel(kennel_id)

    def subscribe(self, topic, QoS):
        self.client.subscribe(topic, QoS)

    def publish(self, topic, message, QoS):
        self.client.publish(topic, message, QoS)

    def stop(self):
        self.client.stop()

    def disinfect_kennel(self, kennel_id):
        print(f"Starting disinfection process for kennel {kennel_id}")
        time.sleep(10)  # Simulate disinfection process
        print(f"Disinfection complete for kennel {kennel_id}")
        self.publish(
            f"{self.baseTopic}/{kennel_id}/status",
            {"message": "disinfected"},
            2,
        )

    def heartbeat(self):
        while True:
            try:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer disinfection_system",
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
    print("\nStopping MQTT Disinfection System service...")
    disinfection_system.stop()


if __name__ == "__main__":
    settings = json.load(open("mqtt_settings.json"))
    disinfection_system = DisinfectionSystem(
        "DisinfectionSystem",
        settings["broker"],
        settings["port"],
        settings["baseTopic"],
        3,
    )
    disinfection_system.start()

    heartbeat_thread = threading.Thread(target=disinfection_system.heartbeat)
    heartbeat_thread.daemon = True  # The thread will terminate when the program ends
    heartbeat_thread.start()

    disinfection_system.subscribe(settings["baseTopic"] + "/+/disinfect", 2)
    # Waits for keyboard interruption
    signal.signal(signal.SIGINT, signal_handler)

    # Keeps the program running
    signal.pause()
