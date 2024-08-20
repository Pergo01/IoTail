from Libraries import Publisher
import time
import json
import board
import adafruit_dht
import datetime


class TempHumidSensor:

    def __init__(self, clientID, broker, port):
        self.temp_humid_sensor = adafruit_dht.DHT11(board.D15, use_pulseio=False)
        self.broker = broker
        self.port = port
        self.client = Publisher(clientID, broker, port, self)

    def start(self):
        self.client.start()
        time.sleep(1)

    def publish(self, topic, message, QoS):
        self.client.publish(topic, message, QoS)

    def stop(self):
        self.client.stop()


if __name__ == "__main__":
    settings = json.load(open("mqtt_settings.json"))
    temp_humid_sensor = TempHumidSensor(
        "TempHumidSensor", settings["broker"], settings["port"]
    )
    temp_humid_sensor.start()

    while True:
        try:
            temp = temp_humid_sensor.temp_humid_sensor.temperature
            humid = temp_humid_sensor.temp_humid_sensor.humidity
            temp_humid_sensor.publish(
                settings["baseTopic"] + "/kennel1/sensors/temp_humid",
                {
                    "bn": "TempHumidSensor",
                    "e": [
                        {
                            "n": "temperature",
                            "u": "Cel",
                            "t": datetime.datetime.now().timestamp(),
                            "v": temp,
                        },
                        {
                            "n": "humidity",
                            "u": "%",
                            "t": datetime.datetime.now().timestamp(),
                            "v": humid,
                        },
                    ],
                },
                2,
            )
            time.sleep(1)
        except RuntimeError as error:
            # Errors happen fairly often, DHT's are hard to read, just keep going
            print(error.args[0])
            time.sleep(2.0)
            continue
        except Exception as error:
            temp_humid_sensor.exit()
            raise error
        except KeyboardInterrupt:
            break
    temp_humid_sensor.stop()


