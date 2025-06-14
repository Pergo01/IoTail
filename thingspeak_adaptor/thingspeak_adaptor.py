import json
import requests
from Libraries import Subscriber
import time
import threading
import requests
import socket
import cherrypy
import jwt
from datetime import datetime


class ThingspeakAdaptor:
    exposed = True

    def __init__(self, clientID, broker, port, serviceID):
        with open("settings.json") as f:
            self.settings = json.load(f)  # Load settings from a JSON file

        with open("secret_key.txt") as f:
            self.secret_key = f.read()  # Read the secret key from a file

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
        self.channelID = self.settings["channel_id"]  # Channel ID for Thingspeak

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

    def fetch_thingspeak_data(self, kennelID, startDate):
        """Fetches data from Thingspeak for a specific kennelID."""
        url = f"https://api.thingspeak.com/channels/{self.channelID}/feeds.json"
        params = {
            "api_key": self.thingspeak_read_api_key,
            "start": startDate,  # Start date for fetching data
        }
        response = requests.get(
            url, params=params
        )  # Makes a GET request to Thingspeak API
        if response.status_code == 200:
            data = response.json()  # Parses the JSON response
            feeds = data["feeds"]

            kennel_measurements = {
                "temperature": [],
                "humidity": [],
            }

            for feed in feeds:
                if int(feed["field4"]) == kennelID:
                    if feed["field1"] is not None:
                        try:
                            temp = float(feed["field1"])
                            kennel_measurements["temperature"].append(
                                {
                                    "timestamp": datetime.fromisoformat(
                                        feed["created_at"].replace("Z", "+00:00")
                                    ).timestamp(),
                                    "value": temp,
                                }
                            )
                        except (ValueError, TypeError):
                            print(f"Invalid temperature value: {feed['field1']}")

                    if feed["field2"] is not None:
                        try:
                            hum = float(feed["field2"])
                            kennel_measurements["humidity"].append(
                                {
                                    "timestamp": datetime.fromisoformat(
                                        feed["created_at"].replace("Z", "+00:00")
                                    ).timestamp(),
                                    "value": hum,
                                }
                            )
                        except (ValueError, TypeError):
                            print(f"Invalid humidity value: {feed['field2']}")

            return json.dumps(kennel_measurements)
        else:
            print(f"Failed to fetch data: {response.status_code}")
            raise cherrypy.HTTPError(
                response.status_code, "Failed to fetch data from Thingspeak"
            )

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

    def verify_token(self, token):
        """Verify the JWT token and return the decoded data or raise an error."""
        if token in [
            "reservation_manager",
            "data_analysis",
            "temp_humid_sensor",
            "motion_sensor",
            "led_connector",
            "camera",
            "thingspeak_adaptor",
            "disinfection_system",
        ]:  # Allow specific tokens without verification for simplicity
            return token
        try:
            decoded = jwt.decode(
                token, self.secret_key, algorithms=["HS256"]
            )  # Decode the JWT token using the secret key
            return decoded
        except (
            jwt.ExpiredSignatureError
        ):  # If the token has expired, return an HTTP error
            raise cherrypy.HTTPError(401, "Token has expired")
        except jwt.InvalidTokenError:  # If the token is invalid, return an HTTP error
            raise cherrypy.HTTPError(401, "Invalid token")

    def GET(self, *uri, **params):
        """Handles GET requests to the Thingspeak adaptor."""
        auth_header = cherrypy.request.headers.get(
            "Authorization"
        )  # Get the Authorization header from the request
        if (
            not auth_header
        ):  # If the Authorization header is not present, return an HTTP error
            raise cherrypy.HTTPError(401, "Authorization token required")
        else:
            token = auth_header.split(" ")[
                1
            ]  # Extract the token from the Authorization header
            self.verify_token(token)  # Verify the token for the route

        if uri[0] == "measurements":
            kennelID = int(
                params.get("kennelID", None)
            )  # Get the kennelID from the params
            startDate = params.get("start", None)  # Get the startDate from the params
            if (
                kennelID is None or startDate is None
            ):  # If kennelID or startDate is not provided, return an HTTP error
                raise cherrypy.HTTPError(400, "kennelID and startDate are required")
            return self.fetch_thingspeak_data(
                kennelID, startDate
            )  # Fetch data from Thingspeak
        else:  # If the URI does not match any known routes, return an HTTP error
            raise cherrypy.HTTPError(404, "Not Found")


if __name__ == "__main__":
    settings = json.load(open("mqtt_settings.json"))  # Load MQTT settings
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]  # getting the IP address of the container
    s.close()
    adaptor = ThingspeakAdaptor(
        "ThingspeakAdaptor", settings["broker"], settings["port"], 4
    )  # Initialize the ThingspeakAdaptor with settings
    conf = {
        "/": {
            "request.dispatch": cherrypy.dispatch.MethodDispatcher(),
            "tools.sessions.on": True,
            "request.show_tracebacks": False,
        }
    }  # Configuration for the CherryPy server
    cherrypy.tree.mount(
        adaptor, "/", conf
    )  # Mount the Thingspeak adaptor class to the root
    cherrypy.config.update(
        {"server.socket_host": ip}
    )  # Set the server socket host to the container's IP address
    cherrypy.config.update(
        {"server.socket_port": 8084}
    )  # Set the server socket port to 8084

    heartbeat_thread = threading.Thread(
        target=adaptor.heartbeat
    )  # Create a thread for the heartbeat function
    heartbeat_thread.daemon = True  # The thread will terminate when the program ends
    heartbeat_thread.start()  # Start the heartbeat thread

    cherrypy.engine.start()  # Start the CherryPy server
    adaptor.start()  # Starts the MQTT client
    adaptor.subscribe(
        settings["baseTopic"] + "/+/sensors/#", 0
    )  # Subscribe to the sensors topic
    cherrypy.engine.block()  # Block the main thread to keep the server running until KeyboardInterrupt
    adaptor.stop()  # Stop the MQTT client when the server is stopped
