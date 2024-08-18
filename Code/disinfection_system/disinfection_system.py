import paho.mqtt.client as mqtt
import json
import time

class DisinfectionSystem:
    def __init__(self, settings_file):
        with open(settings_file) as f:
            self.settings = json.load(f)
        
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.catalog_url = self.settings['catalog_url']

    def connect(self):
        self.client.connect("mosquitto", 1883, 60)

    def on_connect(self, client, userdata, flags, rc):
        print(f"Connected with result code {rc}")
        self.client.subscribe("IoTail/+/disinfection")

    def on_message(self, client, userdata, msg):
        print(f"Received message: {msg.payload.decode()} on topic {msg.topic}")
        kennel_id = msg.topic.split('/')[1]
        self.disinfect_kennel(kennel_id)

    def disinfect_kennel(self, kennel_id):
        print(f"Starting disinfection process for kennel {kennel_id}")
        time.sleep(5)  # Simulate disinfection process
        print(f"Disinfection complete for kennel {kennel_id}")
        self.client.publish(f"IoTail/{kennel_id}/status", json.dumps({"status": "disinfected"}))

    def run(self):
        self.connect()
        self.client.loop_forever()

if __name__ == "__main__":
    disinfection_system = DisinfectionSystem("settings.json")
    disinfection_system.run()