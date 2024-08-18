import paho.mqtt.client as mqtt
import json
import requests
import time

class DataAnalysis:
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
        self.client.subscribe("IoTail/+/sensors")

    def on_message(self, client, userdata, msg):
        data = json.loads(msg.payload.decode())
        self.analyze_data(data)

    def analyze_data(self, data):
        # Implement data analysis logic here
        if data['temperature'] > 30 or data['temperature'] < 15:
            self.send_alert("Temperature out of range")
        if data['humidity'] > 80 or data['humidity'] < 20:
            self.send_alert("Humidity out of range")
        if data['motion'] == 1:
            self.send_alert("Dog is agitated")

    def send_alert(self, message):
        alert = {
            "timestamp": time.time(),
            "message": message
        }
        self.client.publish("IoTail/alerts", json.dumps(alert))

    def run(self):
        self.connect()
        self.client.loop_forever()

if __name__ == "__main__":
    analysis = DataAnalysis("settings.json")
    analysis.run()