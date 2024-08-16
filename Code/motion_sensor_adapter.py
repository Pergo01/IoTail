from gpiozero import MotionSensor
from Libraries import Publisher
import time
import json


class PIRSensor:

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


if __name__ == "__main__":
    settings = json.load(open("settings.json"))
    motion_sensor = PIRSensor("MotionSensor", settings["broker"], settings["port"])
    motion_sensor.start()

    while True:
        try:
            motion_sensor.motion_sensor.wait_for_motion()
            motion_sensor.publish("IoTail", {"movement": True}, 2)
            motion_sensor.motion_sensor.wait_for_no_motion()
            motion_sensor.publish("IoTail", {"movement": False}, 2)
        except KeyboardInterrupt:
            break
    motion_sensor.stop()
