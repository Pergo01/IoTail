#dockerfile thingspeak adaptor
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "thingspeak_adaptor.py"]