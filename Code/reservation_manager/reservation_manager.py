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

    def __init__(self, reservation_file, clientID, broker, port, baseTopic, serviceID):
        with open("secret_key.txt") as f:
            self.secret_key = f.read()  # Load the secret key from a file
        self.catalog_url = json.load(open("settings.json"))[
            "catalog_url"
        ]  # Load catalog URL from settings
        self.get_stores()  # Load the store settings from the catalog
        self.reservation_file = reservation_file
        self.clientID = clientID
        self.serviceID = serviceID
        self.broker = broker
        self.port = port
        self.baseTopic = baseTopic
        self.client = PublisherSubscriber(
            clientID, broker, port, self
        )  # Initialize MQTT client
        self.pending_reservations = []

        if not firebase_admin._apps:  # Ensures Firebase is initialized only once
            cred = credentials.Certificate("firebase_account_key.json")
            firebase_admin.initialize_app(cred)

        # Load reservations from file, if present
        try:
            with open(self.reservation_file) as f:
                self.reservations = json.load(f)
        except FileNotFoundError:
            self.reservations = {"reservation": []}

    def start(self):
        """Starts the MQTT client and sets up initial states for kennels."""
        self.client.start()
        message = {"message": "on"}
        for store in self.settings:
            for kennel in store["Kennels"]:  # set all kennel leds as free when starting
                self.publish(
                    self.baseTopic + "/kennel1/leds/greenled", message, 2
                )  # SHOULD BE f"kennel{kennel["ID"]}/leds/greenled" but we have just one led
        for reservation in self.reservations["reservation"]:
            if reservation["active"]:
                self.occupy_kennel(
                    reservation["storeID"], reservation["kennelID"]
                )  # set reserved kennels as occupied
            else:
                self.book_kennel(
                    reservation["storeID"], reservation["kennelID"]
                )  # set reserved kennels as locked
        time.sleep(1)

    def subscribe(self, topic, QoS):
        """Subscribes to a specific MQTT topic."""
        self.client.subscribe(topic, QoS)

    def publish(self, topic, message, QoS):
        """Publishes a message to a specific MQTT topic."""
        self.client.publish(topic, message, QoS)

    def stop(self):
        """Stops the MQTT client."""
        self.client.stop()

    def notify(self, topic, msg):
        """Handles incoming MQTT messages."""
        data = json.loads(msg)
        kennelID = int(
            topic.split("/")[1].replace("kennel", "")
        )  # Extract kennel ID from the topic
        reservation = next(
            (res for res in self.pending_reservations if (res["kennelID"]) == kennelID),
            None,
        )  # Find the reservation associated with the kennel ID
        status = data.get("message")
        if reservation and status == "disinfected":  # If the kennel is disinfected
            self.free_kennel(
                reservation["storeID"], reservation["kennelID"]
            )  # Free the kennel
            self.pending_reservations.remove(
                reservation
            )  # Remove the reservation from pending reservations
            self.get_stores()  # Refresh the store settings

    def get_user(self, userID):
        """Fetches user details from the catalog service."""
        headers = {
            "Authorization": f"Bearer reservation_manager",
            "Content-Type": "application/json",
        }
        response = requests.get(
            f"{self.catalog_url}/users/{userID}", headers=headers
        )  # Get user details from the catalog service
        if response.ok:  # If the response is successful
            return response.json()  # Return the user details as JSON
        print("Couldn't get users")
        raise cherrypy.HTTPError(
            404, "User not found"
        )  # If the user is not found, raise an error

    def get_stores(self):
        """Fetches store settings from the catalog service."""
        headers = {
            "Authorization": f"Bearer reservation_manager",
            "Content-Type": "application/json",
        }
        response = requests.get(
            f"{self.catalog_url}/stores", headers=headers
        )  # Get store settings from the catalog service
        if response.ok:  # If the response is successful
            self.settings = (
                response.json()
            )  # Store the settings in the instance variable
        print("Couldn't get stores")
        exit(1)

    def verify_token(self, token):
        """Verifies the JWT token."""
        if token == "data_analysis":  # Special case for data analysis token
            return token
        try:
            decoded = jwt.decode(
                token, self.secret_key, algorithms=["HS256"]
            )  # Decode the JWT token using the secret key
            return decoded
        except jwt.ExpiredSignatureError:  # If the token has expired
            raise cherrypy.HTTPError(401, "Token has expired")
        except jwt.InvalidTokenError:  # If the token is invalid
            raise cherrypy.HTTPError(401, "Invalid token")

    def save_reservations(self):
        """Saves the current reservations to the reservation file."""
        with open(self.reservation_file, "w") as f:
            json.dump(self.reservations, f, indent=4)

    def find_available_kennel(self, store, dog_size):
        """Finds an available kennel that fits the dog's size."""
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
        """Handles the reservation request."""
        dogID = data.get("dogID")
        userID = data.get("userID")
        storeID = data.get("storeID")
        dog_size = data.get("dog_size")

        store = next(
            (s for s in self.settings if s["StoreID"] == storeID),
            None,
        )  # Find the store by ID
        kennelID = self.find_available_kennel(
            store, dog_size
        )  # Find an available kennel for the dog size
        if kennelID is not None:  # If an available kennel is found
            reservationID = str(
                uuid.uuid4()
            )  # Generate a unique ID for the reservation
            self.book_kennel(storeID, int(kennelID))  # Book the kennel
            reservationTime = round(
                time.time()
            )  # Get the current time as the reservation time
            unlockCode = next(
                (
                    kennel["UnlockCode"]
                    for kennel in store["Kennels"]
                    if kennel["ID"] == kennelID
                ),
                None,
            )  # Get the unlock code for the kennel
            user = self.get_user(userID)  # Get user details from the catalog service
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
            )  # Add the reservation to the reservations list
            self.save_reservations()  # Save the reservations to the file
            self.get_stores()  # Refresh the store settings
            return json.dumps(
                {
                    "status": "confirmed",
                    "kennelID": kennelID,
                    "reservationID": reservationID,
                    "timestamp": reservationTime,
                    "message": f"Reservation confirmed for dog {dogID})",
                }
            )
        raise cherrypy.HTTPError(
            404, "No available kennels"
        )  # If no available kennels are found, return an HTTP error

    def handle_unlock(self, data):
        """Handles the unlock request for a kennel."""
        dogID = data.get("dogID")
        userID = data.get("userID")
        dog_size = data.get("dog_size")
        kennelID = data.get("kennelID")
        code = data.get("unlockCode")

        if kennelID is not None:  # If a kennel ID is provided
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
            }  # Find the kennel that matches the provided ID and dog size
            if not tmp:  # If no matching kennel is found, return an HTTP error
                raise cherrypy.HTTPError(
                    404, "Kennel not compatible with dog size or not available"
                )

            storeID, kennel_info = list(tmp.items())[
                0
            ]  # Get the store ID and kennel info
            kennelID, unlockCode = (
                kennel_info  # Extract the kennel ID and unlock code from the kennel info
            )

            if (
                unlockCode != code
            ):  # If the provided unlock code does not match the kennel's unlock code
                raise cherrypy.HTTPError(401, "Invalid unlock code")

            reservationID = str(
                uuid.uuid4()
            )  # Generate a unique ID for the reservation
            self.occupy_kennel(storeID, int(kennelID))  # Occupy the kennel
            user = self.get_user(userID)  # Get user details from the catalog service
            reservationTime = round(
                time.time()
            )  # Get the current time as the reservation time
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
            )  # Add the reservation to the reservations list
            self.save_reservations()  # Save the reservations to the file
            self.get_stores()  # Refresh the store settings
            return json.dumps(
                {
                    "status": "confirmed",
                    "kennelID": kennelID,
                    "reservationID": reservationID,
                    "timestamp": reservationTime,
                    "message": f"Reservation confirmed for dog {dogID})",
                }
            )
        raise cherrypy.HTTPError(
            404, "No available kennels"
        )  # If no kennel ID is provided, return an HTTP error

    def handle_cancellation(self, reservationID):
        """Handles the cancellation of a reservation."""
        reservation = next(
            (
                res
                for res in self.reservations["reservation"]
                if (res["reservationID"]) == reservationID
            ),
            None,
        )  # Find the reservation by ID
        if reservation:  # If the reservation is found
            self.reservations["reservation"].remove(
                reservation
            )  # Remove the reservation from the list
            self.save_reservations()  # Save the updated reservations to the file
            message = {"message": "off"}
            self.publish(
                self.baseTopic + "/kennel1/leds/redled", message, 2
            )  # SHOULD BE f"kennel{kennelID}/leds/redled" but we have just one led per color. Turn off the red LED
            if reservation["active"]:  # If the reservation was active
                self.pending_reservations.append(
                    reservation
                )  # Add the reservation to pending reservations
                message = {"message": "on"}
                self.publish(
                    self.baseTopic + "/kennel1/leds/yellowled", message, 2
                )  # SHOULD BE f"kennel{kennelID}/leds/yellowled" but we have just one led per color. Turn on the yellow LED
                self.publish(
                    self.baseTopic + f"/kennel{reservation['kennelID']}/disinfect",
                    message,
                    2,
                )  # Notify the kennel to start disinfection
            else:  # If the reservation was not active
                self.free_kennel(reservation["storeID"], reservation["kennelID"])
            return json.dumps(
                {
                    "status": "cancelled",
                    "message": f"Reservation in kennel {reservation['kennelID']} cancelled",
                }
            )
        else:
            raise cherrypy.HTTPError(
                404, f"No reservation found for id {reservationID}"
            )

    def handle_activation(self, reservationID, unlockCode):
        """Handles the activation of a reservation."""
        reservation = next(
            (
                res
                for res in self.reservations["reservation"]
                if (res["reservationID"]) == reservationID
            ),
            None,
        )  # Find the reservation by ID
        if reservation:  # If the reservation is found
            if (
                reservation["unlockCode"] != unlockCode
            ):  # If the provided unlock code does not match the reservation's unlock code
                raise cherrypy.HTTPError(status=401, message="Invalid unlock code")
            self.occupy_kennel(
                reservation["storeID"], reservation["kennelID"]
            )  # Occupy the kennel
            reservation["active"] = True  # Set the reservation as active
            reservation["activationTime"] = round(
                time.time()
            )  # Set the activation time
            self.save_reservations()  # Save the updated reservations to the file
            self.get_stores()  # Refresh the store settings
            return json.dumps(
                {
                    "status": "active",
                    "message": f"Reservation in kennel {reservation['kennelID']} activated",
                }
            )
        else:
            raise cherrypy.HTTPError(
                404, f"No reservation found for id {reservationID}"
            )

    def book_kennel(self, storeID: int, kennel: int):
        """Books a kennel for a reservation."""
        headers = {
            "Authorization": "Bearer reservation_manager",
            "Content-Type": "application/json",
        }
        body = json.dumps(
            {"storeID": storeID, "kennel": kennel}
        )  # Prepare the request body with store ID and kennel number
        response = requests.post(
            f"{self.catalog_url}/book",
            headers=headers,
            data=body,
        )  # Send a request to book the kennel
        if response.ok:  # If the response is successful
            message = {"message": "off"}
            self.publish(
                self.baseTopic + "/kennel1/leds/greenled", message, 2
            )  # SHOULD BE "kennel{kennelID}/leds/greenled" but we have just one led per color. Turn off the green LED
            message = {"message": "on"}
            self.publish(
                self.baseTopic + "/kennel1/leds/yellowled", message, 2
            )  # SHOULD BE "kennel{kennelID}/leds/yellowled" but we have just one led per color. Turn on the yellow LED
            return json.loads(response.text)
        raise cherrypy.HTTPError(
            500, "Error booking kennel"
        )  # If the booking fails, return an HTTP error

    def free_kennel(self, storeID: int, kennel: int):
        """Frees a booked kennel."""
        headers = {
            "Authorization": "Bearer reservation_manager",
            "Content-Type": "application/json",
        }
        body = json.dumps({"storeID": storeID, "kennel": kennel})
        response = requests.post(
            f"{self.catalog_url}/free",
            headers=headers,
            data=body,
        )  # Send a request to free the kennel
        if response.ok:  # If the response is successful
            message = {"message": "off"}
            self.publish(
                self.baseTopic + "/kennel1/leds/yellowled", message, 2
            )  # SHOULD BE "kennel{kennelID}/leds/yellowled" but we have just one led per color. Turn off the yellow LED
            message = {"message": "on"}
            self.publish(
                self.baseTopic + "/kennel1/leds/greenled", message, 2
            )  # SHOULD BE f"kennel{kennelID}/leds/greenled" but we have just one led per color. Turn on the green LED
            return json.loads(response.text)
        raise cherrypy.HTTPError(
            500, "Error unlocking kennel"
        )  # If the freeing fails, return an HTTP error

    def occupy_kennel(self, storeID: int, kennel: int):
        """Occupies a booked kennel."""
        headers = {
            "Authorization": "Bearer reservation_manager",
            "Content-Type": "application/json",
        }
        body = json.dumps({"storeID": storeID, "kennel": kennel})
        response = requests.post(
            f"{self.catalog_url}/lock",
            headers=headers,
            data=body,
        )  # Send a request to occupy the kennel
        if response.ok:  # If the response is successful
            message = {"message": "off"}
            self.publish(
                self.baseTopic + "/kennel1/leds/greenled", message, 2
            )  # SHOULD BE "kennel{kennelID}/leds/greenled" but we have just one led per color. Turn off the green LED
            self.publish(
                self.baseTopic + "/kennel1/leds/yellowled", message, 2
            )  # SHOULD BE "kennel{kennelID}/leds/yellowled" but we have just one led per color. Turn off the yellow LED
            message = {"message": "on"}
            self.publish(
                self.baseTopic + "/kennel1/leds/redled", message, 2
            )  # SHOULD BE "kennel{kennelID}/leds/redled" but we have just one led per color. Turn on the red LED
            return json.loads(response.text)
        raise cherrypy.HTTPError(
            500, "Error unlocking kennel"
        )  # If the occupation fails, return an HTTP error

    def check_expiry(self):
        """Checks for expiring or expired reservations and sends notifications."""
        while True:
            current_time = round(time.time())  # Get the current time in seconds
            if self.reservations:  # Check if there are any reservations
                for reservation in self.reservations[
                    "reservation"
                ]:  # Iterate through each reservation
                    if (
                        current_time - reservation["reservationTime"] > 1800
                        and not reservation["active"]
                    ):  # 30 minutes passed
                        self.handle_cancellation(
                            reservation["reservationID"]
                        )  # Cancel the reservation if it has expired
                        for token in reservation[
                            "firebaseTokens"
                        ]:  # Send notification to the user at each of their app instances
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
                        for token in reservation[
                            "firebaseTokens"
                        ]:  # Send notification to the user at each of their app instances
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
        auth_header = cherrypy.request.headers.get(
            "Authorization"
        )  # Get the Authorization header from the request
        if (
            not auth_header
        ):  # If the Authorization header is not present, return an HTTP error
            raise cherrypy.HTTPError(401, "Authorization token required")
        token = auth_header.split(" ")[
            1
        ]  # Extract the token from the Authorization header
        self.verify_token(token)  # Verify the token
        body = cherrypy.request.body.read()
        data = json.loads(body)
        if uri[0] == "reserve":  # If the request is for reservation
            return self.handle_reservation(data)  # Handle the reservation request
        if uri[0] == "unlock":  # If the request is for unlocking a kennel
            return self.handle_unlock(data)  # Handle the unlock request
        if uri[0] == "activate":  # If the request is for activating a reservation
            if (
                len(uri) < 2
            ):  # If the reservation ID is not provided, return an HTTP error
                raise cherrypy.HTTPError(400, "Reservation ID required")
            reservationID = uri[1]
            return self.handle_activation(
                reservationID, data["unlockCode"]
            )  # Handle the activation request
        else:
            raise cherrypy.HTTPError(
                404, "Endpoint not found"
            )  # If the endpoint is not found, return an HTTP error

    def GET(self, *uri):
        auth_header = cherrypy.request.headers.get(
            "Authorization"
        )  # Get the Authorization header from the request
        if (
            not auth_header
        ):  # If the Authorization header is not present, return an HTTP error
            raise cherrypy.HTTPError(401, "Authorization token required")
        token = auth_header.split(" ")[
            1
        ]  # Extract the token from the Authorization header
        self.verify_token(token)  # Verify the token
        if uri[0] == "status":  # If the request is for status
            if len(uri) > 1:  # If a user ID is provided
                reservations = [
                    res
                    for res in self.reservations["reservation"]
                    if res["userID"] == uri[1]
                ]
                return json.dumps(reservations)  # Return the reservations for the user
            return json.dumps(
                self.reservations["reservation"]
            )  # Return all reservations
        else:
            raise cherrypy.HTTPError(
                404, "Endpoint not found"
            )  # If the endpoint is not found, return an HTTP error

    def DELETE(self, *uri):
        auth_header = cherrypy.request.headers.get(
            "Authorization"
        )  # Get the Authorization header from the request
        if (
            not auth_header
        ):  # If the Authorization header is not present, return an HTTP error
            raise cherrypy.HTTPError(401, "Authorization token required")
        token = auth_header.split(" ")[
            1
        ]  # Extract the token from the Authorization header
        self.verify_token(token)  # Verify the token
        if uri[0] == "cancel":  # If the request is for cancellation
            reservationID = uri[1]
            return self.handle_cancellation(
                reservationID
            )  # Handle the cancellation request
        raise cherrypy.HTTPError(
            404, "Endpoint not found"
        )  # If the endpoint is not found, return an HTTP error

    def heartbeat(self):
        """Sends a heartbeat signal to the catalog service to indicate that the reservation manager is active."""
        while True:
            try:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer reservation_manager",
                }
                url = self.catalog_url + "/heartbeat"
                payload = {
                    "category": "service",
                    "serviceID": self.serviceID,
                }
                response = requests.post(
                    url, headers=headers, data=json.dumps(payload)
                )  # Send a POST request to the catalog service
                if response.status_code == 200:  # If the response is successful
                    print("Heartbeat sent successfully")
                else:
                    print("Failed to send heartbeat")
            except requests.exceptions.RequestException as e:
                print(f"Error sending heartbeat: {e}")
            time.sleep(60)  # Wait for 60 seconds before sending the next heartbeat


if __name__ == "__main__":
    # Load settings and initialize the manager
    settings = json.load(open("mqtt_settings.json"))
    manager = ReservationManager(
        "reservation.json",
        "ReservationManager",
        settings["broker"],
        settings["port"],
        settings["baseTopic"],
        1,
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

    check_expiry_thread = threading.Thread(
        target=manager.check_expiry
    )  # Thread to check for expired reservations
    check_expiry_thread.daemon = True  # Il thread terminerà quando il programma termina
    check_expiry_thread.start()  # Start the thread to check for expired reservations

    heartbeat_thread = threading.Thread(
        target=manager.heartbeat
    )  # Thread to send heartbeat signals
    heartbeat_thread.daemon = True  # The thread will terminate when the program ends
    heartbeat_thread.start()  # Start the heartbeat for the reservation manager

    cherrypy.tree.mount(
        manager, "/", conf
    )  # Mount the ReservationManager class to the root URL
    cherrypy.config.update(
        {"server.socket_host": ip}
    )  # Set the server socket host to the local IP address
    cherrypy.config.update(
        {"server.socket_port": 8083}
    )  # Set the server socket port to 8083
    cherrypy.engine.start()  # Start the CherryPy engine to handle requests
    manager.start()  # Start the MQTT client
    manager.subscribe(
        settings["baseTopic"] + "/+/status", 2
    )  # Subscribe to status updates for all kennels
    cherrypy.engine.block()  # Block the main thread to keep the server running
    manager.stop()  # Stop the MQTT client when the server is stopped
