import json
from Libraries import PublisherSubscriber
import time
import signal
import requests
import threading
import firebase_admin
from firebase_admin import credentials, messaging, exceptions


class DataAnalysis:
    def __init__(self, clientID, broker, port, baseTopic):
        self.clientID = clientID
        self.broker = broker
        self.port = port
        self.baseTopic = baseTopic
        self.client = PublisherSubscriber(clientID, broker, port, self)
        self.settings = json.load(open("settings.json"))
        self.catalog_url = self.settings["catalog_url"]
        if not firebase_admin._apps:  # Ensures Firebase is initialized only once
            cred = credentials.Certificate("firebase_account_key.json")
            firebase_admin.initialize_app(cred)
        time.sleep(10)  # WAITING FOR RESERVATION_MANAGER TO START

        # Dictionary to track the last alert sent for each kennel and alert type
        self.last_alerts = {}

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
                self.dogs.extend(
                    [
                        {**dog, "FirebaseTokens": user["FirebaseTokens"]}
                        for dog in user["Dogs"]
                    ]
                )

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

    def start(self):
        self.client.start()
        time.sleep(1)

    def notify(self, topic, msg):
        data = json.loads(msg)
        # Pass topic and data to get the kennel ID, sensor type and dog info
        self.analyze_data(topic, data)

    def subscribe(self, topic, QoS):
        self.client.subscribe(topic, QoS)

    def should_send_alert(self, kennel_id, alert_type):
        # Check if enough time has passed since the last alert.
        now = time.time()
        key = (kennel_id, alert_type)
        last_sent = self.last_alerts.get(key, 0)
        if now - last_sent >= 300:  # 5 minutes = 300 seconds
            self.last_alerts[key] = now
            return True
        return False

    def analyze_data(self, topic, data):
        # Extract the kennel ID and sensor type from the topic
        try:
            parts = topic.split("/")
            kennel_id = int(parts[1].replace("kennel", ""))
            sensor_type = parts[-1].lower()  # e.g., "temp_humid" or "motion"
        except Exception as e:
            print("Error in topic analysis:", topic)
            return

        # Retrieve the reservation associated with the kennel
        reservation = next(
            (r for r in self.reservations if int(r["kennelID"]) == kennel_id), None
        )
        if not reservation or not reservation["active"]:
            return

        dog_id = reservation["dogID"]
        dog_info = next(
            (dog for dog in self.dogs if str(dog["DogID"]) == str(dog_id)), None
        )
        if not dog_info:
            print("No dog found for dog id", dog_id)
            return

        # If the message comes from the motion sensor
        if sensor_type == "motion":
            readings = {
                item.get("n", "motion"): item.get("v", False)
                for item in data.get("e", [])
            }
            motion = readings.get("motion", False)
            if motion and self.should_send_alert(kennel_id, "motion"):
                self.publish(
                    self.baseTopic + f"/kennel{kennel_id}/alert/motion",
                    "Dog is agitated",
                    0,
                )
                for token in dog_info["FirebaseTokens"]:
                    message = messaging.Message(
                        notification=messaging.Notification(
                            title="Dog is agitated",
                            body="Your dog is moving too much. Check if everything is ok.",
                        ),
                        token=token,
                    )
                    try:
                        response = messaging.send(message)
                        print(
                            f"Message sent successfully for kennel {kennel_id}: {response}"
                        )
                    except exceptions.FirebaseError as e:
                        print(f"Error sending message: {e}")
            return

        # If the message comes from the temperature/humidity sensor
        breed_id = dog_info.get("BreedID", 0)
        if breed_id != 0:
            breed_info = next(
                (breed for breed in self.catalog if breed["BreedID"] == breed_id), None
            )
            if breed_info is None:
                breed_info = {
                    "MinIdealTemperature": 15,
                    "MaxIdealTemperature": 30,
                    "MinIdealHumidity": 20,
                    "MaxIdealHumidity": 80,
                }
        else:
            breed_info = {
                "MinIdealTemperature": dog_info.get("MinIdealTemperature", 15),
                "MaxIdealTemperature": dog_info.get("MaxIdealTemperature", 30),
                "MinIdealHumidity": dog_info.get("MinIdealHumidity", 20),
                "MaxIdealHumidity": dog_info.get("MaxIdealHumidity", 80),
            }

        readings = {
            item.get("n", "temp_humid"): item.get("v", False)
            for item in data.get("e", [])
        }
        temperature = readings.get("temperature")
        humidity = readings.get("humidity")
        if temperature is None or humidity is None:
            print("Incomplete sensor data:", data)
            return

        # Temperature check
        if (
            temperature > breed_info["MaxIdealTemperature"]
            or temperature < breed_info["MinIdealTemperature"]
        ) and self.should_send_alert(kennel_id, "temperature"):
            self.publish(
                self.baseTopic + f"/kennel{kennel_id}/alert/temperature",
                f"Temperature {temperature} is outside ideal range ({breed_info['MinIdealTemperature']}ºC-{breed_info['MaxIdealTemperature']}ºC)",
                0,
            )
            for token in dog_info["FirebaseTokens"]:
                message = messaging.Message(
                    notification=messaging.Notification(
                        title="Temperature not ideal",
                        body=f"Temperature {temperature} is outside ideal range ({breed_info['MinIdealTemperature']}ºC-{breed_info['MaxIdealTemperature']}ºC)",
                    ),
                    token=token,
                )
                try:
                    response = messaging.send(message)
                    print(
                        f"Message sent successfully for kennel {kennel_id}: {response}"
                    )
                except exceptions.FirebaseError as e:
                    print(f"Error sending message: {e}")

        # Humidity check
        if (
            humidity > breed_info["MaxIdealHumidity"]
            or humidity < breed_info["MinIdealHumidity"]
        ) and self.should_send_alert(kennel_id, "humidity"):
            self.publish(
                self.baseTopic + f"/kennel{kennel_id}/alert/humidity",
                f"Humidity {humidity} is outside ideal range ({breed_info['MinIdealHumidity']}%-{breed_info['MaxIdealHumidity']}%)",
                0,
            )
            for token in dog_info["FirebaseTokens"]:
                message = messaging.Message(
                    notification=messaging.Notification(
                        title="Humidity not ideal",
                        body=f"Humidity {humidity} is outside ideal range ({breed_info['MinIdealHumidity']}%-{breed_info['MaxIdealHumidity']}%)",
                    ),
                    token=token,
                )
                try:
                    response = messaging.send(message)
                    print(
                        f"Message sent successfully for kennel {kennel_id}: {response}"
                    )
                except exceptions.FirebaseError as e:
                    print(f"Error sending message: {e}")

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
    # Handles Ctrl+C signals to gracefully stop data_analysis process
    print("\nStopping MQTT Data Analysis service...")
    analysis.stop()


if __name__ == "__main__":
    settings = json.load(open("mqtt_settings.json"))
    analysis = DataAnalysis(
        "DataAnalysis", settings["broker"], settings["port"], settings["baseTopic"]
    )

    refresh_thread = threading.Thread(target=analysis.refresh)
    refresh_thread.daemon = True  # The thread will terminate when the program ends
    refresh_thread.start()

    analysis.start()
    # Subscription to topics for all types of sensors from all kennels
    analysis.subscribe(settings["baseTopic"] + "/+/sensors/+", 0)
    # Waits for keyboard interruption
    signal.signal(signal.SIGINT, signal_handler)

    # Keeps the program running
    signal.pause()
