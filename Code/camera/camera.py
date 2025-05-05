from Libraries import Subscriber
import json
import time
import subprocess
import sys
import socket
import requests
import threading
import signal


class Camera:
    def __init__(self, clientID, broker, port, ip, deviceID):
        self.clientID = clientID
        self.deviceID = deviceID
        self.broker = broker
        self.port = port
        self.client = Subscriber(clientID, broker, port, self)
        self.stream_process = None
        self.ip = ip
        self.catalog_url = json.load(open("settings.json"))["catalog_url"]

    def start(self):
        self.client.start()
        time.sleep(1)

    def notify(self, topic, msg):
        message = json.loads(msg)
        # print(message)
        if message["message"] == "on" and self.stream_process is None:
            print("Starting the camera stream...")
            self.stream_process = self.run()
        elif message["message"] == "off" and self.stream_process is not None:
            print("Stopping the camera stream...")
            self.close()
            self.stream_process = None

    def subscribe(self, topic, QoS):
        self.client.subscribe(topic, QoS)

    def stop(self):
        self.client.stop()

    def run(self):
        try:
            # Run the mjpeg-streamer command as a subprocess
            command = (
                "mjpeg-streamer --host "
                + ip
                + ' --port 8090 -s 0 --prefix "camera" --width 1920 --height 1080 --quality 75 --fps 30 &'
            )
            return subprocess.Popen(command, shell=True)
        except Exception as e:
            print(f"Error starting stream: {e}")
            sys.exit(1)

    def close(self):
        if self.stream_process:
            self.stream_process.terminate()
        command = "killall mjpeg-streamer"
        print("Stream stopped.")
        return subprocess.Popen(command, shell=True)

    def heartbeat(self):
        while True:
            try:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer camera",
                }
                url = self.catalog_url + "/heartbeat"
                payload = {
                    "category": "sensor",
                    "deviceID": self.deviceID,
                }
                response = requests.post(url, headers=headers, data=json.dumps(payload))
                if response.status_code == 200:
                    print("Heartbeat sent successfully")
                else:
                    print("Failed to send heartbeat")
            except requests.exceptions.RequestException as e:
                print(f"Error sending heartbeat: {e}")
            time.sleep(60)


def signal_handler(sig, frame):
    """Handles Ctrl+C to stop the camera cleanly"""
    print("\nStopping MQTT Camera service...")
    camera.stop()


if __name__ == "__main__":
    settings = json.load(open("mqtt_settings.json"))
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    camera = Camera("Camera", settings["broker"], settings["port"], ip, 6)
    camera.start()

    heartbeat_thread = threading.Thread(target=camera.heartbeat)
    heartbeat_thread.daemon = True  # The thread will terminate when the program ends
    heartbeat_thread.start()

    camera.subscribe(settings["baseTopic"] + "/kennel1/camera", 0)

    # Wait for keyboardinterrupt
    signal.signal(signal.SIGINT, signal_handler)

    # Keep the script running without a while loop
    signal.pause()
