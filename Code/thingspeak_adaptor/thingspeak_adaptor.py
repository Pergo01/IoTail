import paho.mqtt.client as mqtt
import json
import requests
import time

class ThingspeakAdaptor:
    def __init__(self, settings_file):
        with open(settings_file) as f:
            self.settings = json.load(f)
        
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.catalog_url = self.settings['catalog_url']
       #self.broker_info = self.get_broker_info()
        self.thingspeak_api_key = self.settings['thingspeak_api_key']
        self.thingspeak_url = f"https://api.thingspeak.com/update?api_key={self.thingspeak_api_key}"
    '''
    def get_broker_info(self):
        response = requests.get(f"{self.catalog_url}/broker")
        return json.loads(response.text)
    '''
    def connect(self):
        self.client.connect("mosquitto", 1883, 60)

    def on_connect(self, client, userdata, flags, rc):
        print(f"Connected with result code {rc}")
        self.client.subscribe("IoTail/+/sensors")

    def on_message(self, client, userdata, msg):
        data = json.loads(msg.payload.decode())
        self.send_to_thingspeak(data)

    def send_to_thingspeak(self, data):
        payload = {
            "field1": data['temperature'],
            "field2": data['humidity'],
            "field3": data['motion']
        }
        response = requests.get(self.thingspeak_url, params=payload)
        print(f"Sent to Thingspeak: {response.status_code}")

    def run(self):
        self.connect()
        self.client.loop_forever()

if __name__ == "__main__":
    adaptor = ThingspeakAdaptor("settings.json")
    adaptor.run()