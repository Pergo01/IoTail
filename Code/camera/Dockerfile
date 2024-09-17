#dockerfile camera
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN apt-get update && apt-get install -y build-essential libgl1 libgtk2.0-dev psmisc
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["python", "camera.py"]
