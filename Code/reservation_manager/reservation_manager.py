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
        self.get_stores()
        self.reservation_file = reservation_file

        # Carica le prenotazioni esistenti dal file, se presente
        try:
            with open(self.reservation_file) as f:
                self.reservations = json.load(f)
        except FileNotFoundError:
            self.reservations = {}

    def get_stores(self):
        headers = {
            "Authorization": f"Bearer reservation_manager",
            "Content-Type": "application/json",
        }
        response = requests.get(f"http://catalog:8080/stores", headers=headers)
        if response.ok:
            self.settings = response.json()
        else:
            print("Couldn't get list")
            exit(1)

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

    def find_available_kennel(self, store):
        # TODO sort kennel by dimension to fit the dog in the smallest possible kennel in which the dog can fit
        for kennel in store["Kennels"]:
            if not kennel["Booked"] and not kennel["Occupied"]:
                return kennel["ID"]
        return None

    def handle_reservation(self, data):
        dogID = data.get("dogID")
        userID = data.get("userID")
        loc = data.get("location")

        store = next(
            (s for s in self.settings if s["Location"] == loc),
            None,
        )
        kennelID = self.find_available_kennel(store)
        if kennelID is not None:
            reservationID = str(
                uuid.uuid4()
            )  # Genera un ID univoco per la prenotazione
            self.book_kennel(loc, int(kennelID))
            self.reservations["reservation"].append(
                {
                    "userID": userID,
                    "reservationID": reservationID,
                    "dogID": dogID,
                    "kennelID": kennelID,
                    "location": loc,
                    "timestamp": time.time(),
                }
            )
            self.save_reservations()
            self.get_stores()
            return json.dumps(
                {
                    "status": "confirmed",
                    "kennelID": kennelID,
                    "reservationID": reservationID,
                    "message": f"Reservation confirmed for dog {dogID})",
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
            self.free_kennel(reservation["location"], reservation["kennelID"])
            self.reservations["reservation"].remove(reservation)
            self.save_reservations()
            self.get_stores()
            return json.dumps(
                {
                    "status": "cancelled",
                    "message": f"Reservation in kennel {reservation['kennelID']} cancelled",
                }
            )
        else:
            return json.dumps(
                {
                    "status": "not_found",
                    "message": f"No reservation found for id {reservationID}",
                }
            )

    def book_kennel(self, location: list, kennel: int):
        headers = {
            "Authorization": "Bearer reservation_manager",
            "Content-Type": "application/json",
        }
        body = json.dumps({"location": location, "kennel": kennel})
        response = requests.post(
            f"http://catalog:8080/book",
            headers=headers,
            data=body,
        )
        if response.ok:
            return json.loads(response.text)
        raise cherrypy.HTTPError(500, "Error booking kennel")

    def free_kennel(self, location: list, kennel: int):
        headers = {
            "Authorization": "Bearer reservation_manager",
            "Content-Type": "application/json",
        }
        body = json.dumps({"location": location, "kennel": kennel})
        response = requests.post(
            f"http://catalog:8080/free",
            headers=headers,
            data=body,
        )
        if response.ok:
            return json.loads(response.text)
        raise cherrypy.HTTPError(500, "Error unlocking kennel")

    def POST(self, *uri):
        auth_header = cherrypy.request.headers.get("Authorization")
        if not auth_header:
            raise cherrypy.HTTPError(401, "Authorization token required")
        token = auth_header.split(" ")[1]
        self.verify_token(token)  # Verify the token
        if uri[0] == "reserve":
            body = cherrypy.request.body.read()
            data = json.loads(body)
            return self.handle_reservation(data)
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

    def DELETE(self, *uri):
        auth_header = cherrypy.request.headers.get("Authorization")
        if not auth_header:
            raise cherrypy.HTTPError(401, "Authorization token required")
        token = auth_header.split(" ")[1]
        self.verify_token(token)
        if uri[0] == "cancel":
            reservationID = uri[1]
            return self.handle_cancellation(reservationID)
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
