import paho.mqtt.client as mqtt
import json
import requests
import time

class ReservationManager:
    def __init__(self, settings_file):
        with open(settings_file) as f:
            self.settings = json.load(f)
        
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.catalog_url = self.settings['catalog_url']
       #self.broker_info = self.get_broker_info()

        self.reservations = {}
    '''
    def get_broker_info(self):
        response = requests.get(f"{self.catalog_url}/broker")
        return json.loads(response.text)
    '''
    def connect(self):
        self.client.connect("mosquitto", 1883, 60)

    def on_connect(self, client, userdata, flags, rc):
        print(f"Connected with result code {rc}")
        self.client.subscribe("IoTail/reservations/#")

    def on_message(self, client, userdata, msg):
        if msg.topic.endswith("/request"):
            self.handle_reservation_request(json.loads(msg.payload.decode()))
        elif msg.topic.endswith("/cancel"):
            self.handle_cancellation(json.loads(msg.payload.decode()))

    def handle_reservation_request(self, data):
        kennel_id = self.find_available_kennel()
        if kennel_id:
            self.reservations[kennel_id] = data
            response = {"status": "confirmed", "kennel_id": kennel_id}
        else:
            response = {"status": "unavailable"}
        self.client.publish("IoTail/reservations/response", json.dumps(response))

    def handle_cancellation(self, data):
        kennel_id = data.get('kennel_id')
        if kennel_id in self.reservations:
            del self.reservations[kennel_id]
            response = {"status": "cancelled"}
        else:
            response = {"status": "not_found"}
        self.client.publish("IoTail/reservations/response", json.dumps(response))

    def find_available_kennel(self):
        # Implement logic to find an available kennel
        # This is a simplified version
        for i in range(1, 11):  # Assuming 10 kennels
            if f"kennel{i}" not in self.reservations:
                return f"kennel{i}"
        return None

    def run(self):
        self.connect()
        self.client.loop_forever()

if __name__ == "__main__":
    manager = ReservationManager("settings.json")
    manager.run()