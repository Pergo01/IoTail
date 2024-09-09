		#dockerfile device connector
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
COPY Libraries /app/Libraries
RUN apt-get update && apt-get install -y build-essential git
RUN pip install --no-cache-dir -r requirements.txt
RUN git clone https://github.com/adafruit/Adafruit_Python_DHT.git
RUN cd Adafruit_Python_DHT && python setup.py install --force-pi
RUN pip install lgpio pigpio gpio gpiozero
RUN apt install -y wget
RUN wget https://github.com/Gadgetoid/PY_LGPIO/releases/download/0.2.2.0/lgpio-0.2.2.0.tar.gz
RUN pip install lgpio-0.2.2.0.tar.gz
RUN rm -rf Adafruit_Python_DHT
COPY . .
RUN chmod a+x launch.sh

# CMD ["python", "device_connector.py"]
CMD ["./launch.sh"]
# CMD ["sleep", "3600s"]
