from Libraries import Publisher
import time
import json
import board
import adafruit_dht
import datetime
import cherrypy
import socket
import requests
import threading


class TempHumidSensor:
    exposed = True

    def __init__(self, clientID, broker, port, deviceID):
        self.deviceID = deviceID
        self.temp_humid_sensor = adafruit_dht.DHT11(
            board.D15, use_pulseio=False
        )  # Initialize DHT11 sensor on GPIO pin D15
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
        temp = self.temp_humid_sensor.temperature
        humid = self.temp_humid_sensor.humidity
        return json.dumps(
            {
                "bn": "TempHumidSensor",
                "e": [
                    {
                        "n": "temperature",
                        "u": "Cel",
                        "t": datetime.datetime.now().timestamp(),
                        "v": temp,
                    },
                    {
                        "n": "humidity",
                        "u": "%",
                        "t": datetime.datetime.now().timestamp(),
                        "v": humid,
                    },
                ],
            }
        )  # Returns the current temperature and humidity in JSON format

    def heartbeat(self):
        """Sends a heartbeat signal to the catalog service every 60 seconds."""
        while True:
            try:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer temp_humid_sensor",
                }
                url = self.catalog_url + "/heartbeat"
                payload = {
                    "category": "sensor",
                    "deviceID": self.deviceID,
                }
                response = requests.post(
                    url, headers=headers, data=json.dumps(payload)
                )  # Send heartbeat to catalog service
                if response.status_code == 200:  # Check if the heartbeat was successful
                    print("Heartbeat sent successfully")
                else:
                    print("Failed to send heartbeat")
            except requests.exceptions.RequestException as e:
                print(f"Error sending heartbeat: {e}")
            time.sleep(60)  # Wait for 60 seconds before sending the next heartbeat


if __name__ == "__main__":
    settings = json.load(open("mqtt_settings.json"))  # Load MQTT settings
    temp_humid_sensor = TempHumidSensor(
        "TempHumidSensor", settings["broker"], settings["port"], 1
    )  # Initialize TempHumidSensor with MQTT settings
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]  # Get the local IP address
    s.close()
    temp_humid_sensor.start()  # Start the MQTT client
    conf = {
        "/": {
            "request.dispatch": cherrypy.dispatch.MethodDispatcher(),
            "tools.sessions.on": True,
        }
    }  # Configuration for CherryPy server
    cherrypy.tree.mount(
        temp_humid_sensor, "/", conf
    )  # Mount the TempHumidSensor to the CherryPy server
    cherrypy.config.update(
        {"server.socket_host": ip}
    )  # Update the server socket host to the local IP address
    cherrypy.config.update(
        {"server.socket_port": 8082}
    )  # Update the server socket port to 8082

    heartbeat_thread = threading.Thread(
        target=temp_humid_sensor.heartbeat
    )  # Heartbeat thread for TempHumidSensor
    heartbeat_thread.daemon = True  # The thread will terminate when the program ends
    heartbeat_thread.start()  # Start the heartbeat thread

    cherrypy.engine.start()  # Start the CherryPy server

    while True:
        try:
            temp = temp_humid_sensor.temp_humid_sensor.temperature
            humid = temp_humid_sensor.temp_humid_sensor.humidity
            timestamp = datetime.datetime.now().timestamp()
            temp_humid_sensor.publish(
                settings["baseTopic"] + "/kennel1/sensors/temp_humid",
                {
                    "bn": "TempHumidSensor",
                    "e": [
                        {
                            "n": "temperature",
                            "u": "Cel",
                            "t": timestamp,
                            "v": temp,
                        },
                        {
                            "n": "humidity",
                            "u": "%",
                            "t": timestamp,
                            "v": humid,
                        },
                    ],
                },
                2,
            )  # Publish temperature and humidity data
            time.sleep(1.0)
        except RuntimeError as error:
            print(error.args[0])
            time.sleep(2.0)
            continue
        except KeyboardInterrupt:
            break
    cherrypy.engine.block()  # Block the CherryPy engine to keep the server running
    temp_humid_sensor.stop()  # Stop the MQTT client
