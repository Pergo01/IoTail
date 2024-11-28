
import json
import time
import uuid
import socket
import cherrypy
import requests

class ReservationManager:
    exposed = True

    def __init__(self, reservation_file):
        
        response = requests.get(f"http://host.docker.internal:8080/kennels")
        if response.ok:
            self.settings = response.json()
        else: 
            print("Couldn't get list")    
            exit(1)
        self.reservation_file = reservation_file
        self.total_kennels = len(self.settings)

        # Carica le prenotazioni esistenti dal file, se presente
        try:
            with open(self.reservation_file) as f:
                self.reservations = json.load(f)
        except FileNotFoundError:
            self.reservations = {}

    def save_reservations(self):
        """Salva le prenotazioni nel file JSON."""
        with open(self.reservation_file, "w") as f:
            json.dump(self.reservations, f, indent=4)

    def find_available_kennel(self):
        for i in range(1, self.total_kennels + 1):
            if f"kennel{i}" not in self.reservations:
                return f"kennel{i}"
        return None

    def handle_reservation_request(self, data):
        dog_name = data.get('dog_name')
        dog_breed = data.get('dog_breed')
        dog_size = data.get('dog_size')
        
        kennel_id = self.find_available_kennel()
        if kennel_id:
            reservation_id = str(uuid.uuid4())  # Genera un ID univoco per il cane
            self.reservations["reservation"].append( {
                'reservation_id': reservation_id,
                'dog_name': dog_name,
                'dog_breed': dog_breed,
                'dog_size': dog_size,
                'kennel_id': kennel_id,
                'timestamp': time.time()
            })
            self.save_reservations()
            return json.dumps({
                "status": "confirmed", 
                "kennel_id": kennel_id,
                "reservation_id": reservation_id,
                "message": f"Reservation confirmed for {dog_name} ({dog_breed})"
            })
        else:
            return json.dumps({"status": "unavailable", "message": "No kennels available"})

    def handle_cancellation(self, data):
        reservation_id = data.get("reservation_id")
        reservation = next(
            (
                res
                for res in self.reservations["reservation"]
                if (res["reservation_id"]) == reservation_id
            ),
            None,
        )
        if reservation:
            self.reservations["reservation"].remove(reservation)
            self.save_reservations()
            return json.dumps(
                {
                    "status": "cancelled",
                    "message": f"Reservation for {reservation['dog_name']} in kennel {reservation['kennel_id']} cancelled",
                }
            )
        else:
            return json.dumps(
                {
                    "status": "not_found",
                    "message": f"No reservation found for id {reservation_id}",
                }
            ) 

    
    def POST(self, *uri):
        if uri[0] == "reserve":
            body = cherrypy.request.body.read()
            data = json.loads(body) 
            return self.handle_reservation_request(data)
        elif uri[0] == "cancel":
            body = cherrypy.request.body.read()
            data = json.loads(body) 
            return self.handle_cancellation(data)
        else:
            raise cherrypy.HTTPError(404, "Endpoint not found")

    
    def GET(self, *uri):
        if uri[0] == "status":
            return json.dumps(self.reservations["reservation"])
        else:
            raise cherrypy.HTTPError(404, "Endpoint not found")

if __name__ == "__main__":
    # Load settings and initialize the manager
    manager = ReservationManager("reservation.json")

    # Determine the local IP address
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    # CherryPy configuration
    conf = {
        "/": {
            "request.dispatch": cherrypy.dispatch.MethodDispatcher(),
            "tools.sessions.on": True
        }
    }

    # Mount the application and start the server
    cherrypy.tree.mount(manager, "/", conf)
    cherrypy.config.update({
        "server.socket_host": ip,
        "server.socket_port": 8083,
        "engine.autoreload.on": False,
    })

    print(f"Server running at http://{ip}:8083/")
    cherrypy.engine.start()
    