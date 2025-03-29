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
        if token in ["reservation_manager", "data_analysis"]:
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
        else:
            dog["MinIdealTemperature"] = body["minIdealTemperature"]
            dog["MaxIdealTemperature"] = body["maxIdealTemperature"]
            dog["MinIdealHumidity"] = body["minIdealHumidity"]
            dog["MaxIdealHumidity"] = body["maxIdealHumidity"]

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
            raise cherrypy.HTTPError(401, "Authorization token required")
        token = auth_header.split(" ")[1]
        self.verify_token(token)  # Verify the token

        if len(uri) == 0:
            return json.dumps(self.catalog_data)
        elif uri[0] == "broker":
            return json.dumps(self.catalog_data["broker"])
        elif uri[0] == "devices":
            return json.dumps(self.catalog_data["Devices"])
        elif uri[0] == "services":
            return json.dumps(self.catalog_data["serviceList"])
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
            self.catalog_data["serviceList"].append(json_body)
            self.save_catalog()
            return json.dumps({"status": "success", "message": "Service added"})

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
            for i, device in enumerate(self.catalog_data["deviceList"]):
                if device["deviceID"] == json_body["deviceID"]:
                    self.catalog_data["deviceList"][i] = json_body
                    break
        elif uri[0] == "services":
            for i, service in enumerate(self.catalog_data["serviceList"]):
                if service["serviceID"] == json_body["serviceID"]:
                    self.catalog_data["serviceList"][i] = json_body
                    break
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
            device_id = uri[1]
            self.catalog_data["deviceList"] = [
                d for d in self.catalog_data["deviceList"] if d["deviceID"] != device_id
            ]
        elif uri[0] == "services" and len(uri) > 1:
            service_id = uri[1]
            self.catalog_data["serviceList"] = [
                s
                for s in self.catalog_data["serviceList"]
                if s["serviceID"] != service_id
            ]
        else:
            raise cherrypy.HTTPError(400, "Bad request")

        self.save_catalog()
        return "200 OK"


if __name__ == "__main__":
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    conf = {
        "/": {
            "request.dispatch": cherrypy.dispatch.MethodDispatcher(),
            "tools.sessions.on": True,
            "request.show_tracebacks": False,
        }
    }
    cherrypy.tree.mount(Catalog(), "/", conf)
    cherrypy.config.update({"server.socket_host": ip})
    cherrypy.config.update({"server.socket_port": 8080})
    cherrypy.engine.start()
    cherrypy.engine.block()
