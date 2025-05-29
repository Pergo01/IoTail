#!/bin/bash

# This script launches multiple Python scripts to connect to various devices.
python motion_sensor_connector.py &
sleep 1s
python temp_humid_connector.py &
sleep 1s
python led_connector.py &
sleep 1s
tail -f /dev/null # Keep the script running to maintain the connections