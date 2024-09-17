from Libraries import Subscriber
import json
import time
import subprocess
import sys
import socket


class Camera:
    def __init__(self, clientID, broker, port, ip):
        self.clientID = clientID
        self.broker = broker
        self.port = port
        self.client = Subscriber(clientID, broker, port, self)
        self.stream_process = None
        self.ip = ip

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
        command = 'killall mjpeg-streamer'
        print("Stream stopped.")
        return subprocess.Popen(command, shell=True)


if __name__ == "__main__":
    settings = json.load(open("mqtt_settings.json"))
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    camera = Camera("Camera", settings["broker"], settings["port"], ip)
    camera.start()
    camera.subscribe(settings["baseTopic"] + "/kennel1/camera", 0)
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            break
    camera.stop()
