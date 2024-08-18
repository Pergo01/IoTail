import paho.mqtt.client as mqtt
import json
import time
import requests
import random

class DeviceConnector:
    def __init__(self, settings_file):
        with open(settings_file) as f:
            self.settings = json.load(f)
        
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.catalog_url = self.settings['catalog_url']
       #self.broker_info = self.get_broker_info()
    '''
    def get_broker_info(self):
        response = requests.get(f"{self.catalog_url}/broker")
        return json.loads(response.text)
    '''
    def connect(self):
        self.client.connect("mosquitto", 1883, 60)

    def on_connect(self, client, userdata, flags, rc):
        print(f"Connected with result code {rc}")
        self.client.subscribe("IoTail/+/actuators/#")

    def on_message(self, client, userdata, msg):
        print(f"Received message on topic {msg.topic}: {msg.payload.decode()}")
        # Handle actuation commands here

    def publish_sensor_data(self):
        while True:
            temperature = random.uniform(15, 30)
            humidity = random.uniform(20, 80)
            motion = random.choice([0, 1])

            payload = {
                "temperature": temperature,
                "humidity": humidity,
                "motion": motion
            }

            self.client.publish("IoTail/kennel1/sensors", json.dumps(payload))
            time.sleep(60)  # Publish every minute

    def run(self):
        self.connect()
        self.client.loop_start()
        self.publish_sensor_data()

if __name__ == "__main__":
    connector = DeviceConnector("settings.json")
    connector.run()