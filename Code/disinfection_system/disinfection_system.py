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
        self.client = PublisherSubscriber(
            clientID, broker, port, self
        )  # Initialize MQTT client
        self.catalog_url = json.load(open("settings.json"))[
            "catalog_url"
        ]  # Load catalog URL from settings

    def start(self):
        """Starts the MQTT client and connects to the broker."""
        self.client.start()
        time.sleep(1)

    def notify(self, topic, msg):
        """Handles incoming MQTT messages."""
        data = json.loads(msg)
        kennel_id = topic.split("/")[1]
        if data["message"] == "on":  # Check if the message is to disinfect the kennel
            self.disinfect_kennel(
                kennel_id
            )  # Start disinfection process for the specified kennel

    def subscribe(self, topic, QoS):
        """Subscribes to a specific MQTT topic."""
        self.client.subscribe(topic, QoS)

    def publish(self, topic, message, QoS):
        """Publishes a message to a specific MQTT topic."""
        self.client.publish(topic, message, QoS)

    def stop(self):
        """Stops the MQTT client."""
        self.client.stop()

    def disinfect_kennel(self, kennel_id):
        """Simulates the disinfection process for a specific kennel."""
        print(f"Starting disinfection process for kennel {kennel_id}")
        time.sleep(10)  # Simulate disinfection process
        print(f"Disinfection complete for kennel {kennel_id}")
        self.publish(
            f"{self.baseTopic}/{kennel_id}/status",
            {"message": "disinfected"},
            2,
        )  # Publish disinfection status to the kennel's status topic

    def heartbeat(self):
        """Sends a heartbeat signal to the catalog service to indicate that the disinfection system is active."""
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
                response = requests.post(
                    url, headers=headers, data=json.dumps(payload)
                )  # Send heartbeat to catalog service
                if response.status_code == 200:  # Heartbeat sent successfully
                    print("Heartbeat sent successfully")
                else:
                    print("Failed to send heartbeat")
            except requests.exceptions.RequestException as e:
                print(f"Error sending heartbeat: {e}")
            time.sleep(60)


def signal_handler(sig, frame):
    """Handles keyboard interruption to stop the disinfection system gracefully."""
    print("\nStopping MQTT Disinfection System service...")
    disinfection_system.stop()


if __name__ == "__main__":
    settings = json.load(open("mqtt_settings.json"))  # Load MQTT settings
    disinfection_system = DisinfectionSystem(
        "DisinfectionSystem",
        settings["broker"],
        settings["port"],
        settings["baseTopic"],
        3,
    )  # Initialize Disinfection System
    disinfection_system.start()  # Start the MQTT client

    heartbeat_thread = threading.Thread(
        target=disinfection_system.heartbeat
    )  # Heartbeat thread for disinfection system
    heartbeat_thread.daemon = True  # The thread will terminate when the program ends
    heartbeat_thread.start()  # Start heartbeat for disinfection system

    disinfection_system.subscribe(
        settings["baseTopic"] + "/+/disinfect", 2
    )  # Subscribe to disinfection topics
    # Waits for keyboard interruption
    signal.signal(signal.SIGINT, signal_handler)

    # Keeps the program running
    signal.pause()
