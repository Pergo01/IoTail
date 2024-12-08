import json
import time
import uuid
import socket
import cherrypy
import requests
import jwt


class ReservationManager:
    exposed = True

    def __init__(self, reservation_file):
        with open("secret_key.txt") as f:
            self.secret_key = f.read()
        headers = {
            "Authorization": f"Bearer reservation_manager",
            "Content-Type": "application/json",
        }
        response = requests.get(
            f"http://host.docker.internal:8080/kennels", headers=headers
        )
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

    def verify_token(self, token):
        try:
            decoded = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            return decoded
        except jwt.ExpiredSignatureError:
            raise cherrypy.HTTPError(401, "Token has expired")
        except jwt.InvalidTokenError:
            raise cherrypy.HTTPError(401, "Invalid token")

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
        dog_name = data.get("dog_name")
        dog_breed = data.get("dog_breed")
        dog_size = data.get("dog_size")
        userID = data.get("userID")

        kennelID = self.find_available_kennel()
        if kennelID:
            reservationID = str(uuid.uuid4())  # Genera un ID univoco per il cane
            self.reservations["reservation"].append(
                {
                    "userID": userID,
                    "reservationID": reservationID,
                    "dog_name": dog_name,
                    "dog_breed": dog_breed,
                    "dog_size": dog_size,
                    "kennelID": kennelID,
                    "timestamp": time.time(),
                }
            )
            self.save_reservations()
            return json.dumps(
                {
                    "status": "confirmed",
                    "kennelID": kennelID,
                    "reservationID": reservationID,
                    "message": f"Reservation confirmed for {dog_name} ({dog_breed})",
                }
            )
        else:
            return json.dumps(
                {"status": "unavailable", "message": "No kennels available"}
            )

    def handle_cancellation(self, reservationID):
        reservation = next(
            (
                res
                for res in self.reservations["reservation"]
                if (res["reservationID"]) == reservationID
            ),
            None,
        )
        if reservation:
            self.reservations["reservation"].remove(reservation)
            self.save_reservations()
            return json.dumps(
                {
                    "status": "cancelled",
                    "message": f"Reservation for {reservation['dog_name']} in kennel {reservation['kennelID']} cancelled",
                }
            )
        else:
            return json.dumps(
                {
                    "status": "not_found",
                    "message": f"No reservation found for id {reservationID}",
                }
            )

    def POST(self, *uri):
        auth_header = cherrypy.request.headers.get("Authorization")
        if not auth_header:
            raise cherrypy.HTTPError(401, "Authorization token required")
        token = auth_header.split(" ")[1]
        self.verify_token(token)  # Verify the token
        if uri[0] == "reserve":
            body = cherrypy.request.body.read()
            data = json.loads(body)
            return self.handle_reservation_request(data)
        elif uri[0] == "cancel":
            reservationID = uri[1]
            return self.handle_cancellation(reservationID)
        else:
            raise cherrypy.HTTPError(404, "Endpoint not found")

    def GET(self, *uri):
        auth_header = cherrypy.request.headers.get("Authorization")
        if not auth_header:
            raise cherrypy.HTTPError(401, "Authorization token required")
        token = auth_header.split(" ")[1]
        self.verify_token(token)  # Verify the token
        if uri[0] == "status":
            if len(uri) > 1:
                reservations = [
                    res
                    for res in self.reservations["reservation"]
                    if res["userID"] == uri[1]
                ]
                return json.dumps(reservations)
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
            "tools.sessions.on": True,
            "request.show_tracebacks": False,
        }
    }
    cherrypy.tree.mount(manager, "/", conf)
    cherrypy.config.update({"server.socket_host": ip})
    cherrypy.config.update({"server.socket_port": 8083})
    cherrypy.engine.start()
    cherrypy.engine.block()

    print(f"Server running at http://{ip}:8083/")
    cherrypy.engine.start()
