from gpiozero import MotionSensor
from Libraries import Publisher
import time
import json
import datetime
import cherrypy
import socket
import requests
import threading


class PIRSensor:
    exposed = True

    def __init__(self, clientID, broker, port, deviceID):
        self.deviceID = deviceID
        self.motion_sensor = MotionSensor(14)  # GPIO pin 14 for motion sensor
        self.broker = broker
        self.port = port
        self.client = Publisher(clientID, broker, port, self)  # Initialize MQTT client
        self.catalog_url = json.load(open("settings.json"))[
            "catalog_url"
        ]  # Load catalog URL from settings

    def start(self):
        """Starts the MQTT client and connects to the broker."""
        self.client.start()
        time.sleep(1)

    def publish(self, topic, message, QoS):
        """Publishes a message to a specific MQTT topic."""
        self.client.publish(topic, message, QoS)

    def stop(self):
        """Stops the MQTT client."""
        self.client.stop()

    def GET(self):
        return json.dumps(
            {
                "bn": "MotionSensor",
                "e": [
                    {
                        "n": "motion",
                        "u": "bool",
                        "t": datetime.datetime.now().timestamp(),
                        "v": self.motion_sensor.motion_detected,
                    }
                ],
            }
        )  # Returns the current motion status in JSON format

    def heartbeat(self):
        """Sends a heartbeat signal to the catalog service every 60 seconds."""
        while True:
            try:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer motion_sensor",
                }
                url = self.catalog_url + "/heartbeat"
                payload = {
                    "category": "sensor",
                    "deviceID": self.deviceID,
                }
                response = requests.post(
                    url, headers=headers, data=json.dumps(payload)
                )  # Send heartbeat
                if response.status_code == 200:  # Check if the heartbeat was successful
                    print("Heartbeat sent successfully")
                else:
                    print("Failed to send heartbeat")
            except requests.exceptions.RequestException as e:
                print(f"Error sending heartbeat: {e}")
            time.sleep(60)  # Wait for 60 seconds before sending the next heartbeat


if __name__ == "__main__":
    settings = json.load(open("mqtt_settings.json"))  # Load MQTT settings
    motion_sensor = PIRSensor(
        "MotionSensor", settings["broker"], settings["port"], 2
    )  # Initialize PIR sensor with clientID, broker, port, and deviceID
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]  # Get the local IP address
    s.close()
    motion_sensor.start()  # Start the MQTT client
    conf = {
        "/": {
            "request.dispatch": cherrypy.dispatch.MethodDispatcher(),
            "tools.sessions.on": True,
        }
    }  # CherryPy configuration
    cherrypy.tree.mount(
        motion_sensor, "/", conf
    )  # Mount the PIRSensor class to the root URL
    cherrypy.config.update(
        {"server.socket_host": ip}
    )  # Set the server socket host to the local IP address
    cherrypy.config.update(
        {"server.socket_port": 8081}
    )  # Set the server socket port to 8081

    heartbeat_thread = threading.Thread(
        target=motion_sensor.heartbeat
    )  # Create a thread for sending heartbeat messages
    heartbeat_thread.daemon = True  # The thread will terminate when the program ends
    heartbeat_thread.start()  # Start the heartbeat thread

    cherrypy.engine.start()  # Start the CherryPy server

    motion_sensor.publish(
        settings["baseTopic"] + "/kennel1/sensors/motion",
        {
            "bn": "MotionSensor",
            "e": [
                {
                    "n": "motion",
                    "u": "bool",
                    "t": datetime.datetime.now().timestamp(),
                    "v": False,
                }
            ],
        },
        2,
    )  # Initialize motion sensor status for plots on thingspeak and nodered

    while True:
        try:
            motion_sensor.motion_sensor.wait_for_motion()  # Wait for motion detection
            motion_sensor.publish(
                settings["baseTopic"] + "/kennel1/sensors/motion",
                {
                    "bn": "MotionSensor",
                    "e": [
                        {
                            "n": "motion",
                            "u": "bool",
                            "t": datetime.datetime.now().timestamp(),
                            "v": True,
                        }
                    ],
                },
                2,
            )  # Publish motion detected status
            motion_sensor.motion_sensor.wait_for_no_motion()  # Wait for no motion detection
            motion_sensor.publish(
                settings["baseTopic"] + "/kennel1/sensors/motion",
                {
                    "bn": "MotionSensor",
                    "e": [
                        {
                            "n": "motion",
                            "u": "bool",
                            "t": datetime.datetime.now().timestamp(),
                            "v": False,
                        }
                    ],
                },
                2,
            )  # Publish no motion detected status
        except KeyboardInterrupt:
            break
    cherrypy.engine.stop()  # Stop the CherryPy server
    motion_sensor.stop()  # Stop the MQTT client
