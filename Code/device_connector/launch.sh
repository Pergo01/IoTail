#!/bin/bash

python motion_sensor_connector.py &
sleep 1s
python temp_humid_connector.py &
sleep 1s
python led_connector.py &
sleep 1s
tail -f /dev/null
