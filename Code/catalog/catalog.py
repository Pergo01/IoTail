import cherrypy
import json
import time
import os
import socket

class Catalog:
    exposed = True

    def __init__(self):
        self.catalog_data = self.load_catalog()

    def load_catalog(self):
        try:
            with open('catalog.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {"broker": {}, "deviceList": [], "serviceList": [], "dogBreeds": []}

    def save_catalog(self):
        try:
            with open('catalog.json', 'w') as f:
                json.dump(self.catalog_data, f, indent=4)
        except IOError as e:
            print(f"Error saving catalog: {e}")

    # Aggiungere metodo per gestire le prenotazioni dei kennel
    def handle_reservation(self, reservation_data):
        # Implementare la logica di prenotazione qui
        pass

    def GET(self, *uri, **params):
        if len(uri) == 0:
            return json.dumps(self.catalog_data)
        elif uri[0] == 'broker':
            return json.dumps(self.catalog_data['broker'])
        elif uri[0] == 'devices':
            return json.dumps(self.catalog_data['Devices'])
        elif uri[0] == 'services':
            return json.dumps(self.catalog_data['serviceList'])
        elif uri[0] == 'kennels':
            return json.dumps(self.catalog_data['Kennels'])
        elif uri[0] == 'dogs':
            return json.dumps(self.catalog_data['Dogs'])
        else:
            raise cherrypy.HTTPError(404, "Resource not found")

    def POST(self, *uri, **params):
        body = cherrypy.request.body.read()
        json_body = json.loads(body)

        if uri[0] == 'devices':
            self.catalog_data['deviceList'].append(json_body)
        elif uri[0] == 'services':
            self.catalog_data['serviceList'].append(json_body)
        else:
            raise cherrypy.HTTPError(400, "Bad request")

        self.save_catalog()
        return "201 Created"

    def PUT(self, *uri, **params):
        body = cherrypy.request.body.read()
        json_body = json.loads(body)

        if uri[0] == 'devices':
            for i, device in enumerate(self.catalog_data['deviceList']):
                if device['deviceID'] == json_body['deviceID']:
                    self.catalog_data['deviceList'][i] = json_body
                    break
        elif uri[0] == 'services':
            for i, service in enumerate(self.catalog_data['serviceList']):
                if service['serviceID'] == json_body['serviceID']:
                    self.catalog_data['serviceList'][i] = json_body
                    break
        else:
            raise cherrypy.HTTPError(400, "Bad request")

        self.save_catalog()
        return "200 OK"

    def DELETE(self, *uri, **params):
        if uri[0] == 'devices' and len(uri) > 1:
            device_id = uri[1]
            self.catalog_data['deviceList'] = [d for d in self.catalog_data['deviceList'] if d['deviceID'] != device_id]
        elif uri[0] == 'services' and len(uri) > 1:
            service_id = uri[1]
            self.catalog_data['serviceList'] = [s for s in self.catalog_data['serviceList'] if s['serviceID'] != service_id]
        else:
            raise cherrypy.HTTPError(400, "Bad request")

        self.save_catalog()
        return "200 OK"

if __name__ == '__main__':
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    conf = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on': True
        }
    }
    cherrypy.tree.mount(Catalog(), '/', conf)
    cherrypy.config.update({'server.socket_host': ip})
    cherrypy.config.update({'server.socket_port': 8080})
    cherrypy.engine.start()
    cherrypy.engine.block()