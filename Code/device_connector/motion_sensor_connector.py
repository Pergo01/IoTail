from gpiozero import MotionSensor
from Libraries import Publisher
import time
import json
import datetime
import cherrypy
import socket


class PIRSensor:
    exposed = True

    def __init__(self, clientID, broker, port):
        self.motion_sensor = MotionSensor(14)
        self.broker = broker
        self.port = port
        self.client = Publisher(clientID, broker, port, self)

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


if __name__ == "__main__":
    settings = json.load(open("mqtt_settings.json"))
    motion_sensor = PIRSensor("MotionSensor", settings["broker"], settings["port"])
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
