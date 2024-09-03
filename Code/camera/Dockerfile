#dockerfile camera
FROM python:3.9-slim

WORKDIR /app
COPY motion.txt .

# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get update && apt-get install -y motion
# RUN apt-get install -y motion
# RUN motion --version
RUN rm /etc/motion/motion.conf
RUN cp motion.txt /etc/motion/motion.conf
# RUN mv /etc/motion/motion.txt /etc/motion/motion.conf
# RUN apt-get update && apt-get install -y libgl1-mesa-glx

COPY . .

#CMD ["motion"]
#ENTRYPOINT ["tail", "-f", "/dev/null"]
CMD ["sh", "-c", "motion && tail -f /dev/null"]
