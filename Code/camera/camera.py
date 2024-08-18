import cv2
import paho.mqtt.client as mqtt
import json
import requests
import base64

class Camera:
    def __init__(self, settings_file):
        with open(settings_file) as f:
            self.settings = json.load(f)
        
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.catalog_url = self.settings['catalog_url']
       #self.broker_info = self.get_broker_info()

        self.camera = cv2.VideoCapture(0)
    '''
    def get_broker_info(self):
        response = requests.get(f"{self.catalog_url}/broker")
        return json.loads(response.text)
    '''
    def connect(self):
        self.client.connect("mosquitto", 1883, 60)

    def on_connect(self, client, userdata, flags, rc):
        print(f"Connected with result code {rc}")
        self.client.subscribe("IoTail/+/camera/activate")

    def on_message(self, client, userdata, msg):
        if msg.topic.endswith("/camera/activate"):
            self.activate_camera()

    def activate_camera(self):
        ret, frame = self.camera.read()
        if ret:
            _, buffer = cv2.imencode('.jpg', frame)
            jpg_as_text = base64.b64encode(buffer).decode('utf-8')
            self.client.publish("IoTail/kennel1/camera/frame", jpg_as_text)

    def run(self):
        self.connect()
        self.client.loop_forever()

if __name__ == "__main__":
    camera = Camera("settings.json")
    camera.run()