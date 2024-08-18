import requests
import json

class MobileAppSimulator:
    def __init__(self, catalog_url):
        self.catalog_url = catalog_url

    def book_kennel(self, dog_info):
        response = requests.post(f"{self.catalog_url}/reservations", json=dog_info)
        return response.json()

    def get_kennel_status(self, kennel_id):
        response = requests.get(f"{self.catalog_url}/kennels/{kennel_id}")
        return response.json()

    def end_reservation(self, kennel_id):
        response = requests.delete(f"{self.catalog_url}/reservations/{kennel_id}")
        return response.json()

if __name__ == "__main__":
    app = MobileAppSimulator("http://localhost:8080")
    
    # Simulate booking a kennel
    dog_info = {
        "breed": "Labrador",
        "age": 3,
        "weight": 25
    }
    booking = app.book_kennel(dog_info)
    print(f"Booking response: {booking}")

    # Simulate getting kennel status
    if 'kennel_id' in booking:
        status = app.get_kennel_status(booking['kennel_id'])
        print(f"Kennel status: {status}")

    # Simulate ending reservation
    if 'kennel_id' in booking:
        end_reservation = app.end_reservation(booking['kennel_id'])
        print(f"End reservation response: {end_reservation}")