# IoTail Project

This project implements an IoT platform for monitoring and managing public shared dog kennels.
It is meant to be used with a companion app, which can be found in the [IoTail Companion](https://github.com/Pergo01/IoTail_Companion.git) repository.

⚠️ Please, setup this project before working with the app.

## Setup

1. Install [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/install/).
2. Clone this repository.
3. Navigate to the project directory.
4. Go to the [Thingspeak](https://thingspeak.mathworks.com/) website, create an account or log in, create a new channel and then note the channel ID and the write and read API keys of the channel, from the "API Keys" section.
4. Create the file `settings.json` with the following structure (do not change catalog url) and put it inside the root directory:
    ```json
    {
        "catalog_url": "http://catalog:8080",
        "channel_id": 1234567,
        "thingspeak_write_api_key": "your_channel_write_api_key",
        "thingspeak_read_api_key": "your_channel_read_api_key"
    }
    ```
5. Create the file `secret_key.txt` with a secret word inside to crypt your tokens and place it inside the root directory
6. Go to the [Firebase Console](https://console.firebase.google.com/) website, log in with your google account and create a new project to use with the IoTail companion app (Flutter)
7. Go into the project settings -> service account, click on Python and then on "Generate new private key". Confirm the generation.
8. Rename the json file to `firebase_account_key.json` and copy it to the root folder of this project
9. Go to [mailgun.com](https://www.mailgun.com/) and create an account. In the main page of your account, note the "sending domain", click on your account at the top right corner and go to "API Security", add a new key and copy it.
10. Create the file `.env` in the "catalog" folder with this structure:
```bash
MAILGUN_API_KEY= "your_mailgun_api_key"
MAILGUN_API_URL= "https://api.mailgun.net/v3/your_sending_domain/messages"
FROM_EMAIL_ADDRESS= "Your_Sender <your_sender@email.com>"
```
11. From the left menu, go to "Domain settings" in the "SEND" tab, go to "Setup", add an email address you want to send your email to (unfortunately, free mailgun accounts can only send emails to maximum 5 verified accounts) and verify it through the email you receive.
12. In a terminal, run `docker-compose up -d --build` from the root directory of the project to build and start all services.

## Services

- Catalog: Manages system information
- Device Connector: Connect sensors to the IoT platform
- Camera: Manages video feed
- Data Analysis: Processes sensors data
- Reservation Manager: Handles kennel reservations
- ThingSpeak Adaptor: Integrates the platform with ThingSpeak
- Disinfection System: Manages kennel disinfection (simulation)

## Devices

All connections are referred to a Raspberry Pi 3 model B
- USB Camera
- Adafruit DHT Temperature and Humidity sensor, plugged to pin 15
- Dfrobot DSN-FIR800 Motion sensor, plugged to pin 14
- Green, Yellow, Red LEDs, plugged through a breadboard, respectively, to pin 21, 26 and 16

To check services and devices status (assuming catalog is online), go to *http://your_server_ip:8080/status_page*

## Usage

After building, only two commands are needed:
- `docker compose stop` to stop the containers
- `docker compose start` to start the containers
- `docker compose restart` to restart the containers

Additionally, if only specific containers need to be stopped/started/restarted, it is sufficient to put their name after the commands above, separated by a space.
The commands are meant to be run in the terminal inside the root directory of the project.

## Mock users for testing

There are two mock users:
- John Doe
    - email: john.doe@gmail.com
    - password: 123456789

    User with one dog already present
- Johanna Doe
    - email: johanna.doe@gmail.com
    - password: 987654321

    Completely empty user

<!--

## Contributing

[Add contribution guidelines here]

## License

[Add license information here] -->