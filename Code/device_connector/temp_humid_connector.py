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
        self.temp_humid_sensor = adafruit_dht.DHT11(board.D15, use_pulseio=False)
        self.broker = broker
        self.port = port
        self.client = Publisher(clientID, broker, port, self)
        self.catalog_url = json.load(open("settings.json"))["catalog_url"]

    def start(self):
        self.client.start()
        time.sleep(1)

    def publish(self, topic, message, QoS):
        self.client.publish(topic, message, QoS)

    def stop(self):
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
        )

    def heartbeat(self):
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
                response = requests.post(url, headers=headers, data=json.dumps(payload))
                if response.status_code == 200:
                    print("Heartbeat sent successfully")
                else:
                    print("Failed to send heartbeat")
            except requests.exceptions.RequestException as e:
                print(f"Error sending heartbeat: {e}")
            time.sleep(60)


if __name__ == "__main__":
    settings = json.load(open("mqtt_settings.json"))
    temp_humid_sensor = TempHumidSensor(
        "TempHumidSensor", settings["broker"], settings["port"], 1
    )
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    temp_humid_sensor.start()
    conf = {
        "/": {
            "request.dispatch": cherrypy.dispatch.MethodDispatcher(),
            "tools.sessions.on": True,
        }
    }
    cherrypy.tree.mount(temp_humid_sensor, "/", conf)
    cherrypy.config.update({"server.socket_host": ip})
    cherrypy.config.update({"server.socket_port": 8082})

    heartbeat_thread = threading.Thread(target=temp_humid_sensor.heartbeat)
    heartbeat_thread.daemon = True  # The thread will terminate when the program ends
    heartbeat_thread.start()

    cherrypy.engine.start()

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
            )
            time.sleep(1.0)
        except RuntimeError as error:
            print(error.args[0])
            time.sleep(2.0)
            continue
        except KeyboardInterrupt:
            break
    cherrypy.engine.block()
    temp_humid_sensor.stop()
