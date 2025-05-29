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
        self.client = Subscriber(
            clientID, broker, port, self
        )  # Initialize the MQTT client
        self.stream_process = None
        self.ip = ip
        self.catalog_url = json.load(open("settings.json"))[
            "catalog_url"
        ]  # Load catalog URL from settings

    def start(self):
        """Starts the MQTT client and connects to the broker"""
        self.client.start()  # Start the MQTT client
        time.sleep(1)

    def notify(self, topic, msg):
        """Handles incoming MQTT messages to start or stop the camera stream"""
        message = json.loads(msg)
        # print(message)
        if (
            message["message"] == "on" and self.stream_process is None
        ):  # Check if the stream is not already running
            print("Starting the camera stream...")
            self.stream_process = self.run()  # Start the camera stream
        elif (
            message["message"] == "off" and self.stream_process is not None
        ):  # Check if the stream is running
            print("Stopping the camera stream...")
            self.close()  # Stop the camera stream
            self.stream_process = None  # Reset the stream process

    def subscribe(self, topic, QoS):
        """Subscribes to a specific MQTT topic"""
        self.client.subscribe(topic, QoS)  # Subscribe to the specified topic

    def stop(self):
        """Stops the MQTT client and cleans up resources"""
        self.client.stop()  # Stop the MQTT client

    def run(self):
        """Starts the mjpeg-streamer process to stream video from the camera"""
        try:
            # Run the mjpeg-streamer command as a subprocess
            command = (
                "mjpeg-streamer --host "
                + ip
                + ' --port 8090 -s 0 --prefix "camera" --width 1920 --height 1080 --quality 75 --fps 30 &'
            )
            return subprocess.Popen(
                command, shell=True
            )  # Execute the command to start the stream
        except Exception as e:
            print(f"Error starting stream: {e}")
            sys.exit(1)

    def close(self):
        """Stops the mjpeg-streamer process and cleans up resources"""
        if self.stream_process:  # Check if the stream process is running
            self.stream_process.terminate()  # Terminate the stream process
        command = "killall mjpeg-streamer"  # Command to stop the stream
        print("Stream stopped.")
        return subprocess.Popen(
            command, shell=True
        )  # Execute the command to stop the stream

    def heartbeat(self):
        """Sends a heartbeat signal to the catalog service every 60 seconds"""
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
                response = requests.post(
                    url, headers=headers, data=json.dumps(payload)
                )  # Send heartbeat to the catalog service
                if response.status_code == 200:  # if response is ok
                    print("Heartbeat sent successfully")
                else:  # if response is not ok
                    print("Failed to send heartbeat")
            except (
                requests.exceptions.RequestException
            ) as e:  # Handle any request exceptions
                print(f"Error sending heartbeat: {e}")
            time.sleep(60)  # Wait for 60 seconds before sending the next heartbeat


def signal_handler(sig, frame):
    """Handles Ctrl+C to stop the camera cleanly"""
    print("\nStopping MQTT Camera service...")
    camera.stop()


if __name__ == "__main__":
    settings = json.load(open("mqtt_settings.json"))  # Load MQTT settings
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]  # Get the local IP address
    s.close()
    camera = Camera(
        "Camera", settings["broker"], settings["port"], ip, 6
    )  # Instantiate the Camera class
    camera.start()  # Start the MQTT client

    heartbeat_thread = threading.Thread(
        target=camera.heartbeat
    )  # Create a thread for the heartbeat function
    heartbeat_thread.daemon = True  # The thread will terminate when the program ends
    heartbeat_thread.start()  # Start the heartbeat thread

    camera.subscribe(
        settings["baseTopic"] + "/kennel1/camera", 0
    )  # Subscribe to the camera topic (for now only kennel 1)

    # Wait for keyboardinterrupt
    signal.signal(signal.SIGINT, signal_handler)

    # Keep the script running without a while loop
    signal.pause()
