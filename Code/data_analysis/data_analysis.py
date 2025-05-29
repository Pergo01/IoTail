import json
from Libraries import PublisherSubscriber
import time
import signal
import requests
import threading
import firebase_admin
from firebase_admin import credentials, messaging, exceptions


class DataAnalysis:
    def __init__(self, clientID, broker, port, baseTopic, serviceID):
        self.clientID = clientID
        self.serviceID = serviceID
        self.broker = broker
        self.port = port
        self.baseTopic = baseTopic
        self.client = PublisherSubscriber(
            clientID, broker, port, self
        )  # Initialize the MQTT client
        self.settings = json.load(open("settings.json"))  # Load settings from JSON file
        self.catalog_url = self.settings["catalog_url"]  # Catalog URL from settings
        if not firebase_admin._apps:  # Ensures Firebase is initialized only once
            cred = credentials.Certificate("firebase_account_key.json")
            firebase_admin.initialize_app(cred)  # Initialize Firebase Admin SDK
        time.sleep(10)  # WAITING FOR RESERVATION_MANAGER TO START

        self.last_alerts = (
            {}
        )  # Dictionary to track the last alert sent for each kennel and alert type
        self.averages = {}  # Dictionary to track HVAC status for each kennel
        self.hvac_status = (
            {}
        )  # Dictionary to track HVAC status. Format: {kennelX: {"heating": bool, "cooling": bool, "humidifier": bool, "dehumidifier": bool}}

    def get_data(self):
        """Fetches data from the catalog and reservation manager services to get breeds, dogs, and reservations."""
        self.get_breeds()
        self.get_dogs()
        self.get_reservations()

    def get_breeds(self):
        """Fetches the list of breeds from the catalog service."""
        headers = {
            "Authorization": f"Bearer data_analysis",
            "Content-Type": "application/json",
        }
        response = requests.get(
            self.settings["catalog_url"] + "/breeds", headers=headers
        )  # Make a GET request to the catalog service to fetch breeds
        if response.status_code != 200:  # Check if the request was not successful
            raise Exception("Failed to get breeds")
        self.breeds = response.json()  # Store the list of breeds

    def get_dogs(self):
        headers = {
            "Authorization": f"Bearer data_analysis",
            "Content-Type": "application/json",
        }
        response = requests.get(
            self.settings["catalog_url"] + "/users", headers=headers
        )  # Make a GET request to the catalog service to fetch users and their dogs
        if response.status_code != 200:  # Check if the request was not successful
            raise Exception("Failed to get dogs")
        self.dogs = [
            dog for user in response.json() for dog in user["Dogs"] if user["Dogs"]
        ]  # Flatten the list of dogs from all users

    def get_reservations(self):
        headers = {
            "Authorization": f"Bearer data_analysis",
            "Content-Type": "application/json",
        }
        response = requests.get(
            "http://reservation_manager:8083/status", headers=headers
        )  # Make a GET request to the reservation manager service to fetch reservations
        if response.status_code != 200:  # Check if the request was not successful
            raise Exception("Failed to get reservations")
        self.reservations = response.json()  # Store the list of reservations

    def start(self):
        """Starts the MQTT client and subscribes to the necessary topics."""
        self.client.start()  # Start the MQTT client
        time.sleep(1)

    def notify(self, topic, msg):
        """Callback function to handle incoming MQTT messages."""
        data = json.loads(msg)
        # Pass topic and data to get the kennel ID, sensor type and dog info
        self.analyze_data(topic, data)  # Analyze the data received from the MQTT topic

    def subscribe(self, topic, QoS):
        """Subscribes to a specific MQTT topic."""
        self.client.subscribe(topic, QoS)

    def should_send_alert(self, kennel_id, alert_type):
        """Checks if an alert should be sent based on the last alert time."""
        now = time.time()
        key = (kennel_id, alert_type)
        last_sent = self.last_alerts.get(key, 0)
        if now - last_sent >= 300:  # 5 minutes = 300 seconds
            self.last_alerts[key] = now  # Update the last sent time
            return True
        return False

    def analyze_data(self, topic, data):
        """Analyzes the data received from the MQTT topic and controls HVAC systems accordingly."""
        try:  # Extract the kennel ID and sensor type from the topic
            parts = topic.split("/")
            kennel_id = int(parts[1].replace("kennel", ""))
            sensor_type = parts[-1].lower()  # e.g., "temp_humid" or "motion"
        except Exception as e:
            print("Error in topic analysis:", topic)
            return

        reservation = next(
            (r for r in self.reservations if int(r["kennelID"]) == kennel_id), None
        )  # Find the reservation for the given kennel ID
        if (
            not reservation or not reservation["active"]
        ):  # Check if the reservation is not present or not active
            return

        dog_id = reservation["dogID"]
        dog_info = next(
            (dog for dog in self.dogs if str(dog["DogID"]) == str(dog_id)), None
        )  # Find the dog information for the given dog ID
        if not dog_info:  # If no dog information is found, log an error and return
            print("No dog found for dog id", dog_id)
            return

        # Get dog's name for personalized messages
        dog_name = dog_info.get("Name", "Your dog")

        # If the message comes from the motion sensor
        if sensor_type == "motion":
            readings = {
                item.get("n", "motion"): item.get("v", False)
                for item in data.get("e", [])
            }  # Extract motion readings from the data
            motion = readings.get("motion", False)
            if motion and self.should_send_alert(
                kennel_id, "motion"
            ):  # If motion is detected and an alert was not sent recently
                self.publish(
                    self.baseTopic + f"/kennel{kennel_id}/alert/motion",
                    f"{dog_name} is agitated",
                    0,
                )  # Publish an alert message to the MQTT topic
                for token in reservation[
                    "firebaseTokens"
                ]:  # Send a notification to all Firebase tokens associated with the reservation
                    message = messaging.Message(
                        notification=messaging.Notification(
                            title=f"{dog_name} is agitated",
                            body=f"{dog_name} is moving too much. Check if everything is ok.",
                        ),
                        token=token,
                    )  # Create a Firebase message with the notification
                    try:
                        response = messaging.send(
                            message
                        )  # Send the message via Firebase
                        print(
                            f"Message sent successfully for kennel {kennel_id}: {response}"
                        )
                    except exceptions.FirebaseError as e:
                        print(f"Error sending message: {e}")
            return
        # If the message comes from the temperature/humidity sensor
        breed_id = dog_info.get("BreedID", 0)
        if breed_id != 0:  # If the dog has a breed ID, fetch the breed information
            breed_info = next(
                (breed for breed in self.breeds if breed["BreedID"] == breed_id), None
            )  # Find the breed information for the given breed ID
            if (
                breed_info is None
            ):  # If no breed information is found, use default values
                breed_info = {
                    "MinIdealTemperature": 15,
                    "MaxIdealTemperature": 30,
                    "MinIdealHumidity": 20,
                    "MaxIdealHumidity": 80,
                }
        else:  # If the dog has mixed breed, use values from the dog itself
            breed_info = {
                "MinIdealTemperature": dog_info.get("MinIdealTemperature", 15),
                "MaxIdealTemperature": dog_info.get("MaxIdealTemperature", 30),
                "MinIdealHumidity": dog_info.get("MinIdealHumidity", 20),
                "MaxIdealHumidity": dog_info.get("MaxIdealHumidity", 80),
            }

        readings = {
            item.get("n", "temp_humid"): item.get("v", False)
            for item in data.get("e", [])
        }  # Extract temperature and humidity readings from the data
        temperature = readings.get("temperature")
        humidity = readings.get("humidity")
        if (
            temperature is None or humidity is None
        ):  # Check if both temperature and humidity readings are present
            print("Incomplete sensor data:", data)
            return

        # Initialize HVAC status for this kennel if not already present
        kennel_key = f"kennel{kennel_id}"
        if kennel_key not in self.hvac_status:
            self.hvac_status[kennel_key] = {
                "heating": False,
                "cooling": False,
                "humidifier": False,
                "dehumidifier": False,
            }

        # Humidity check
        if (
            humidity > breed_info["MaxIdealHumidity"]
        ):  # If humidity is above the ideal range
            # Activate dehumidifier if not already active
            if not self.hvac_status[kennel_key]["dehumidifier"]:
                self.hvac_status[kennel_key]["dehumidifier"] = True
                self.publish(
                    self.baseTopic + f"/kennel{kennel_id}/hvac/dehumidifier",
                    json.dumps({"command": "activate"}),
                    0,
                )
                print(f"Activated dehumidifier for kennel {kennel_id}")

            # Turn off humidifier if active
            if self.hvac_status[kennel_key]["humidifier"]:
                self.hvac_status[kennel_key]["humidifier"] = False
                self.publish(
                    self.baseTopic + f"/kennel{kennel_id}/hvac/humidifier",
                    json.dumps({"command": "deactivate"}),
                    0,
                )
                print(f"Deactivated humidifier for kennel {kennel_id}")

        elif (
            humidity < breed_info["MinIdealHumidity"]
        ):  # If humidity is below the ideal range
            # Activate humidifier if not already active
            if not self.hvac_status[kennel_key]["humidifier"]:
                self.hvac_status[kennel_key]["humidifier"] = True
                self.publish(
                    self.baseTopic + f"/kennel{kennel_id}/hvac/humidifier",
                    json.dumps({"command": "activate"}),
                    0,
                )
                print(f"Activated humidifier for kennel {kennel_id}")

            # Turn off dehumidifier if active
            if self.hvac_status[kennel_key]["dehumidifier"]:
                self.hvac_status[kennel_key]["dehumidifier"] = False
                self.publish(
                    self.baseTopic + f"/kennel{kennel_id}/hvac/dehumidifier",
                    json.dumps({"command": "deactivate"}),
                    0,
                )
                print(f"Deactivated dehumidifier for kennel {kennel_id}")

        else:
            # Turn off both humidifier and dehumidifier if values are in range
            if self.hvac_status[kennel_key]["humidifier"]:
                self.hvac_status[kennel_key]["humidifier"] = False
                self.publish(
                    self.baseTopic + f"/kennel{kennel_id}/hvac/humidifier",
                    json.dumps({"command": "deactivate"}),
                    0,
                )
                print(
                    f"Deactivated humidifier for kennel {kennel_id} - humidity in range"
                )

            if self.hvac_status[kennel_key]["dehumidifier"]:
                self.hvac_status[kennel_key]["dehumidifier"] = False
                self.publish(
                    self.baseTopic + f"/kennel{kennel_id}/hvac/dehumidifier",
                    json.dumps({"command": "deactivate"}),
                    0,
                )
                print(
                    f"Deactivated dehumidifier for kennel {kennel_id} - humidity in range"
                )

        if (
            humidity > breed_info["MaxIdealHumidity"]
            or humidity < breed_info["MinIdealHumidity"]
        ) and self.should_send_alert(
            kennel_id, "humidity"
        ):  # If humidity is outside the ideal range and an alert was not sent recently
            self.publish(
                self.baseTopic + f"/kennel{kennel_id}/alert/humidity",
                f"Humidity {humidity} is outside ideal range for {dog_name} ({breed_info['MinIdealHumidity']}%-{breed_info['MaxIdealHumidity']}%)",
                0,
            )
            for token in reservation[
                "firebaseTokens"
            ]:  # Send a notification to all Firebase tokens associated with the reservation
                message = messaging.Message(
                    notification=messaging.Notification(
                        title=f"Humidity not ideal for {dog_name}",
                        body=f"Humidity {humidity} is outside ideal range for {dog_name} ({breed_info['MinIdealHumidity']}%-{breed_info['MaxIdealHumidity']}%)",
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

        # Temperature check
        if (
            not parts[1] in self.averages.keys()
        ):  # Initialize averages for this kennel if not already present
            self.averages[parts[1]] = []

        # Calculate heat index (apparent temperature) https://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml
        # Convert temperature to Fahrenheit for the standard formula
        temp_f = (temperature * 9 / 5) + 32
        rh = humidity  # relative humidity in percentage

        # First calculate the simpler formula
        simple_hi = 0.5 * (temp_f + 61.0 + ((temp_f - 68.0) * 1.2) + (rh * 0.094))

        # Average with the temperature
        hi_f = (simple_hi + temp_f) / 2

        # If HI >= 80°F, use the full regression equation
        if hi_f >= 80:
            # Full Rothfusz regression equation
            hi_f = -42.379 + 2.04901523 * temp_f + 10.14333127 * rh
            hi_f -= 0.22475541 * temp_f * rh
            hi_f -= 0.00683783 * temp_f**2
            hi_f -= 0.05481717 * rh**2
            hi_f += 0.00122874 * temp_f**2 * rh
            hi_f += 0.00085282 * temp_f * rh**2
            hi_f -= 0.00000199 * temp_f**2 * rh**2

            # Apply adjustments if needed
            # Adjustment for low humidity
            if rh < 13 and temp_f >= 80 and temp_f <= 112:
                adjustment = ((13 - rh) / 4) * ((17 - abs(temp_f - 95)) / 17) ** 0.5
                hi_f -= adjustment

            # Adjustment for high humidity
            if rh > 85 and temp_f >= 80 and temp_f <= 87:
                adjustment = ((rh - 85) / 10) * ((87 - temp_f) / 5)
                hi_f += adjustment

        # Convert back to Celsius
        apparent_temp = (hi_f - 32) * 5 / 9

        self.averages[parts[1]].append(
            apparent_temp
        )  # Append the apparent temperature to the averages list
        if len(self.averages[parts[1]]) < 30:
            return  # Not enough data to calculate the average over 30 seconds
        if len(self.averages[parts[1]]) > 30:
            self.averages[parts[1]].pop(
                0
            )  # Remove the oldest reading to keep the list size at 30
        avg = (
            sum(self.averages[parts[1]]) / 30
        )  # Calculate the average apparent temperature over the last 30 seconds

        # Control HVAC based on average temperature
        if (
            avg > breed_info["MaxIdealTemperature"]
        ):  # If average temperature is above the ideal range
            # Activate cooling if not already active
            if not self.hvac_status[kennel_key]["cooling"]:
                self.hvac_status[kennel_key]["cooling"] = True
                self.publish(
                    self.baseTopic + f"/kennel{kennel_id}/hvac/cooling",
                    json.dumps({"command": "activate"}),
                    0,
                )
                print(f"Activated cooling for kennel {kennel_id}")

            # Turn off heating if active
            if self.hvac_status[kennel_key]["heating"]:
                self.hvac_status[kennel_key]["heating"] = False
                self.publish(
                    self.baseTopic + f"/kennel{kennel_id}/hvac/heating",
                    json.dumps({"command": "deactivate"}),
                    0,
                )
                print(f"Deactivated heating for kennel {kennel_id}")

        elif (
            avg < breed_info["MinIdealTemperature"]
        ):  # If average temperature is below the ideal range
            # Activate heating if not already active
            if not self.hvac_status[kennel_key]["heating"]:
                self.hvac_status[kennel_key]["heating"] = True
                self.publish(
                    self.baseTopic + f"/kennel{kennel_id}/hvac/heating",
                    json.dumps({"command": "activate"}),
                    0,
                )
                print(f"Activated heating for kennel {kennel_id}")

            # Turn off cooling if active
            if self.hvac_status[kennel_key]["cooling"]:
                self.hvac_status[kennel_key]["cooling"] = False
                self.publish(
                    self.baseTopic + f"/kennel{kennel_id}/hvac/cooling",
                    json.dumps({"command": "deactivate"}),
                    0,
                )
                print(f"Deactivated cooling for kennel {kennel_id}")

        else:
            # Turn off both heating and cooling if values are in range
            if self.hvac_status[kennel_key]["heating"]:
                self.hvac_status[kennel_key]["heating"] = False
                self.publish(
                    self.baseTopic + f"/kennel{kennel_id}/hvac/heating",
                    json.dumps({"command": "deactivate"}),
                    0,
                )
                print(
                    f"Deactivated heating for kennel {kennel_id} - temperature in range"
                )

            if self.hvac_status[kennel_key]["cooling"]:
                self.hvac_status[kennel_key]["cooling"] = False
                self.publish(
                    self.baseTopic + f"/kennel{kennel_id}/hvac/cooling",
                    json.dumps({"command": "deactivate"}),
                    0,
                )
                print(
                    f"Deactivated cooling for kennel {kennel_id} - temperature in range"
                )

        if (
            avg > breed_info["MaxIdealTemperature"]
            or avg < breed_info["MinIdealTemperature"]
        ) and self.should_send_alert(
            kennel_id, "temperature"
        ):  # If average temperature is outside the ideal range and an alert was not sent recently
            self.publish(
                self.baseTopic + f"/kennel{kennel_id}/alert/temperature",
                f"Apparent Temperature {avg:.1f} is outside ideal range for {dog_name} ({breed_info['MinIdealTemperature']}ºC-{breed_info['MaxIdealTemperature']}ºC)",
                0,
            )
            for token in reservation[
                "firebaseTokens"
            ]:  # Send a notification to all Firebase tokens associated with the reservation
                message = messaging.Message(
                    notification=messaging.Notification(
                        title=f"Apparent Temperature not ideal for {dog_name}",
                        body=f"Apparent Temperature {avg:.1f} is outside ideal range for {dog_name} ({breed_info['MinIdealTemperature']}ºC-{breed_info['MaxIdealTemperature']}ºC)",
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
        """Publishes a message to a specific MQTT topic."""
        alert = {"timestamp": time.time(), "message": message}
        self.client.publish(topic, alert, QoS)

    def stop(self):
        """Stops the MQTT client and performs any necessary cleanup."""
        self.client.stop()

    def refresh(self):
        """Periodically fetches data and sends heartbeats to the catalog service."""
        while True:
            self.get_data()
            self.heartbeat()
            time.sleep(60)

    def heartbeat(self):
        """Sends a heartbeat signal to the catalog service to indicate that the data_analysis service is running."""
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": "Bearer data_analysis",
            }
            url = self.catalog_url + "/heartbeat"
            payload = {
                "category": "service",
                "serviceID": self.serviceID,
            }
            response = requests.post(
                url, headers=headers, data=json.dumps(payload)
            )  # Make a POST request to the catalog service to send a heartbeat
            if response.status_code == 200:  # Check if the request was successful
                print("Heartbeat sent successfully")
            else:
                print("Failed to send heartbeat")
        except requests.exceptions.RequestException as e:
            print(f"Error sending heartbeat: {e}")


def signal_handler(sig, frame):
    """Handles keyboard interruption to stop the MQTT client gracefully."""
    print("\nStopping MQTT Data Analysis service...")
    analysis.stop()


if __name__ == "__main__":
    settings = json.load(open("mqtt_settings.json"))  # Load MQTT settings
    analysis = DataAnalysis(
        "DataAnalysis", settings["broker"], settings["port"], settings["baseTopic"], 2
    )  # Instantiate the DataAnalysis class

    refresh_thread = threading.Thread(
        target=analysis.refresh
    )  # Create a thread for the refresh function, which fetches data and sends heartbeats
    refresh_thread.daemon = True  # The thread will terminate when the program ends
    refresh_thread.start()  # Start the refresh thread

    analysis.start()  # Start the MQTT client
    # Subscription to topics for all types of sensors from all kennels
    analysis.subscribe(settings["baseTopic"] + "/+/sensors/+", 0)
    # Waits for keyboard interruption
    signal.signal(signal.SIGINT, signal_handler)

    # Keeps the program running
    signal.pause()
