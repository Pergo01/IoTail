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
        self.motion_sensor = MotionSensor(14)
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
        )

    def heartbeat(self):
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
    motion_sensor = PIRSensor("MotionSensor", settings["broker"], settings["port"], 2)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    motion_sensor.start()
    conf = {
        "/": {
            "request.dispatch": cherrypy.dispatch.MethodDispatcher(),
            "tools.sessions.on": True,
        }
    }
    cherrypy.tree.mount(motion_sensor, "/", conf)
    cherrypy.config.update({"server.socket_host": ip})
    cherrypy.config.update({"server.socket_port": 8081})

    heartbeat_thread = threading.Thread(target=motion_sensor.heartbeat)
    heartbeat_thread.daemon = True  # The thread will terminate when the program ends
    heartbeat_thread.start()

    cherrypy.engine.start()

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
            motion_sensor.motion_sensor.wait_for_motion()
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
            )
            motion_sensor.motion_sensor.wait_for_no_motion()
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
            )
        except KeyboardInterrupt:
            break
    cherrypy.engine.stop()
    motion_sensor.stop()
