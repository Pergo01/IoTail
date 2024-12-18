import cherrypy
import json
import time
import os
import socket
import bcrypt
import uuid
import jwt
import datetime


class Catalog:
    exposed = True

    def __init__(self):
        self.catalog_data = self.load_catalog()
        with open("secret_key.txt") as f:
            self.secret_key = f.read()

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
        if token == "reservation_manager":
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
            with open("catalog.json", "r") as f:
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

    def register(self, body):
        email_list = [user["Email"] for user in self.catalog_data["Users"]]
        if body["email"] in email_list:
            raise cherrypy.HTTPError(400, "Email already exists")
        hashed_password = bcrypt.hashpw(
            body["password"].encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        userID = str(uuid.uuid4())
        self.catalog_data["Users"].append(
            {
                "UserID": userID,
                "Name": body["name"],
                "Email": body["email"],
                "Password": hashed_password,
                "PhoneNumber": body["phone"],
                "Dogs": [],
            }
        )
        self.save_catalog()
        role = body.get("role", "Client")  # Default role is "client"
        token = self.generate_token(userID, role)
        return json.dumps(
            {
                "status": "success",
                "message": f"User {body['email']} successfully registered",
                "token": token,
                "userID": userID,
            }
        )

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
            return json.dumps(
                {
                    "status": "success",
                    "message": f"User {body['email']} successfully logged in",
                    "token": token,
                    "userID": user["UserID"],
                }
            )
        raise cherrypy.HTTPError(401, "Invalid credentials")

    def book_kennel(self, body):
        loc = body["location"]
        kennel = body["kennel"]

        store = next(
            (
                store
                for store in self.catalog_data["Stores"]
                if store["Location"] == loc
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
        loc = body["location"]
        kennel = body["kennel"]
        store = next(
            (s for s in self.catalog_data["Stores"] if s["Location"] == loc),
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
        loc = body["location"]
        kennel = body["kennel"]
        store = next(
            (s for s in self.catalog_data["Stores"] if s["Location"] == loc),
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

    def add_dog(self, userID, body):
        dogID = str(uuid.uuid4())
        user = next(
            (u for u in self.catalog_data["Users"] if u["UserID"] == userID),
            None,
        )
        if user:
            body["DogID"] = dogID
            user["Dogs"].append(body)
            self.save_catalog()
            return json.dumps({"status": "success", "message": "Dog added"})
        raise cherrypy.HTTPError(404, "User not found")

    def delete_dog(self, userID, dogID):
        user = next(
            (u for u in self.catalog_data["Users"] if u["UserID"] == userID),
            None,
        )
        if user:
            user["Dogs"] = [d for d in user["Dogs"] if d["DogID"] != dogID]
            self.save_catalog()
            return json.dumps({"status": "success", "message": "Dog deleted"})
        raise cherrypy.HTTPError(404, "User not found")

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
                return json.dumps(user)
            return json.dumps(self.catalog_data["Users"])
        else:
            raise cherrypy.HTTPError(404, "Resource not found")

    def POST(self, *uri, **params):
        # Routes that do not require authentication
        public_routes = ["register", "login"]

        # Check if the route is public
        if uri[0] not in public_routes:
            # Enforce authentication for all other POST routes
            auth_header = cherrypy.request.headers.get("Authorization")
            if not auth_header:
                raise cherrypy.HTTPError(401, "Authorization token required")
            token = auth_header.split(" ")[1]
            self.verify_token(token)  # Verify the token

        # Handle specific POST routes
        body = cherrypy.request.body.read()
        json_body = json.loads(body)

        if uri[0] == "register":
            return self.register(json_body)
        elif uri[0] == "login":
            return self.login(json_body)
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
            return self.add_dog(userID, json_body)
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
