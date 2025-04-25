import json
import time
import uuid
import socket
import cherrypy
import requests
import jwt
import threading
from Libraries import PublisherSubscriber
import firebase_admin
from firebase_admin import credentials, messaging, exceptions


class ReservationManager:
    exposed = True

    def __init__(self, reservation_file, clientID, broker, port, baseTopic):
        with open("secret_key.txt") as f:
            self.secret_key = f.read()
        self.get_stores()
        self.reservation_file = reservation_file
        self.clientID = clientID
        self.broker = broker
        self.port = port
        self.baseTopic = baseTopic
        self.client = PublisherSubscriber(clientID, broker, port, self)
        self.pending_reservations = []

        if not firebase_admin._apps:  # Ensures Firebase is initialized only once
            cred = credentials.Certificate("firebase_account_key.json")
            firebase_admin.initialize_app(cred)

        # Load reservations from file, if present
        try:
            with open(self.reservation_file) as f:
                self.reservations = json.load(f)
            for reservation in self.reservations["reservation"]:
                self.occupy_kennel(
                    reservation["storeID"], reservation["kennelID"]
                )  # set reserved kennels as occupied
        except FileNotFoundError:
            self.reservations = {"reservation": []}

    def start(self):
        self.client.start()
        message = {"message": "on"}
        for store in self.settings:
            for kennel in store["Kennels"]:  # set all kennel leds as free when starting
                self.publish(
                    self.baseTopic + "/kennel1/leds/greenled", message, 2
                )  # SHOULD BE f"kennel{kennel["ID"]}/leds/greenled" but we have just one led
        time.sleep(1)

    def subscribe(self, topic, QoS):
        self.client.subscribe(topic, QoS)

    def publish(self, topic, message, QoS):
        self.client.publish(topic, message, QoS)

    def stop(self):
        self.client.stop()

    def notify(self, topic, msg):
        data = json.loads(msg)
        kennelID = int(topic.split("/")[1].replace("kennel", ""))
        reservation = next(
            (res for res in self.pending_reservations if (res["kennelID"]) == kennelID),
            None,
        )
        status = data.get("message")
        if reservation and status == "disinfected":
            self.free_kennel(reservation["storeID"], reservation["kennelID"])
            self.pending_reservations.remove(reservation)
            self.get_stores()

    def get_user(self, userID):
        headers = {
            "Authorization": f"Bearer reservation_manager",
            "Content-Type": "application/json",
        }
        response = requests.get(f"http://catalog:8080/users/{userID}", headers=headers)
        if response.ok:
            return response.json()
        else:
            print("Couldn't get users")
            raise cherrypy.HTTPError(404, "User not found")

    def get_stores(self):
        headers = {
            "Authorization": f"Bearer reservation_manager",
            "Content-Type": "application/json",
        }
        response = requests.get(f"http://catalog:8080/stores", headers=headers)
        if response.ok:
            self.settings = response.json()
        else:
            print("Couldn't get stores")
            exit(1)

    def verify_token(self, token):
        if token == "data_analysis":
            return token
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

    def find_available_kennel(self, store, dog_size):
        # Define the order for kennel dimensions
        dimension_order = {"Small": 0, "Medium": 1, "Large": 2}

        # Sort kennels by dimension size
        sorted_kennels = sorted(
            store["Kennels"], key=lambda x: dimension_order[x["Size"]]
        )

        # Find the smallest available kennel that fits the dog
        for kennel in sorted_kennels:
            if (
                not kennel["Booked"]
                and not kennel["Occupied"]
                and dimension_order[kennel["Size"]] >= dimension_order[dog_size]
            ):
                return kennel["ID"]

        # Return None if no suitable kennel is found
        return None

    def handle_reservation(self, data):
        dogID = data.get("dogID")
        userID = data.get("userID")
        storeID = data.get("storeID")
        dog_size = data.get("dog_size")

        store = next(
            (s for s in self.settings if s["StoreID"] == storeID),
            None,
        )
        kennelID = self.find_available_kennel(store, dog_size)
        if kennelID is not None:
            reservationID = str(
                uuid.uuid4()
            )  # Genera un ID univoco per la prenotazione
            self.book_kennel(storeID, int(kennelID))
            reservationTime = round(time.time())
            unlockCode = next(
                (
                    kennel["UnlockCode"]
                    for kennel in store["Kennels"]
                    if kennel["ID"] == kennelID
                ),
                None,
            )
            user = self.get_user(userID)
            self.reservations["reservation"].append(
                {
                    "userID": userID,
                    "reservationID": reservationID,
                    "dogID": dogID,
                    "kennelID": kennelID,
                    "storeID": storeID,
                    "active": False,
                    "unlockCode": unlockCode,
                    "firebaseTokens": user["FirebaseTokens"],
                    "reservationTime": reservationTime,
                    "activationTime": None,
                }
            )
            self.save_reservations()
            self.get_stores()
            return json.dumps(
                {
                    "status": "confirmed",
                    "kennelID": kennelID,
                    "reservationID": reservationID,
                    "timestamp": reservationTime,
                    "message": f"Reservation confirmed for dog {dogID})",
                }
            )
        raise cherrypy.HTTPError(404, "No available kennels")

    def handle_unlock(self, data):
        dogID = data.get("dogID")
        userID = data.get("userID")
        dog_size = data.get("dog_size")
        kennelID = data.get("kennelID")
        code = data.get("unlockCode")

        if kennelID is not None:
            # Define the order for kennel dimensions
            dimension_order = {"Small": 0, "Medium": 1, "Large": 2}
            tmp = {
                store["StoreID"]: [kennel["ID"], kennel["UnlockCode"]]
                for store in self.settings
                for kennel in store["Kennels"]
                if kennel["ID"] == kennelID
                and dimension_order[kennel["Size"]] >= dimension_order[dog_size]
                and not kennel["Booked"]
                and not kennel["Occupied"]
            }
            if not tmp:
                raise cherrypy.HTTPError(
                    404, "Kennel not compatible with dog size or not available"
                )

            storeID, kennel_info = list(tmp.items())[0]
            kennelID, unlockCode = kennel_info

            if unlockCode != code:
                raise cherrypy.HTTPError(401, "Invalid unlock code")

            reservationID = str(
                uuid.uuid4()
            )  # Genera un ID univoco per la prenotazione
            self.occupy_kennel(storeID, int(kennelID))
            user = self.get_user(userID)
            reservationTime = round(time.time())
            self.reservations["reservation"].append(
                {
                    "userID": userID,
                    "reservationID": reservationID,
                    "dogID": dogID,
                    "kennelID": kennelID,
                    "storeID": storeID,
                    "active": True,
                    "firebaseTokens": user["FirebaseTokens"],
                    "reservationTime": reservationTime,
                    "activationTime": reservationTime,
                }
            )
            self.save_reservations()
            self.get_stores()
            return json.dumps(
                {
                    "status": "confirmed",
                    "kennelID": kennelID,
                    "reservationID": reservationID,
                    "timestamp": reservationTime,
                    "message": f"Reservation confirmed for dog {dogID})",
                }
            )
        raise cherrypy.HTTPError(404, "No available kennels")

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
            message = {"message": "off"}
            self.publish(
                self.baseTopic + "/kennel1/leds/redled", message, 2
            )  # SHOULD BE f"kennel{kennelID}/leds/redled" but we have just one led per color
            if reservation["active"]:
                self.pending_reservations.append(reservation)
                message = {"message": "on"}
                self.publish(
                    self.baseTopic + "/kennel1/leds/yellowled", message, 2
                )  # SHOULD BE f"kennel{kennelID}/leds/yellowled" but we have just one led per color
                self.publish(
                    self.baseTopic + f"/kennel{reservation['kennelID']}/disinfect",
                    message,
                    2,
                )
            else:
                self.free_kennel(reservation["storeID"], reservation["kennelID"])
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

    def handle_activation(self, reservationID, unlockCode):
        reservation = next(
            (
                res
                for res in self.reservations["reservation"]
                if (res["reservationID"]) == reservationID
            ),
            None,
        )
        if reservation:
            if reservation["unlockCode"] != unlockCode:
                raise cherrypy.HTTPError(status=401, message="Invalid unlock code")
            self.occupy_kennel(reservation["storeID"], reservation["kennelID"])
            reservation["active"] = True
            reservation["activationTime"] = round(time.time())
            self.save_reservations()
            self.get_stores()
            return json.dumps(
                {
                    "status": "active",
                    "message": f"Reservation in kennel {reservation['kennelID']} activated",
                }
            )
        else:
            return json.dumps(
                {
                    "status": "not_found",
                    "message": f"No reservation found for id {reservationID}",
                }
            )

    def book_kennel(self, storeID: int, kennel: int):
        headers = {
            "Authorization": "Bearer reservation_manager",
            "Content-Type": "application/json",
        }
        body = json.dumps({"storeID": storeID, "kennel": kennel})
        response = requests.post(
            f"http://catalog:8080/book",
            headers=headers,
            data=body,
        )
        if response.ok:
            message = {"message": "off"}
            self.publish(
                self.baseTopic + "/kennel1/leds/greenled", message, 2
            )  # SHOULD BE "kennel{kennelID}/leds/greenled" but we have just one led per color
            message = {"message": "on"}
            self.publish(
                self.baseTopic + "/kennel1/leds/yellowled", message, 2
            )  # SHOULD BE "kennel{kennelID}/leds/yellowled" but we have just one led per color
            return json.loads(response.text)
        raise cherrypy.HTTPError(500, "Error booking kennel")

    def free_kennel(self, storeID: int, kennel: int):
        headers = {
            "Authorization": "Bearer reservation_manager",
            "Content-Type": "application/json",
        }
        body = json.dumps({"storeID": storeID, "kennel": kennel})
        response = requests.post(
            f"http://catalog:8080/free",
            headers=headers,
            data=body,
        )
        if response.ok:
            message = {"message": "off"}
            self.publish(
                self.baseTopic + "/kennel1/leds/yellowled", message, 2
            )  # SHOULD BE "kennel{kennelID}/leds/yellowled" but we have just one led per color
            message = {"message": "on"}
            self.publish(
                self.baseTopic + "/kennel1/leds/greenled", message, 2
            )  # SHOULD BE f"kennel{kennelID}/leds/greenled" but we have just one led per color
            return json.loads(response.text)
        raise cherrypy.HTTPError(500, "Error unlocking kennel")

    def occupy_kennel(self, storeID: int, kennel: int):
        headers = {
            "Authorization": "Bearer reservation_manager",
            "Content-Type": "application/json",
        }
        body = json.dumps({"storeID": storeID, "kennel": kennel})
        response = requests.post(
            f"http://catalog:8080/lock",
            headers=headers,
            data=body,
        )
        if response.ok:
            message = {"message": "off"}
            self.publish(
                self.baseTopic + "/kennel1/leds/greenled", message, 2
            )  # SHOULD BE "kennel{kennelID}/leds/greenled" but we have just one led per color
            self.publish(
                self.baseTopic + "/kennel1/leds/yellowled", message, 2
            )  # SHOULD BE "kennel{kennelID}/leds/yellowled" but we have just one led per color
            message = {"message": "on"}
            self.publish(
                self.baseTopic + "/kennel1/leds/redled", message, 2
            )  # SHOULD BE "kennel{kennelID}/leds/redled" but we have just one led per color
            return json.loads(response.text)
        raise cherrypy.HTTPError(500, "Error unlocking kennel")

    def check_expiry(self):
        while True:
            current_time = round(time.time())
            if self.reservations:
                for reservation in self.reservations["reservation"]:
                    if (
                        current_time - reservation["reservationTime"] > 1800
                        and not reservation["active"]
                    ):  # 30 minutes passed
                        self.handle_cancellation(reservation["reservationID"])
                        for token in reservation["firebaseTokens"]:
                            message = messaging.Message(
                                notification=messaging.Notification(
                                    title="Reservation Expired",
                                    body="Your reservation has expired since 30 minutes passed since its submission.",
                                ),
                                token=token,
                            )
                            try:
                                response = messaging.send(message)
                                print(
                                    f"Message sent successfully for kennel {reservation['kennelID']}: {response}"
                                )
                            except exceptions.FirebaseError as e:
                                print(f"Error sending message: {e}")
                    elif (
                        round(current_time - reservation["reservationTime"]) == 1500
                        and not reservation["active"]
                    ):  # 25 minutes passed
                        for token in reservation["firebaseTokens"]:
                            message = messaging.Message(
                                notification=messaging.Notification(
                                    title="Reservation Reminder",
                                    body="Your reservation will expire in 5 minutes. Activate it soon or it will be canceled.",
                                ),
                                token=token,
                            )
                            try:
                                response = messaging.send(message)
                                print(
                                    f"Message sent successfully for kennel {reservation['kennelID']}: {response}"
                                )
                            except exceptions.FirebaseError as e:
                                print(f"Error sending message: {e}")
            time.sleep(1)  # Repeat every second

    def POST(self, *uri):
        auth_header = cherrypy.request.headers.get("Authorization")
        if not auth_header:
            raise cherrypy.HTTPError(401, "Authorization token required")
        token = auth_header.split(" ")[1]
        self.verify_token(token)  # Verify the token
        body = cherrypy.request.body.read()
        data = json.loads(body)
        if uri[0] == "reserve":
            return self.handle_reservation(data)
        if uri[0] == "unlock":
            return self.handle_unlock(data)
        if uri[0] == "activate":
            if len(uri) < 2:
                raise cherrypy.HTTPError(400, "Reservation ID required")
            reservationID = uri[1]
            return self.handle_activation(reservationID, data["unlockCode"])
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
    settings = json.load(open("mqtt_settings.json"))
    manager = ReservationManager(
        "reservation.json",
        "ReservationManager",
        settings["broker"],
        settings["port"],
        settings["baseTopic"],
    )

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

    check_expiry_thread = threading.Thread(target=manager.check_expiry)
    check_expiry_thread.daemon = True  # Il thread terminerà quando il programma termina
    check_expiry_thread.start()

    cherrypy.tree.mount(manager, "/", conf)
    cherrypy.config.update({"server.socket_host": ip})
    cherrypy.config.update({"server.socket_port": 8083})
    cherrypy.engine.start()
    manager.start()
    manager.subscribe(settings["baseTopic"] + "/+/status", 2)
    cherrypy.engine.block()
    manager.stop()
