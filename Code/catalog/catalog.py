import cherrypy
import json
import time
import os
import socket
import bcrypt
import uuid
import jwt
import datetime
from dotenv import load_dotenv
import secrets
import string
import requests
import shutil
from cherrypy.lib import static
import threading


class Catalog:
    exposed = True

    def __init__(self):
        self.catalog_data = self.load_catalog()
        with open("secret_key.txt") as f:
            self.secret_key = f.read()
        load_dotenv()  # for reading API key from `.env` file.
        self.codes = []

    def generate_token(self, user_id, role):
        expiration_time = datetime.datetime.now(
            datetime.timezone.utc
        ) + datetime.timedelta(hours=1)
        token = jwt.encode(
            {"user_id": user_id, "role": role, "exp": expiration_time},
            self.secret_key,
            algorithm="HS256",
        )
        return token

    def verify_token(self, token):
        if token in [
            "reservation_manager",
            "data_analysis",
            "temp_humid_sensor",
            "motion_sensor",
            "led_connector",
            "camera",
            "thingspeak_adaptor",
            "disinfection_system",
        ]:
            return token
        try:
            decoded = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            return decoded
        except jwt.ExpiredSignatureError:
            raise cherrypy.HTTPError(401, "Token has expired")
        except jwt.InvalidTokenError:
            raise cherrypy.HTTPError(401, "Invalid token")

    def load_catalog(self):
        try:
            with open("catalog.json") as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "broker": {},
                "Breeds": [],
                "Devices": [],
                "Users": [],
                "Dogs": [],
                "Kennels": [],
                "Bookings": [],
                "Services": [],
            }

    def save_catalog(self):
        try:
            with open("catalog.json", "w") as f:
                json.dump(self.catalog_data, f, indent=4)
        except IOError as e:
            print(f"Error saving catalog: {e}")

    def register(self, email):
        email_list = [user["Email"] for user in self.catalog_data["Users"]]
        if email in email_list:
            raise cherrypy.HTTPError(400, "Email already exists")
        secure_code = self.generate_secure_code()
        api_key = os.getenv("MAILGUN_API_KEY")  # Read the API key from .env file
        api_url = os.getenv("MAILGUN_API_URL")  # Read the API URL from .env file
        from_address = os.getenv(
            "FROM_EMAIL_ADDRESS"
        )  # Read the sender email from .env file
        response = requests.post(
            api_url,
            auth=("api", api_key),
            data={
                "from": from_address,
                "to": email,
                "subject": "IoTail registration code",
                "text": f"Dear user,\nuse this code to confirm your registration: {secure_code}",
            },
        )
        if response.status_code == 200:
            self.codes.append({"email": email, "code": secure_code})
            return json.dumps(
                {
                    "status": "success",
                    "message": "Confirm registration email sent",
                }
            )
        raise cherrypy.HTTPError(500, "Error sending confirm registration email")

    def confirm_registration(self, body):
        email = body["email"]
        registration_code = body["registration_code"]
        if not self.verify_code(email, registration_code):
            raise cherrypy.HTTPError(401, "Invalid registration code")
        hashed_password = bcrypt.hashpw(
            body["password"].encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        userID = str(uuid.uuid4())
        self.catalog_data["Users"].append(
            {
                "UserID": userID,
                "Name": body["name"],
                "Email": email,
                "Password": hashed_password,
                "PhoneNumber": body["phone"],
                "ProfilePicture": None,
                "FirebaseTokens": [body["firebaseToken"]],
                "Dogs": [],
            }
        )
        self.save_catalog()
        role = body.get("role", "Client")  # Default role is "client"
        token = self.generate_token(userID, role)
        api_key = os.getenv("MAILGUN_API_KEY")  # Read the API key from .env file
        api_url = os.getenv("MAILGUN_API_URL")  # Read the API URL from .env file
        from_address = os.getenv(
            "FROM_EMAIL_ADDRESS"
        )  # Read the sender email from .env file
        requests.post(
            api_url,
            auth=("api", api_key),
            data={
                "from": from_address,
                "to": email,
                "subject": "Welcome to IoTail",
                "text": f"Dear user,\nwe welcome you to IoTail. Enjoy our services!",
            },
        )
        return json.dumps(
            {
                "status": "success",
                "message": f"User {email} successfully registered",
                "token": token,
                "userID": userID,
            }
        )

    @staticmethod
    def generate_secure_code(length=8):
        characters = string.ascii_letters + string.digits
        return "".join(secrets.choice(characters) for _ in range(length))

    def verify_code(self, email, code):
        for i, entry in enumerate(self.codes):
            if entry["email"] == email and entry["code"] == code:
                del self.codes[i]
                return True
        return False

    def login(self, body):
        user = next(
            (u for u in self.catalog_data["Users"] if u["Email"] == body["email"]),
            None,
        )
        if user and bcrypt.checkpw(
            body["password"].encode("utf-8"), user["Password"].encode("utf-8")
        ):
            role = user.get("Role", "client")  # Default role is "client"
            token = self.generate_token(user["UserID"], role)
            firebaseToken = body.get("firebaseToken", None)
            if (
                firebaseToken is not None
                and firebaseToken not in user["FirebaseTokens"]
            ):
                user["FirebaseTokens"].append(body["firebaseToken"])
                self.save_catalog()
            return json.dumps(
                {
                    "status": "success",
                    "message": f"User {body['email']} successfully logged in",
                    "token": token,
                    "userID": user["UserID"],
                }
            )
        raise cherrypy.HTTPError(401, "Invalid credentials")

    def logout(self, userID, firebaseToken):
        user = next(
            (u for u in self.catalog_data["Users"] if u["UserID"] == userID),
            None,
        )
        if not user:
            raise cherrypy.HTTPError(404, "User not found")
        if firebaseToken in user["FirebaseTokens"]:
            user["FirebaseTokens"].remove(firebaseToken)
        self.save_catalog()
        return json.dumps(
            {
                "status": "success",
                "message": f"User {userID} logged out",
            }
        )

    def recover_password(self, body):
        user = next(
            (u for u in self.catalog_data["Users"] if u["Email"] == body["email"]),
            None,
        )
        if user:
            secure_code = self.generate_secure_code()
            api_key = os.getenv("MAILGUN_API_KEY")  # Read the API key from .env file
            api_url = os.getenv("MAILGUN_API_URL")  # Read the API URL from .env file
            from_address = os.getenv(
                "FROM_EMAIL_ADDRESS"
            )  # Read the sender email from .env file
            response = requests.post(
                api_url,
                auth=("api", api_key),
                data={
                    "from": from_address,
                    "to": user["Email"],
                    "subject": "IoTail password recovery",
                    "text": f"Dear user,\nuse this code to recover your password: {secure_code}",
                },
            )
            if response.status_code == 200:
                self.codes.append({"email": user["Email"], "code": secure_code})
                return json.dumps(
                    {
                        "status": "success",
                        "message": "Password recovery email sent",
                    }
                )
            raise cherrypy.HTTPError(500, "Error sending recovery email")
        raise cherrypy.HTTPError(404, "User not found")

    def reset_password(self, body):
        email = body["email"]
        recovery_code = body["recovery_code"]
        password = body["password"]

        if not self.verify_code(email, recovery_code):
            raise cherrypy.HTTPError(401, "Invalid recovery code")
        user = next(
            (u for u in self.catalog_data["Users"] if u["Email"] == email),
            None,
        )
        if user:
            user["Password"] = bcrypt.hashpw(
                password.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")
            self.save_catalog()
            api_key = os.getenv("MAILGUN_API_KEY")  # Read the API key from .env file
            api_url = os.getenv("MAILGUN_API_URL")  # Read the API URL from .env file
            from_address = os.getenv(
                "FROM_EMAIL_ADDRESS"
            )  # Read the sender email from .env file
            requests.post(
                api_url,
                auth=("api", api_key),
                data={
                    "from": from_address,
                    "to": user["Email"],
                    "subject": "IoTail password reset successful",
                    "text": f"Dear user,\nyour password has been successfully reset",
                },
            )
            return json.dumps(
                {
                    "status": "success",
                    "message": "Password reset successfully",
                }
            )
        raise cherrypy.HTTPError(404, "User not found")

    def edit_user(self, userID, body, file):
        # Find the user by ID
        user = next(
            (u for u in self.catalog_data["Users"] if u["UserID"] == userID),
            None,
        )
        if not user:
            raise cherrypy.HTTPError(404, "User not found")

        # Update user details from the JSON body
        user["Name"] = body["name"]
        user["Email"] = body["email"]
        user["PhoneNumber"] = body["phoneNumber"]

        # Handle profile picture file
        if file:
            profile_pictures_dir = "profile_pictures"
            os.makedirs(
                profile_pictures_dir, exist_ok=True
            )  # Ensure the directory exists
            file_path = os.path.join(profile_pictures_dir, f"{userID}_profile.jpg")
            with open(file_path, "wb") as f:
                shutil.copyfileobj(file, f)
            user["ProfilePicture"] = file_path  # Save the relative path

        # Save updated catalog
        self.save_catalog()

        return json.dumps(
            {
                "status": "success",
                "message": f"User {userID} updated",
            }
        )

    def add_dog(self, userID, body, picture):
        dogID = str(uuid.uuid4())
        user = next(
            (u for u in self.catalog_data["Users"] if u["UserID"] == userID),
            None,
        )
        if not user:
            raise cherrypy.HTTPError(404, "User not found")
        names = [d["Name"] for d in user["Dogs"]]
        if body["name"] in names:
            raise cherrypy.HTTPError(
                400, f"Dog with name {body['name']} already exists for user {userID}"
            )
        body = {
            key[0].upper() + key[1:]: val for key, val in body.items()
        }  # Capitalize only first letter of the key without touching the others
        body["DogID"] = dogID
        if picture:
            dog_pictures_dir = "dog_pictures"
            os.makedirs(dog_pictures_dir, exist_ok=True)  # Ensure the directory exists
            file_path = os.path.join(dog_pictures_dir, f"{userID}_{dogID}_dog.jpg")
            with open(file_path, "wb") as f:
                shutil.copyfileobj(picture, f)
            body["Picture"] = file_path  # Save the relative path
        else:
            body["Picture"] = None
        user["Dogs"].append(body)
        self.save_catalog()
        return json.dumps(
            {"status": "success", "message": f"Dog added to user {userID}"}
        )

    def edit_dog(self, userID, dogID, body, file):
        # Find the user by ID
        user = next(
            (u for u in self.catalog_data["Users"] if u["UserID"] == userID),
            None,
        )
        if not user:
            raise cherrypy.HTTPError(404, "User not found")

        dog = next(
            (d for d in user["Dogs"] if d["DogID"] == dogID),
            None,
        )
        if not dog:
            raise cherrypy.HTTPError(404, "Dog not found")

        # Update dog details from the JSON body
        dog["Name"] = body["name"]
        dog["Age"] = body["age"]
        dog["Sex"] = body["sex"]
        dog["Size"] = body["size"]
        dog["Weight"] = body["weight"]
        dog["CoatType"] = body["coatType"]
        dog["Allergies"] = body["allergies"]

        if dog["BreedID"] == 0:
            if body["breedID"] == 0:
                dog["MinIdealTemperature"] = body["minIdealTemperature"]
                dog["MaxIdealTemperature"] = body["maxIdealTemperature"]
                dog["MinIdealHumidity"] = body["minIdealHumidity"]
                dog["MaxIdealHumidity"] = body["maxIdealHumidity"]
            else:
                del dog["MinIdealTemperature"]
                del dog["MaxIdealTemperature"]
                del dog["MinIdealHumidity"]
                del dog["MaxIdealHumidity"]

        dog["BreedID"] = body["breedID"]

        # Handle profile picture file
        if file:
            dog_pictures_dir = "dog_pictures"
            os.makedirs(dog_pictures_dir, exist_ok=True)  # Ensure the directory exists
            file_path = os.path.join(dog_pictures_dir, f"{userID}_{dogID}_dog.jpg")
            with open(file_path, "wb") as f:
                shutil.copyfileobj(file, f)
            dog["Picture"] = file_path  # Save the relative path

        # Save updated catalog
        self.save_catalog()

        return json.dumps(
            {
                "status": "success",
                "message": f"Dog {dogID} of user {userID} updated",
            }
        )

    def delete_dog(self, userID, dogID):
        user = next(
            user for user in self.catalog_data["Users"] if user["UserID"] == userID
        )
        if not user:
            return json.dumps(
                {"status": "error", "message": f"User {userID} not found"}
            )
        dog = next(
            (d for d in user["Dogs"] if d["DogID"] == dogID),
            None,
        )
        if not dog:
            raise cherrypy.HTTPError(404, "Dog not found")
        if dog["Picture"]:
            os.remove(dog["Picture"])
        user["Dogs"] = [d for d in user["Dogs"] if d["DogID"] != dogID]
        self.save_catalog()
        return json.dumps(
            {"status": "success", "message": f"Dog {dogID} of User {userID} deleted"}
        )

    def book_kennel(self, body):
        storeID = body["storeID"]
        kennel = body["kennel"]

        store = next(
            (
                store
                for store in self.catalog_data["Stores"]
                if store["StoreID"] == storeID
            ),
            None,
        )
        if store:
            k = next((k for k in store["Kennels"] if k["ID"] == kennel), None)
            if k:
                k["Booked"] = True
                self.save_catalog()
                return json.dumps({"status": "success", "message": "Kennel booked"})
            raise cherrypy.HTTPError(404, "Kennel not found")
        raise cherrypy.HTTPError(404, "Store not found")

    def lock_kennel(self, body):
        storeID = body["storeID"]
        kennel = body["kennel"]
        store = next(
            (s for s in self.catalog_data["Stores"] if s["StoreID"] == storeID),
            None,
        )
        if store:
            kennel = next(
                (k for k in store["Kennels"] if k["ID"] == kennel),
                None,
            )
            if kennel:
                kennel["Occupied"] = True
                self.save_catalog()
                return json.dumps({"status": "success", "message": "Kennel locked"})
            raise cherrypy.HTTPError(404, "Kennel not found")
        raise cherrypy.HTTPError(404, "Store not found")

    def free_kennel(self, body):
        storeID = body["storeID"]
        kennel = body["kennel"]
        store = next(
            (s for s in self.catalog_data["Stores"] if s["StoreID"] == storeID),
            None,
        )
        if store:
            kennel = next(
                (k for k in store["Kennels"] if k["ID"] == kennel),
                None,
            )
            if kennel:
                kennel["Occupied"] = False
                kennel["Booked"] = False
                self.save_catalog()
                return json.dumps({"status": "success", "message": "Kennel freed"})
            raise cherrypy.HTTPError(404, "Kennel not found")
        raise cherrypy.HTTPError(404, "Store not found")

    def GET(self, *uri, **params):
        auth_header = cherrypy.request.headers.get("Authorization")
        if not auth_header:
            # Allow access to status_page without token for simplicity, or add specific token check
            if not (len(uri) > 0 and uri[0] == "status_page"):
                raise cherrypy.HTTPError(401, "Authorization token required")
        else:
            token = auth_header.split(" ")[1]
            self.verify_token(token)  # Verify the token for other routes

        if len(uri) == 0:
            return json.dumps(self.catalog_data)
        elif uri[0] == "broker":
            return json.dumps(self.catalog_data["broker"])
        elif uri[0] == "devices":
            return json.dumps(self.catalog_data["Devices"])
        elif uri[0] == "services":
            return json.dumps(
                self.catalog_data.get("Services", [])
            )  # Modificato da serviceList a Services
        elif uri[0] == "stores":
            return json.dumps(self.catalog_data["Stores"])
        elif uri[0] == "breeds":
            return json.dumps(self.catalog_data["Breeds"])
        elif uri[0] == "users":
            if len(uri) > 1:
                user = next(
                    (u for u in self.catalog_data["Users"] if u["UserID"] == uri[1]),
                    None,
                )
                if not user:
                    raise cherrypy.HTTPError(404, "User not found")

                return json.dumps(
                    {key: val for key, val in user.items() if key != "Password"}
                )
            return json.dumps(self.catalog_data["Users"])
        elif uri[0] == "profile_picture":
            if len(uri) < 2:
                raise cherrypy.HTTPError(400, "Bad request, add userID")
            user = next(
                (u for u in self.catalog_data["Users"] if u["UserID"] == uri[1]),
                None,
            )
            if not user:
                raise cherrypy.HTTPError(404, "User not found")
            if not user["ProfilePicture"]:
                return None
            return static.serve_file(
                "/app/" + user["ProfilePicture"],
                content_type="image/jpg",
                disposition="attachment",
                name=user["ProfilePicture"].split("/")[-1],
            )
        elif uri[0] == "dog_picture":
            if len(uri) < 3:
                raise cherrypy.HTTPError(400, "Bad request, use userID and dogID")
            user = next(
                (u for u in self.catalog_data["Users"] if u["UserID"] == uri[1]),
                None,
            )
            if not user:
                raise cherrypy.HTTPError(404, "User not found")
            dog = next(
                (d for d in user["Dogs"] if d["DogID"] == uri[2]),
                None,
            )
            if not dog:
                raise cherrypy.HTTPError(404, "Dog not found")
            if not dog["Picture"]:
                return None
            return static.serve_file(
                "/app/" + dog["Picture"],
                content_type="image/jpg",
                disposition="attachment",
                name=dog["Picture"].split("/")[-1],
            )
        elif uri[0] == "status_page":
            cherrypy.response.headers["Content-Type"] = "text/html"
            html = """
            <html>
            <head>
                <title>Status Page</title>
                <style>
                    .status-circle {
                        height: 15px;
                        width: 15px;
                        border-radius: 50%;
                        display: inline-block;
                        margin-right: 10px;
                    }
                    .green { background-color: green; }
                    .red { background-color: red; }
                    body { font-family: Arial, sans-serif; margin: 20px; }
                    h1 { color: #333; }
                    h2 { color: #555; border-bottom: 1px solid #eee; padding-bottom: 5px;}
                    ul { list-style-type: none; padding-left: 0; }
                    li { margin-bottom: 8px; padding: 5px; border: 1px solid #ddd; border-radius: 4px; background-color: #f9f9f9; display: flex; align-items: center;}
                    .details { margin-left: 10px; }
                </style>

            </head>
            <body>
                <h1>System Status</h1>
            """

            html += "<h2>Devices</h2><ul>"
            if "Devices" in self.catalog_data and self.catalog_data["Devices"]:
                for device in self.catalog_data["Devices"]:
                    device_id = device.get("DeviceID", "N/A")
                    device_name = device.get("Name", f"DefaultNameForID_{device_id}")
                    available_status = device.get("Available", False)

                    status_color = "green" if available_status else "red"
                    html += f"""<li>
                                    <span class='status-circle {status_color}'></span>
                                    <div class='details'>
                                        ID: {device_id}, Name: {device_name}
                                    </div>
                                </li>"""
            else:
                html += "<li>No devices registered.</li>"
            html += "</ul>"

            html += "<h2>Services</h2><ul>"
            service_list_items = self.catalog_data.get("Services", [])
            if service_list_items:
                for service in service_list_items:
                    service_id = service.get("ServiceID", "N/A")
                    service_name = service.get("Name", f"DefaultNameForID_{service_id}")
                    available_status = service.get("Available", False)

                    status_color = "green" if available_status else "red"
                    html += f"""<li>
                                    <span class='status-circle {status_color}'></span>
                                    <div class='details'>
                                        ID: {service_id}, Name: {service_name}
                                    </div>
                                </li>"""
            else:
                html += "<li>No services registered.</li>"
            html += "</ul>"

            html += """
            </body>
            </html>
            """
            return html
        else:
            raise cherrypy.HTTPError(404, "Resource not found")

    def POST(self, *uri, **params):
        # Routes that do not require authentication
        public_routes = ["register", "login", "recover", "confirm_registration"]

        # Check if the route is public
        if uri[0] not in public_routes:
            # Enforce authentication for all other POST routes
            auth_header = cherrypy.request.headers.get("Authorization")
            if not auth_header:
                raise cherrypy.HTTPError(401, "Authorization token required")
            token = auth_header.split(" ")[1]
            self.verify_token(token)  # Verify the token

        if cherrypy.request.headers.get("Content-Type", "").startswith(
            "application/json"
        ):
            # Handle specific POST routes
            body = cherrypy.request.body.read()
            json_body = json.loads(body)

        if uri[0] == "register":
            return self.register(json_body["email"])
        elif uri[0] == "confirm_registration":
            return self.confirm_registration(json_body)
        elif uri[0] == "login":
            return self.login(json_body)
        elif uri[0] == "logout":
            return self.logout(json_body["userID"], json_body["firebaseToken"])
        elif uri[0] == "book":
            return self.book_kennel(json_body)
        elif uri[0] == "lock":
            return self.lock_kennel(json_body)
        elif uri[0] == "free":
            return self.free_kennel(json_body)
        elif uri[0] == "dogs":
            if len(uri) == 1:
                raise cherrypy.HTTPError(400, "Bad request, add userID")
            userID = uri[1]
            if cherrypy.request.headers.get("Content-Type", "").startswith(
                "multipart/form-data"
            ):
                fields = cherrypy.request.body.params
                dog_data_field = fields.get("dogData")
                dog_picture_field = fields.get("dogPicture")

                if not dog_data_field:
                    raise cherrypy.HTTPError(400, "dogData is required")

                dog_data = json.loads(dog_data_field)

                dog_picture = None
                if dog_picture_field:
                    dog_picture = dog_picture_field.file
                return self.add_dog(userID, dog_data, dog_picture)
            elif cherrypy.request.headers.get("Content-Type", "").startswith(
                "application/json"
            ):
                return self.add_dog(userID, json_body, None)
        elif uri[0] == "recover":
            return self.recover_password(json_body)
        elif uri[0] == "devices":
            self.catalog_data["Devices"].append(json_body)
            self.save_catalog()
            return json.dumps({"status": "success", "message": "Device added"})
        elif uri[0] == "services":
            self.catalog_data.setdefault("Services", []).append(
                json_body
            )  # Modificato da serviceList a Services
            self.save_catalog()
            return json.dumps({"status": "success", "message": "Service added"})
        elif uri[0] == "heartbeat":
            # Handle heartbeat
            category = json_body.get("category", None)
            if not category:
                raise cherrypy.HTTPError(400, "Category is required")
            if category == "sensor":
                device_id = json_body["deviceID"]
                device = next(
                    (
                        d
                        for d in self.catalog_data["Devices"]
                        if d["DeviceID"] == device_id
                    ),
                    None,
                )
                if not device:
                    raise cherrypy.HTTPError(404, "Device not found")
                device["LastAvailable"] = time.time()
                device["Available"] = True
            elif category == "service":
                service_id = json_body.get("serviceID")
                service = next(
                    (
                        s
                        for s in self.catalog_data.get(
                            "Services", []  # Modificato da serviceList a Services
                        )
                        if s.get("ServiceID") == service_id
                    ),
                    None,
                )
                if not service:
                    raise cherrypy.HTTPError(
                        404,
                        f"Service with ID {service_id} not found in Services",  # Messaggio aggiornato
                    )
                service["LastAvailable"] = time.time()
                service["Available"] = True
            else:
                raise cherrypy.HTTPError(400, "Invalid category")
            self.save_catalog()
            return json.dumps({"status": "success", "message": "Heartbeat received"})
        else:
            raise cherrypy.HTTPError(400, "Bad request")

    def PUT(self, *uri, **params):
        # Routes that do not require authentication
        public_routes = ["reset_password"]

        # Check if the route is public
        if uri[0] not in public_routes:
            # Enforce authentication for all other POST routes
            auth_header = cherrypy.request.headers.get("Authorization")
            if not auth_header:
                raise cherrypy.HTTPError(401, "Authorization token required")
            token = auth_header.split(" ")[1]
            self.verify_token(token)  # Verify the token

        if cherrypy.request.headers.get("Content-Type", "").startswith(
            "application/json"
        ):
            body = cherrypy.request.body.read()
            json_body = json.loads(body)

        if uri[0] == "devices":
            # Modificato per usare "Devices" invece di "deviceList"
            device_id_to_update = json_body.get("DeviceID")
            if device_id_to_update is None:
                raise cherrypy.HTTPError(
                    400, "DeviceID is required in request body for update"
                )

            devices = self.catalog_data.get("Devices", [])
            found = False
            for i, device in enumerate(devices):
                if device.get("DeviceID") == device_id_to_update:
                    self.catalog_data["Devices"][i] = json_body
                    found = True
                    break
            if not found:
                # Opzionale: gestire il caso in cui il dispositivo non viene trovato
                # Potrebbe essere un errore 404 o si potrebbe aggiungere il dispositivo
                raise cherrypy.HTTPError(
                    404, f"Device with ID {device_id_to_update} not found"
                )

        elif uri[0] == "services":
            service_id_to_update = json_body.get(
                "serviceID"
            )  # Assumendo che il JSON in input usi "serviceID"
            if service_id_to_update is None:
                raise cherrypy.HTTPError(
                    400, "serviceID is required in request body for update"
                )

            services = self.catalog_data.get(
                "Services", []
            )  # Modificato da serviceList a Services
            found = False
            for i, service in enumerate(services):
                if service.get("ServiceID") == service_id_to_update:
                    self.catalog_data["Services"][
                        i
                    ] = json_body  # Modificato da serviceList a Services
                    found = True
                    break
            if not found:
                raise cherrypy.HTTPError(
                    404, f"Service with ID {service_id_to_update} not found"
                )
        elif uri[0] == "users":
            if len(uri) < 2:
                raise cherrypy.HTTPError(400, "UserID is required")

            userID = uri[1]

            # Check for multipart data
            if cherrypy.request.headers.get("Content-Type", "").startswith(
                "multipart/form-data"
            ):
                fields = cherrypy.request.body.params
                user_data_field = fields.get("userData")
                profile_picture_field = fields.get("profilePicture")

                if not user_data_field:
                    raise cherrypy.HTTPError(400, "userData is required")

                user_data = json.loads(user_data_field)

                profile_picture = None
                if profile_picture_field:
                    profile_picture = profile_picture_field.file

                # Call edit_user with or without profile picture
                return self.edit_user(userID, user_data, profile_picture)
            elif cherrypy.request.headers.get("Content-Type", "").startswith(
                "application/json"
            ):
                return self.edit_user(userID, json_body, None)
            else:
                raise cherrypy.HTTPError(
                    400, "Expected multipart/form-data or application/json request"
                )
        elif uri[0] == "dogs":
            if len(uri) < 3:
                raise cherrypy.HTTPError(400, "UserID and dogID is required")

            userID = uri[1]
            dogID = uri[2]

            # Check for multipart data
            if cherrypy.request.headers.get("Content-Type", "").startswith(
                "multipart/form-data"
            ):
                fields = cherrypy.request.body.params
                dog_data_field = fields.get("dogData")
                dog_picture_field = fields.get("dogPicture")

                if not dog_data_field:
                    raise cherrypy.HTTPError(400, "dogData is required")

                dog_data = json.loads(dog_data_field)

                dog_picture = None
                if dog_picture_field:
                    dog_picture = dog_picture_field.file

                # Call edit_user with or without profile picture
                return self.edit_dog(userID, dogID, dog_data, dog_picture)
            elif cherrypy.request.headers.get("Content-Type", "").startswith(
                "application/json"
            ):
                return self.edit_dog(userID, dogID, json_body, None)
            else:
                raise cherrypy.HTTPError(
                    400, "Expected multipart/form-data or application/json request"
                )
        elif uri[0] == "reset_password":
            return self.reset_password(json_body)
        else:
            raise cherrypy.HTTPError(400, "Bad request")

        self.save_catalog()
        return "200 OK"

    def DELETE(self, *uri, **params):
        if uri[0] == "dogs":
            # DEL request at IP:8080/dogs/userID/dogID
            if len(uri) < 3:
                raise cherrypy.HTTPError(400, "Bad request, use both userID and dogID")
            return self.delete_dog(uri[1], uri[2])
        elif uri[0] == "users":
            # DEL request at IP:8080/users/userID
            if len(uri) < 2:
                raise cherrypy.HTTPError(400, "Bad request, use userID")
            user_id = uri[1]
            user = next(
                user for user in self.catalog_data["Users"] if user["UserID"] == user_id
            )
            if not user:
                return json.dumps(
                    {"status": "error", "message": f"User {uri[1]} not found"}
                )
            if user["ProfilePicture"]:
                os.remove(user["ProfilePicture"])
            self.catalog_data["Users"] = [
                u for u in self.catalog_data["Users"] if u["UserID"] != user_id
            ]
            self.save_catalog()
            return json.dumps(
                {"status": "success", "message": f"User {uri[1]} deleted"}
            )
        elif uri[0] == "profile_picture":
            # DEL request at IP:8080/profile_picture/userID
            if len(uri) < 2:
                raise cherrypy.HTTPError(400, "Bad request, use userID")
            user_id = uri[1]
            user = next(
                user for user in self.catalog_data["Users"] if user["UserID"] == user_id
            )
            if user:
                if user["ProfilePicture"]:
                    os.remove(user["ProfilePicture"])
                user["ProfilePicture"] = None
                self.save_catalog()
                return json.dumps(
                    {"status": "success", "message": "Profile picture deleted"}
                )
            return json.dumps(
                {"status": "error", "message": f"User {uri[1]} not found"}
            )
        elif uri[0] == "dog_picture":
            # DEL request at IP:8080/dog_picture/userID/dogID
            if len(uri) < 3:
                raise cherrypy.HTTPError(400, "Bad request, use userID and dogID")
            user_id = uri[1]
            dog_id = uri[2]
            user = next(
                user for user in self.catalog_data["Users"] if user["UserID"] == user_id
            )
            if user:
                dog = next(dog for dog in user["Dogs"] if dog["DogID"] == dog_id)
                if dog:
                    if dog["Picture"]:
                        os.remove(dog["Picture"])
                    dog["Picture"] = None
                    self.save_catalog()
                    return json.dumps(
                        {"status": "success", "message": "Dog rofile picture deleted"}
                    )
            return json.dumps(
                {"status": "error", "message": f"User {uri[1]} not found"}
            )
        elif uri[0] == "devices" and len(uri) > 1:
            device_id_to_delete = uri[1]
            # Modificato per usare "Devices" invece di "deviceList"
            self.catalog_data["Devices"] = [
                d
                for d in self.catalog_data.get("Devices", [])
                if d.get("DeviceID") != device_id_to_delete
            ]
        elif uri[0] == "services" and len(uri) > 1:
            service_id_to_delete = uri[1]
            self.catalog_data["Services"] = [  # Modificato da serviceList a Services
                s
                for s in self.catalog_data.get(
                    "Services", []
                )  # Modificato da serviceList a Services
                if s.get("ServiceID") != service_id_to_delete
            ]
        else:
            raise cherrypy.HTTPError(400, "Bad request")

        self.save_catalog()
        return "200 OK"

    def check_availability(self):
        while True:
            now = time.time()
            # Check availability of devices
            for device in self.catalog_data.get("Devices", []):
                if "LastAvailable" in device and (
                    now - device.get("LastAvailable", now) > 180
                ):  # Aggiunto .get con default
                    device["Available"] = False
                elif "LastAvailable" not in device:
                    device["Available"] = False

            # Check availability of services
            for service in self.catalog_data.get(
                "Services", []
            ):  # Modificato da serviceList a Services
                if "LastAvailable" in service and (
                    now - service.get("LastAvailable", now)
                    > 180  # Aggiunto .get con default
                ):
                    service["Available"] = False
                elif "LastAvailable" not in service:
                    service["Available"] = False
            self.save_catalog()
            time.sleep(10)


if __name__ == "__main__":
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    catalog = Catalog()
    conf = {
        "/": {
            "request.dispatch": cherrypy.dispatch.MethodDispatcher(),
            "tools.sessions.on": True,
            "request.show_tracebacks": False,
        }
    }
    cherrypy.tree.mount(catalog, "/", conf)
    cherrypy.config.update({"server.socket_host": ip})
    cherrypy.config.update({"server.socket_port": 8080})

    check_heartbeat_thread = threading.Thread(target=catalog.check_availability)
    check_heartbeat_thread.daemon = (
        True  # The thread will terminate when the program ends
    )
    check_heartbeat_thread.start()

    cherrypy.engine.start()
    cherrypy.engine.block()
