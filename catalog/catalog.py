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
        self.catalog_data = self.load_catalog()  # Load the catalog data from JSON file
        with open("secret_key.txt") as f:
            self.secret_key = f.read()  # Read the secret key from a file
        load_dotenv()  # for reading API key from `.env` file.
        self.codes = []  # Store registration and recovery codes in memory

    def generate_token(
        self,
        user_id,
    ):
        """Generate a JWT token for the user with an expiration time of 1 hour."""
        expiration_time = datetime.datetime.now(
            datetime.timezone.utc
        ) + datetime.timedelta(
            hours=1
        )  # Token expires in 1 hour
        token = jwt.encode(
            {"user_id": user_id, "exp": expiration_time},
            self.secret_key,
            algorithm="HS256",
        )  # Generate a JWT token with user ID and expiration time
        return token

    def verify_token(self, token):
        """Verify the JWT token and return the decoded data or raise an error."""
        if token in [
            "reservation_manager",
            "data_analysis",
            "temp_humid_sensor",
            "motion_sensor",
            "led_connector",
            "camera",
            "thingspeak_adaptor",
            "disinfection_system",
        ]:  # Allow specific tokens without verification for simplicity
            return token
        try:
            decoded = jwt.decode(
                token, self.secret_key, algorithms=["HS256"]
            )  # Decode the JWT token using the secret key
            return decoded
        except (
            jwt.ExpiredSignatureError
        ):  # If the token has expired, return an HTTP error
            raise cherrypy.HTTPError(401, "Token has expired")
        except jwt.InvalidTokenError:  # If the token is invalid, return an HTTP error
            raise cherrypy.HTTPError(401, "Invalid token")

    def load_catalog(self):
        """Load the catalog data from a JSON file or create a new catalog if the file does not exist."""
        try:
            with open("catalog.json") as f:
                return json.load(f)  # Load the catalog data from JSON file
        except FileNotFoundError:  # If the file does not exist, create a new catalog
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
        """Save the catalog data to a JSON file."""
        try:
            with open("catalog.json", "w") as f:
                json.dump(
                    self.catalog_data, f, indent=4
                )  # Save the catalog data to JSON file
        except IOError as e:  # If there is an error saving the file, raise an error
            print(f"Error saving catalog: {e}")

    def register(self, email):
        """Prepare a new user for registration by sending a confirmation email with a secure code."""
        email_list = [
            user["Email"] for user in self.catalog_data["Users"]
        ]  # Get a list of existing emails from the catalog
        if (
            email in email_list
        ):  # Check if the email already exists in the catalog, if it does, return an HTTP error because we do not allow duplicate registrations
            raise cherrypy.HTTPError(400, "Email already exists")
        secure_code = (
            self.generate_secure_code()
        )  # Generate a secure code for registration to send to the user
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
        )  # Send a POST request to the Mailgun API to send the confirmation email to the user
        if response.status_code == 200:  # If the response is ok
            self.codes.append(
                {"email": email, "code": secure_code}
            )  # Save a dictionary with the email and code to the codes list to be used later for check
            return json.dumps(
                {
                    "status": "success",
                    "message": "Confirm registration email sent",
                }
            )
        raise cherrypy.HTTPError(
            500, "Error sending confirm registration email"
        )  # If the response is not ok, return an HTTP error

    def confirm_registration(self, body):
        """Confirm the registration of a new user by verifying the registration code and saving the user data."""
        email = body["email"]
        registration_code = body["registration_code"]
        if not self.verify_code(
            email, registration_code
        ):  # Check if the registration code is valid or return an HTTP error
            raise cherrypy.HTTPError(401, "Invalid registration code")
        hashed_password = bcrypt.hashpw(
            body["password"].encode("utf-8"), bcrypt.gensalt()
        ).decode(
            "utf-8"
        )  # Hash the password using bcrypt
        userID = str(uuid.uuid4())  # Generate a unique user ID using UUID
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
        )  # Append a new user dictionary to the Users list in the catalog data
        self.save_catalog()  # Save the updated catalog data to the JSON file
        token = self.generate_token(userID)  # Generate a JWT token for the new user
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
        )  # Send a welcome email to the new user using the Mailgun API
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
        """Generate a secure code of specified length using letters and digits."""
        characters = string.ascii_letters + string.digits
        return "".join(secrets.choice(characters) for _ in range(length))

    def verify_code(self, email, code):
        """Verify the registration or recovery code for a given email."""
        for i, entry in enumerate(self.codes):
            if entry["email"] == email and entry["code"] == code:
                del self.codes[i]  # Remove the code after verification to prevent reuse
                return True
        return False

    def login(self, body):
        """Log in a user by verifying their email and password, and return a JWT token."""
        user = next(
            (u for u in self.catalog_data["Users"] if u["Email"] == body["email"]),
            None,
        )  # Find the user by email in the Users list of the catalog data
        if user and bcrypt.checkpw(
            body["password"].encode("utf-8"), user["Password"].encode("utf-8")
        ):  # Check if the user exists and if the password matches the hashed password
            token = self.generate_token(
                user["UserID"]
            )  # Generate a JWT token for the user
            firebaseToken = body.get(
                "firebaseToken", None
            )  # Get the firebase token from the request body if it exists
            if (
                firebaseToken is not None
                and firebaseToken not in user["FirebaseTokens"]
            ):  # If the firebase token is provided and not already in the user's FirebaseTokens list
                user["FirebaseTokens"].append(
                    body["firebaseToken"]
                )  # Append the firebase token to the user's FirebaseTokens list
                self.save_catalog()  # Save the updated catalog data to the JSON file
            return json.dumps(
                {
                    "status": "success",
                    "message": f"User {body['email']} successfully logged in",
                    "token": token,
                    "userID": user["UserID"],
                }
            )
        raise cherrypy.HTTPError(
            401, "Invalid credentials"
        )  # If the user does not exist or the password does not match, return an HTTP error

    def logout(self, userID, firebaseToken):
        """Log out a user by removing their firebase token."""
        user = next(
            (u for u in self.catalog_data["Users"] if u["UserID"] == userID),
            None,
        )  # Find the user by UserID in the Users list of the catalog data
        if not user:  # If the user does not exist, return an HTTP error
            raise cherrypy.HTTPError(404, "User not found")
        if (
            firebaseToken in user["FirebaseTokens"]
        ):  # If the firebase token is in the user's FirebaseTokens list
            user["FirebaseTokens"].remove(
                firebaseToken
            )  # Remove the firebase token from the user's FirebaseTokens list
        self.save_catalog()  # Save the updated catalog data to the JSON file
        return json.dumps(
            {
                "status": "success",
                "message": f"User {userID} logged out",
            }
        )

    def recover_password(self, body):
        """Send a password recovery email to the user with a secure code."""
        user = next(
            (u for u in self.catalog_data["Users"] if u["Email"] == body["email"]),
            None,
        )  # Find the user by email in the Users list of the catalog data
        if user:  # If the user exists
            secure_code = (
                self.generate_secure_code()
            )  # Generate a secure code for password recovery
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
            )  # Send a POST request to the Mailgun API to send the password recovery email to the user
            if response.status_code == 200:  # If the response is ok
                self.codes.append(
                    {"email": user["Email"], "code": secure_code}
                )  # Save a dictionary with the email and code to the codes list to be used later for check
                return json.dumps(
                    {
                        "status": "success",
                        "message": "Password recovery email sent",
                    }
                )
            raise cherrypy.HTTPError(
                500, "Error sending recovery email"
            )  # If the response is not ok, return an HTTP error
        raise cherrypy.HTTPError(
            404, "User not found"
        )  # If the user does not exist, return an HTTP error

    def reset_password(self, body):
        """Reset the user's password after verifying the recovery code."""
        email = body["email"]
        recovery_code = body["recovery_code"]
        password = body["password"]

        if not self.verify_code(
            email, recovery_code
        ):  # Check if the recovery code is valid or return an HTTP error
            raise cherrypy.HTTPError(401, "Invalid recovery code")
        user = next(
            (u for u in self.catalog_data["Users"] if u["Email"] == email),
            None,
        )  # Find the user by email in the Users list of the catalog data
        if user:  # If the user exists
            user["Password"] = bcrypt.hashpw(
                password.encode("utf-8"), bcrypt.gensalt()
            ).decode(
                "utf-8"
            )  # Hash the new password using bcrypt
            self.save_catalog()  # Save the updated catalog data to the JSON file
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
            )  # Send a confirmation email to the user using the Mailgun API
            return json.dumps(
                {
                    "status": "success",
                    "message": "Password reset successfully",
                }
            )
        raise cherrypy.HTTPError(
            404, "User not found"
        )  # If the user does not exist, return an HTTP error

    def edit_user(self, userID, body, file):
        """Edit user details and handle profile picture upload."""
        user = next(
            (u for u in self.catalog_data["Users"] if u["UserID"] == userID),
            None,
        )  # Find the user by UserID in the Users list of the catalog data
        if not user:  # If the user does not exist, return an HTTP error
            raise cherrypy.HTTPError(404, "User not found")

        # Update user details from the JSON body
        user["Name"] = body["name"]
        user["Email"] = body["email"]
        user["PhoneNumber"] = body["phoneNumber"]

        # Handle profile picture file
        if file:  # If a file is provided, save it as the profile picture
            profile_pictures_dir = "profile_pictures"
            os.makedirs(
                profile_pictures_dir, exist_ok=True
            )  # Ensure the directory exists
            file_path = os.path.join(
                profile_pictures_dir, f"{userID}_profile.jpg"
            )  # Create a file path for the profile picture
            with open(file_path, "wb") as f:
                shutil.copyfileobj(
                    file, f
                )  # Save the uploaded file to the specified path
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
        """Add a new dog to the user's list of dogs."""
        dogID = str(uuid.uuid4())  # Generate a unique dog ID using UUID
        user = next(
            (u for u in self.catalog_data["Users"] if u["UserID"] == userID),
            None,
        )  # Find the user by UserID in the Users list of the catalog data
        if not user:  # If the user does not exist, return an HTTP error
            raise cherrypy.HTTPError(404, "User not found")
        names = [
            d["Name"] for d in user["Dogs"]
        ]  # Get a list of existing dog names for the user
        if (
            body["name"] in names
        ):  # Check if the dog name already exists for the user. If it does, return an HTTP error
            raise cherrypy.HTTPError(
                400, f"Dog with name {body['name']} already exists for user {userID}"
            )
        body = {
            key[0].upper() + key[1:]: val for key, val in body.items()
        }  # Capitalize only first letter of the key without touching the others
        body["DogID"] = dogID  # Add the generated dog ID to the body
        if picture:  # If a picture is provided, save it as the dog's profile picture
            dog_pictures_dir = "dog_pictures"
            os.makedirs(dog_pictures_dir, exist_ok=True)  # Ensure the directory exists
            file_path = os.path.join(
                dog_pictures_dir, f"{userID}_{dogID}_dog.jpg"
            )  # Create a file path for the dog's profile picture
            with open(file_path, "wb") as f:
                shutil.copyfileobj(
                    picture, f
                )  # Save the uploaded file to the specified path
            body["Picture"] = file_path  # Save the relative path
        else:
            body["Picture"] = (
                None  # If no picture is provided, set the Picture field to None
            )
        user["Dogs"].append(
            body
        )  # Append the new dog dictionary to the user's Dogs list in the catalog data
        self.save_catalog()  # Save the updated catalog data to the JSON file
        return json.dumps(
            {"status": "success", "message": f"Dog added to user {userID}"}
        )

    def edit_dog(self, userID, dogID, body, file):
        """Edit the details of a dog for a specific user."""
        user = next(
            (u for u in self.catalog_data["Users"] if u["UserID"] == userID),
            None,
        )  # Find the user by UserID in the Users list of the catalog data
        if not user:  # If the user does not exist, return an HTTP error
            raise cherrypy.HTTPError(404, "User not found")

        dog = next(
            (d for d in user["Dogs"] if d["DogID"] == dogID),
            None,
        )  # Find the dog by DogID in the user's Dogs list
        if not dog:  # If the dog does not exist, return an HTTP error
            raise cherrypy.HTTPError(404, "Dog not found")

        # Update dog details from the JSON body
        dog["Name"] = body["name"]
        dog["Age"] = body["age"]
        dog["Sex"] = body["sex"]
        dog["Size"] = body["size"]
        dog["Weight"] = body["weight"]
        dog["CoatType"] = body["coatType"]
        dog["Allergies"] = body["allergies"]

        if (
            dog["BreedID"] == 0
        ):  # If the dog does not belong to a breed, update ideal temperature and humidity
            if (
                body["breedID"] == 0
            ):  # If the dog still does not belong to a breed, update ideal temperature and humidity
                dog["MinIdealTemperature"] = body["minIdealTemperature"]
                dog["MaxIdealTemperature"] = body["maxIdealTemperature"]
                dog["MinIdealHumidity"] = body["minIdealHumidity"]
                dog["MaxIdealHumidity"] = body["maxIdealHumidity"]
            else:  # If the dog now belongs to a breed, remove ideal temperature and humidity fields
                del dog["MinIdealTemperature"]
                del dog["MaxIdealTemperature"]
                del dog["MinIdealHumidity"]
                del dog["MaxIdealHumidity"]
        else:
            if (
                body["breedID"] == 0
            ):  # If the dog now does not belong to a breed, insert ideal temperature and humidity
                dog["MinIdealTemperature"] = body["minIdealTemperature"]
                dog["MaxIdealTemperature"] = body["maxIdealTemperature"]
                dog["MinIdealHumidity"] = body["minIdealHumidity"]
                dog["MaxIdealHumidity"] = body["maxIdealHumidity"]

        dog["BreedID"] = body["breedID"]  # Update the BreedID of the dog

        # Handle profile picture file
        if file:  # If a file is provided, save it as the dog's profile picture
            dog_pictures_dir = "dog_pictures"
            os.makedirs(dog_pictures_dir, exist_ok=True)  # Ensure the directory exists
            file_path = os.path.join(
                dog_pictures_dir, f"{userID}_{dogID}_dog.jpg"
            )  # Create a file path for the dog's profile picture
            with open(file_path, "wb") as f:
                shutil.copyfileobj(
                    file, f
                )  # Save the uploaded file to the specified path
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
        """Delete a dog from a user's list of dogs."""
        user = next(
            user for user in self.catalog_data["Users"] if user["UserID"] == userID
        )  # Find the user by UserID in the Users list of the catalog data
        if not user:  # If the user does not exist, return an HTTP error
            raise cherrypy.HTTPError(404, "User not found")
        dog = next(
            (d for d in user["Dogs"] if d["DogID"] == dogID),
            None,
        )  # Find the dog by DogID in the user's Dogs list
        if not dog:  # If the dog does not exist, return an HTTP error
            raise cherrypy.HTTPError(404, "Dog not found")
        if dog["Picture"]:  # If the dog has a picture, remove it from the filesystem
            os.remove(dog["Picture"])
        user["Dogs"] = [
            d for d in user["Dogs"] if d["DogID"] != dogID
        ]  # Remove the dog from the user's Dogs list
        self.save_catalog()  # Save the updated catalog data to the JSON file
        return json.dumps(
            {"status": "success", "message": f"Dog {dogID} of User {userID} deleted"}
        )

    def book_kennel(self, body):
        """Book a kennel for a specific store."""
        storeID = body["storeID"]
        kennel = body["kennel"]

        store = next(
            (
                store
                for store in self.catalog_data["Stores"]
                if store["StoreID"] == storeID
            ),
            None,
        )  # Find the store by StoreID in the Stores list of the catalog data
        if store:
            kennel = next(
                (k for k in store["Kennels"] if k["ID"] == kennel), None
            )  # Find the kennel by ID in the store's Kennels list
            if kennel:  # If the kennel exists
                kennel["Booked"] = True  # Set the kennel as booked
                self.save_catalog()  # Save the updated catalog data to the JSON file
                return json.dumps({"status": "success", "message": "Kennel booked"})
            raise cherrypy.HTTPError(
                404, "Kennel not found"
            )  # If the kennel does not exist, return an HTTP error
        raise cherrypy.HTTPError(
            404, "Store not found"
        )  # If the store does not exist, return an HTTP error

    def lock_kennel(self, body):
        """Lock a kennel for a specific store."""
        storeID = body["storeID"]
        kennel = body["kennel"]
        store = next(
            (s for s in self.catalog_data["Stores"] if s["StoreID"] == storeID),
            None,
        )  # Find the store by StoreID in the Stores list of the catalog data
        if store:  # If the store exists
            kennel = next(
                (k for k in store["Kennels"] if k["ID"] == kennel),
                None,
            )  # Find the kennel by ID in the store's Kennels list
            if kennel:  # If the kennel exists
                kennel["Occupied"] = True  # Set the kennel as occupied
                self.save_catalog()  # Save the updated catalog data to the JSON file
                return json.dumps({"status": "success", "message": "Kennel locked"})
            raise cherrypy.HTTPError(
                404, "Kennel not found"
            )  # If the kennel does not exist, return an HTTP error
        raise cherrypy.HTTPError(
            404, "Store not found"
        )  # If the store does not exist, return an HTTP error

    def free_kennel(self, body):
        """Free a kennel for a specific store."""
        storeID = body["storeID"]
        kennel = body["kennel"]
        store = next(
            (s for s in self.catalog_data["Stores"] if s["StoreID"] == storeID),
            None,
        )  # Find the store by StoreID in the Stores list of the catalog data
        if store:  # If the store exists
            kennel = next(
                (k for k in store["Kennels"] if k["ID"] == kennel),
                None,
            )  # Find the kennel by ID in the store's Kennels list
            if kennel:  # If the kennel exists
                kennel["Occupied"] = False  # Set the kennel as not occupied
                kennel["Booked"] = False  # Set the kennel as not booked
                self.save_catalog()  # Save the updated catalog data to the JSON file
                return json.dumps({"status": "success", "message": "Kennel freed"})
            raise cherrypy.HTTPError(
                404, "Kennel not found"
            )  # If the kennel does not exist, return an HTTP error
        raise cherrypy.HTTPError(
            404, "Store not found"
        )  # If the store does not exist, return an HTTP error

    def GET(self, *uri, **params):
        auth_header = cherrypy.request.headers.get(
            "Authorization"
        )  # Get the Authorization header from the request
        if (
            not auth_header
        ):  # If the Authorization header is not present, return an HTTP error
            # Allow access to status_page without token for simplicity, or add specific token check
            if not (
                len(uri) > 0 and uri[0] == "status_page"
            ):  # If the request is not for the status page, raise an HTTP error
                raise cherrypy.HTTPError(401, "Authorization token required")
        else:
            token = auth_header.split(" ")[
                1
            ]  # Extract the token from the Authorization header
            self.verify_token(token)  # Verify the token for other routes

        if len(uri) == 0:  # If no URI is provided, return the entire catalog data
            return json.dumps(self.catalog_data)
        elif uri[0] == "broker":  # If the URI is "broker", return the broker data
            return json.dumps(self.catalog_data["broker"])
        elif uri[0] == "devices":  # If the URI is "devices", return the devices data
            return json.dumps(self.catalog_data["Devices"])
        elif uri[0] == "services":  # If the URI is "services", return the services data
            return json.dumps(
                self.catalog_data.get("Services", [])
            )  # Modificato da serviceList a Services
        elif uri[0] == "stores":  # If the URI is "stores", return the stores data
            return json.dumps(self.catalog_data["Stores"])
        elif uri[0] == "breeds":  # If the URI is "breeds", return the breeds data
            return json.dumps(self.catalog_data["Breeds"])
        elif uri[0] == "users":  # If the URI is "users", return the users data
            if (
                len(uri) > 1
            ):  # If a specific userID is provided, return that user's data
                user = next(
                    (u for u in self.catalog_data["Users"] if u["UserID"] == uri[1]),
                    None,
                )  # Find the user by UserID in the Users list of the catalog data
                if not user:  # If the user does not exist, return an HTTP error
                    raise cherrypy.HTTPError(404, "User not found")

                return json.dumps(
                    {key: val for key, val in user.items() if key != "Password"}
                )
            return json.dumps(self.catalog_data["Users"])
        elif (
            uri[0] == "profile_picture"
        ):  # If the URI is "profile_picture", return the user's profile picture
            if len(uri) < 2:  # If no userID is provided, raise an HTTP error
                raise cherrypy.HTTPError(400, "Bad request, add userID")
            user = next(
                (u for u in self.catalog_data["Users"] if u["UserID"] == uri[1]),
                None,
            )  # Find the user by UserID in the Users list of the catalog data
            if not user:  # If the user does not exist, return an HTTP error
                raise cherrypy.HTTPError(404, "User not found")
            if not user[
                "ProfilePicture"
            ]:  # If the user does not have a profile picture, return None
                return None
            return static.serve_file(
                "/app/" + user["ProfilePicture"],
                content_type="image/jpg",
                disposition="attachment",
                name=user["ProfilePicture"].split("/")[-1],
            )  # Serve the profile picture file
        elif (
            uri[0] == "dog_picture"
        ):  # If the URI is "dog_picture", return the dog's profile picture
            if len(uri) < 3:  # If no userID or dogID is provided, raise an HTTP error
                raise cherrypy.HTTPError(400, "Bad request, use userID and dogID")
            user = next(
                (u for u in self.catalog_data["Users"] if u["UserID"] == uri[1]),
                None,
            )  # Find the user by UserID in the Users list of the catalog data
            if not user:  # If the user does not exist, return an HTTP error
                raise cherrypy.HTTPError(404, "User not found")
            dog = next(
                (d for d in user["Dogs"] if d["DogID"] == uri[2]),
                None,
            )  # Find the dog by DogID in the user's Dogs list
            if not dog:  # If the dog does not exist, return an HTTP error
                raise cherrypy.HTTPError(404, "Dog not found")
            if not dog[
                "Picture"
            ]:  # If the dog does not have a profile picture, return None
                return None
            return static.serve_file(
                "/app/" + dog["Picture"],
                content_type="image/jpg",
                disposition="attachment",
                name=dog["Picture"].split("/")[-1],
            )  # Serve the dog's profile picture file
        elif (
            uri[0] == "status_page"
        ):  # If the URI is "status_page", return the status page HTML
            cherrypy.response.headers["Content-Type"] = (
                "text/html"  # Set the response content type to HTML
            )
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
            """  # Start the HTML document with a title and styles

            html += "<h2>Devices</h2><ul>"  # Add a section for devices
            if (
                "Devices" in self.catalog_data and self.catalog_data["Devices"]
            ):  # Check if Devices key exists and has items
                for device in self.catalog_data[
                    "Devices"
                ]:  # Iterate through each device in the Devices list
                    device_id = device.get("DeviceID", "N/A")
                    device_name = device.get("Name", f"DefaultNameForID_{device_id}")
                    available_status = device.get("Available", False)

                    status_color = (
                        "green" if available_status else "red"
                    )  # Determine the status color based on availability
                    html += f"""<li>
                                    <span class='status-circle {status_color}'></span>
                                    <div class='details'>
                                        ID: {device_id}, Name: {device_name}
                                    </div>
                                </li>"""  # Create a list item for each device with its status
            else:
                html += "<li>No devices registered.</li>"  # If no devices are registered, display a message
            html += "</ul>"  # Close the devices section

            html += "<h2>Services</h2><ul>"  # Add a section for services
            service_list_items = self.catalog_data.get(
                "Services", []
            )  # Get the list of services from the catalog data
            if service_list_items:  # Check if there are any services registered
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
                                </li>"""  # Create a list item for each service with its status
            else:
                html += "<li>No services registered.</li>"  # If no services are registered, display a message
            html += "</ul>"  # Close the services section

            html += """
            </body>
            </html>
            """  # Close the HTML document
            return html
        else:
            raise cherrypy.HTTPError(
                404, "Resource not found"
            )  # If the URI does not match any known routes, return a 404 error

    def POST(self, *uri, **params):
        # Routes that do not require authentication
        public_routes = ["register", "login", "recover", "confirm_registration"]

        # Check if the route is public
        if uri[0] not in public_routes:
            # Enforce authentication for all other POST routes
            auth_header = cherrypy.request.headers.get(
                "Authorization"
            )  # Get the Authorization header from the request
            if (
                not auth_header
            ):  # If the Authorization header is not present, raise an HTTP error
                raise cherrypy.HTTPError(401, "Authorization token required")
            token = auth_header.split(" ")[
                1
            ]  # Extract the token from the Authorization header
            self.verify_token(token)  # Verify the token

        if cherrypy.request.headers.get("Content-Type", "").startswith(
            "application/json"
        ):  # Check if the request body is in JSON format
            # Handle specific POST routes
            body = cherrypy.request.body.read()
            json_body = json.loads(body)

        if uri[0] == "register":  # If the URI is "register", register a new user
            return self.register(json_body["email"])
        elif (
            uri[0] == "confirm_registration"
        ):  # If the URI is "confirm_registration", confirm the registration of a user
            return self.confirm_registration(json_body)
        elif uri[0] == "login":  # If the URI is "login", log in a user
            return self.login(json_body)
        elif uri[0] == "logout":  # If the URI is "logout", log out a user
            return self.logout(json_body["userID"], json_body["firebaseToken"])
        elif uri[0] == "book":  # If the URI is "book", book a kennel for a store
            return self.book_kennel(json_body)
        elif uri[0] == "lock":  # If the URI is "lock", lock a kennel for a store
            return self.lock_kennel(json_body)
        elif uri[0] == "free":  # If the URI is "free", free a kennel for a store
            return self.free_kennel(json_body)
        elif uri[0] == "dogs":  # If the URI is "dogs", add a dog for a user
            if len(uri) == 1:  # If no userID is provided, raise an HTTP error
                raise cherrypy.HTTPError(400, "Bad request, add userID")
            userID = uri[1]
            if cherrypy.request.headers.get("Content-Type", "").startswith(
                "multipart/form-data"
            ):  # Check if the request body is in multipart/form-data format
                fields = (
                    cherrypy.request.body.params
                )  # Get the fields from the request body
                dog_data_field = fields.get("dogData")
                dog_picture_field = fields.get("dogPicture")

                if (
                    not dog_data_field
                ):  # If the dogData field is not present, raise an HTTP error
                    raise cherrypy.HTTPError(400, "dogData is required")

                dog_data = json.loads(dog_data_field)  # Parse the dogData field as JSON

                dog_picture = None  # Initialize dog_picture as None
                if dog_picture_field:  # If the dogPicture field is present
                    dog_picture = dog_picture_field.file
                return self.add_dog(
                    userID, dog_data, dog_picture
                )  # Call the add_dog method with the userID, dog data, and dog picture
            elif cherrypy.request.headers.get("Content-Type", "").startswith(
                "application/json"
            ):  # Check if the request body is in JSON format
                return self.add_dog(
                    userID, json_body, None
                )  # Call the add_dog method with the userID and dog data
        elif uri[0] == "recover":  # If the URI is "recover", recover a user's password
            return self.recover_password(json_body)
        elif uri[0] == "devices":  # If the URI is "devices", add a new device
            self.catalog_data["Devices"].append(
                json_body
            )  # Append the new device dictionary to the Devices list in the catalog data
            self.save_catalog()  # Save the updated catalog data to the JSON file
            return json.dumps({"status": "success", "message": "Device added"})
        elif uri[0] == "services":
            self.catalog_data["Services"].append(
                json_body
            )  # Append the new service dictionary to the Services list in the catalog data
            self.save_catalog()  # Save the updated catalog data to the JSON file
            return json.dumps({"status": "success", "message": "Service added"})
        elif (
            uri[0] == "heartbeat"
        ):  # If the URI is "heartbeat", handle the heartbeat request
            # Handle heartbeat
            category = json_body.get("category", None)
            if not category:  # If the category is not provided, raise an HTTP error
                raise cherrypy.HTTPError(400, "Category is required")
            if (
                category == "sensor"
            ):  # If the category is "sensor", handle sensor heartbeat
                device_id = json_body["deviceID"]
                device = next(
                    (
                        d
                        for d in self.catalog_data["Devices"]
                        if d["DeviceID"] == device_id
                    ),
                    None,
                )  # Find the device by DeviceID in the Devices list of the catalog data
                if not device:  # If the device does not exist, raise an HTTP error
                    raise cherrypy.HTTPError(404, "Device not found")
                device["LastAvailable"] = (
                    time.time()
                )  # Update the LastAvailable timestamp of the device
                device["Available"] = True  # Set the device as available
            elif (
                category == "service"
            ):  # If the category is "service", handle service heartbeat
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
                )  # Find the service by ServiceID in the Services list of the catalog data
                if not service:  # If the service does not exist, raise an HTTP error
                    raise cherrypy.HTTPError(
                        404,
                        f"Service with ID {service_id} not found in Services",  # Messaggio aggiornato
                    )
                service["LastAvailable"] = (
                    time.time()
                )  # Update the LastAvailable timestamp of the service
                service["Available"] = True  # Set the service as available
            else:  # If the category is not recognized, raise an HTTP error
                raise cherrypy.HTTPError(400, "Invalid category")
            self.save_catalog()  # Save the updated catalog data to the JSON file
            return json.dumps({"status": "success", "message": "Heartbeat received"})
        else:  # If the URI does not match any known routes, raise an HTTP error
            raise cherrypy.HTTPError(400, "Bad request")

    def PUT(self, *uri, **params):
        # Routes that do not require authentication
        public_routes = ["reset_password"]

        # Check if the route is public
        if uri[0] not in public_routes:
            # Enforce authentication for all other POST routes
            auth_header = cherrypy.request.headers.get(
                "Authorization"
            )  # Get the Authorization header from the request
            if (
                not auth_header
            ):  # If the Authorization header is not present, raise an HTTP error
                raise cherrypy.HTTPError(401, "Authorization token required")
            token = auth_header.split(" ")[
                1
            ]  # Extract the token from the Authorization header
            self.verify_token(token)  # Verify the token

        if cherrypy.request.headers.get("Content-Type", "").startswith(
            "application/json"
        ):  # Check if the request body is in JSON format
            body = cherrypy.request.body.read()
            json_body = json.loads(body)

        if uri[0] == "devices":  # If the URI is "devices", update a device
            # Modificato per usare "Devices" invece di "deviceList"
            device_id_to_update = json_body.get(
                "DeviceID"
            )  # Assumendo che il JSON in input usi "DeviceID"
            if (
                device_id_to_update is None
            ):  # If DeviceID is not provided, raise an HTTP error
                raise cherrypy.HTTPError(
                    400, "DeviceID is required in request body for update"
                )

            devices = self.catalog_data.get("Devices", [])
            found = False
            for i, device in enumerate(devices):
                if device.get("DeviceID") == device_id_to_update:
                    self.catalog_data["Devices"][
                        i
                    ] = json_body  # Update the device in the Devices list
                    found = True
                    break
            if not found:  # If the device is not found, raise an HTTP error
                raise cherrypy.HTTPError(
                    404, f"Device with ID {device_id_to_update} not found"
                )

        elif uri[0] == "services":  # If the URI is "services", update a service
            service_id_to_update = json_body.get("serviceID")
            if (
                service_id_to_update is None
            ):  # If serviceID is not provided, raise an HTTP error
                raise cherrypy.HTTPError(
                    400, "serviceID is required in request body for update"
                )

            services = self.catalog_data.get(
                "Services", []
            )  # Get the list of services from the catalog data
            found = False
            for i, service in enumerate(services):
                if service.get("ServiceID") == service_id_to_update:
                    self.catalog_data["Services"][
                        i
                    ] = json_body  # Update the service in the Services list
                    found = True
                    break
            if not found:  # If the service is not found, raise an HTTP error
                raise cherrypy.HTTPError(
                    404, f"Service with ID {service_id_to_update} not found"
                )
        elif uri[0] == "users":  # If the URI is "users", update a user
            if len(uri) < 2:  # If no userID is provided, raise an HTTP error
                raise cherrypy.HTTPError(400, "UserID is required")

            userID = uri[1]

            # Check for multipart data
            if cherrypy.request.headers.get("Content-Type", "").startswith(
                "multipart/form-data"
            ):  # Check if the request body is in multipart/form-data format
                fields = (
                    cherrypy.request.body.params
                )  # Get the fields from the request body
                user_data_field = fields.get("userData")
                profile_picture_field = fields.get("profilePicture")

                if (
                    not user_data_field
                ):  # If the userData field is not present, raise an HTTP error
                    raise cherrypy.HTTPError(400, "userData is required")

                user_data = json.loads(user_data_field)

                profile_picture = None
                if profile_picture_field:  # If the profilePicture field is present
                    profile_picture = profile_picture_field.file

                # Call edit_user with or without profile picture
                return self.edit_user(userID, user_data, profile_picture)
            elif cherrypy.request.headers.get("Content-Type", "").startswith(
                "application/json"
            ):  # Check if the request body is in JSON format
                return self.edit_user(
                    userID, json_body, None
                )  # Call edit_user with the userID and user data
            else:  # If the request body is not in the expected format, raise an HTTP error
                raise cherrypy.HTTPError(
                    400, "Expected multipart/form-data or application/json request"
                )
        elif uri[0] == "dogs":  # If the URI is "dogs", edit a dog's details
            if len(uri) < 3:  # If no userID or dogID is provided, raise an HTTP error
                raise cherrypy.HTTPError(400, "UserID and dogID is required")

            userID = uri[1]
            dogID = uri[2]

            # Check for multipart data
            if cherrypy.request.headers.get("Content-Type", "").startswith(
                "multipart/form-data"
            ):  # Check if the request body is in multipart/form-data format
                fields = (
                    cherrypy.request.body.params
                )  # Get the fields from the request body
                dog_data_field = fields.get("dogData")
                dog_picture_field = fields.get("dogPicture")

                if (
                    not dog_data_field
                ):  # If the dogData field is not present, raise an HTTP error
                    raise cherrypy.HTTPError(400, "dogData is required")

                dog_data = json.loads(dog_data_field)

                dog_picture = None
                if dog_picture_field:  # If the dogPicture field is present
                    dog_picture = dog_picture_field.file

                # Call edit_user with or without profile picture
                return self.edit_dog(userID, dogID, dog_data, dog_picture)
            elif cherrypy.request.headers.get("Content-Type", "").startswith(
                "application/json"
            ):  # Check if the request body is in JSON format
                return self.edit_dog(
                    userID, dogID, json_body, None
                )  # Call edit_dog with the userID, dogID, and dog data
            else:  # If the request body is not in the expected format, raise an HTTP error
                raise cherrypy.HTTPError(
                    400, "Expected multipart/form-data or application/json request"
                )
        elif (
            uri[0] == "reset_password"
        ):  # If the URI is "reset_password", reset a user's password
            return self.reset_password(
                json_body
            )  # Call reset_password with the request body
        else:  # If the URI does not match any known routes, raise an HTTP error
            raise cherrypy.HTTPError(400, "Bad request")

        self.save_catalog()  # Save the updated catalog data to the JSON file
        return "200 OK"

    def DELETE(self, *uri, **params):
        if (
            uri[0] == "dogs"
        ):  # If the URI is "dogs", delete a dog from a user's list of dogs
            # DEL request at IP:8080/dogs/userID/dogID
            if len(uri) < 3:  # If no userID or dogID is provided, raise an HTTP error
                raise cherrypy.HTTPError(400, "Bad request, use both userID and dogID")
            return self.delete_dog(
                uri[1], uri[2]
            )  # Call delete_dog with the userID and dogID
        elif uri[0] == "users":  # If the URI is "users", delete a user from the catalog
            # DEL request at IP:8080/users/userID
            if len(uri) < 2:  # If no userID is provided, raise an HTTP error
                raise cherrypy.HTTPError(400, "Bad request, use userID")
            user_id = uri[1]
            user = next(
                user for user in self.catalog_data["Users"] if user["UserID"] == user_id
            )  # Find the user by UserID in the Users list of the catalog data
            if not user:
                raise cherrypy.HTTPError(
                    404, "User not found"
                )  # If the user does not exist, raise an HTTP error
            if user[
                "ProfilePicture"
            ]:  # If the user has a profile picture, remove it from the filesystem
                os.remove(user["ProfilePicture"])
            self.catalog_data["Users"] = [
                u for u in self.catalog_data["Users"] if u["UserID"] != user_id
            ]  # Remove the user from the Users list
            self.save_catalog()  # Save the updated catalog data to the JSON file
            return json.dumps(
                {"status": "success", "message": f"User {uri[1]} deleted"}
            )
        elif (
            uri[0] == "profile_picture"
        ):  # If the URI is "profile_picture", delete a user's profile picture
            # DEL request at IP:8080/profile_picture/userID
            if len(uri) < 2:  # If no userID is provided, raise an HTTP error
                raise cherrypy.HTTPError(400, "Bad request, use userID")
            user_id = uri[1]
            user = next(
                user for user in self.catalog_data["Users"] if user["UserID"] == user_id
            )  # Find the user by UserID in the Users list of the catalog data
            if user:  # If the user exists
                if user[
                    "ProfilePicture"
                ]:  # If the user has a profile picture, remove it from the filesystem
                    os.remove(user["ProfilePicture"])
                user["ProfilePicture"] = None  # Set the user's profile picture to None
                self.save_catalog()  # Save the updated catalog data to the JSON file
                return json.dumps(
                    {"status": "success", "message": "Profile picture deleted"}
                )
            raise cherrypy.HTTPError(
                404, "User not found"
            )  # If the user does not exist, raise an HTTP error
        elif uri[0] == "dog_picture":
            # DEL request at IP:8080/dog_picture/userID/dogID
            if len(uri) < 3:  # If no userID or dogID is provided, raise an HTTP error
                raise cherrypy.HTTPError(400, "Bad request, use userID and dogID")
            user_id = uri[1]
            dog_id = uri[2]
            user = next(
                user for user in self.catalog_data["Users"] if user["UserID"] == user_id
            )  # Find the user by UserID in the Users list of the catalog data
            if user:  # If the user exists
                dog = next(
                    dog for dog in user["Dogs"] if dog["DogID"] == dog_id
                )  # Find the dog by DogID in the user's Dogs list
                if dog:  # If the dog exists
                    if dog[
                        "Picture"
                    ]:  # If the dog has a profile picture, remove it from the filesystem
                        os.remove(dog["Picture"])
                    dog["Picture"] = None  # Set the dog's profile picture to None
                    self.save_catalog()  # Save the updated catalog data to the JSON file
                    return json.dumps(
                        {"status": "success", "message": "Dog rofile picture deleted"}
                    )
                raise cherrypy.HTTPError(
                    404, "Dog not found"
                )  # If the dog does not exist, raise an HTTP error
            raise cherrypy.HTTPError(
                404, "User not found"
            )  # If the user does not exist, raise an HTTP error
        elif (
            uri[0] == "devices" and len(uri) > 1
        ):  # If the URI is "devices" and a deviceID is provided, delete a device
            device_id_to_delete = uri[1]
            self.catalog_data["Devices"] = [
                d
                for d in self.catalog_data.get("Devices", [])
                if d.get("DeviceID") != device_id_to_delete
            ]  # Remove the device with the specified DeviceID from the Devices list
        elif (
            uri[0] == "services" and len(uri) > 1
        ):  # If the URI is "services" and a serviceID is provided, delete a service
            service_id_to_delete = uri[1]
            self.catalog_data["Services"] = [  # Modificato da serviceList a Services
                s
                for s in self.catalog_data.get(
                    "Services", []
                )  # Modificato da serviceList a Services
                if s.get("ServiceID") != service_id_to_delete
            ]  # Remove the service with the specified ServiceID from the Services list
        else:  # If the URI does not match any known routes, raise an HTTP error
            raise cherrypy.HTTPError(400, "Bad request")

        self.save_catalog()  # Save the updated catalog data to the JSON file
        return "200 OK"

    def check_availability(self):
        while True:
            now = time.time()
            # Check availability of devices
            for device in self.catalog_data.get("Devices", []):
                if "LastAvailable" in device and (
                    now - device.get("LastAvailable", now) > 180
                ):  # If LastAvailable is more than 180 seconds ago
                    device["Available"] = False  # Set the device as not available
                elif "LastAvailable" not in device:  # If LastAvailable is not present
                    device["Available"] = False  # Set the device as not available

            # Check availability of services
            for service in self.catalog_data.get("Services", []):
                if "LastAvailable" in service and (
                    now - service.get("LastAvailable", now) > 180
                ):  # If LastAvailable is more than 180 seconds ago
                    service["Available"] = False  # Set the service as not available
                elif "LastAvailable" not in service:  # If LastAvailable is not present
                    service["Available"] = False  # Set the service as not available
            self.save_catalog()  # Save the updated catalog data to the JSON file
            time.sleep(10)  # Sleep for 10 seconds before the next check


if __name__ == "__main__":
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]  # getting the IP address of the container
    s.close()
    catalog = Catalog()  # Initialize the Catalog class
    conf = {
        "/": {
            "request.dispatch": cherrypy.dispatch.MethodDispatcher(),
            "tools.sessions.on": True,
            "request.show_tracebacks": False,
        }
    }  # Configuration for the CherryPy server
    cherrypy.tree.mount(catalog, "/", conf)  # Mount the Catalog class to the root
    cherrypy.config.update(
        {"server.socket_host": ip}
    )  # Set the server socket host to the container's IP address
    cherrypy.config.update(
        {"server.socket_port": 8080}
    )  # Set the server socket port to 8080

    check_heartbeat_thread = threading.Thread(
        target=catalog.check_availability
    )  # Create a thread to check availability of the
    check_heartbeat_thread.daemon = (
        True  # The thread will terminate when the program ends
    )
    check_heartbeat_thread.start()  # Start the thread

    cherrypy.engine.start()  # Start the CherryPy server
    cherrypy.engine.block()  # Block the main thread to keep the server running until KeyboardInterrupt
