# IoTail Project

This project implements an IoT platform for monitoring and managing dog kennels.

## Setup

1. Install Docker and Docker Compose.
2. Clone this repository.
3. Navigate to the project directory.
4. Create the file `settings.json` with the following structure and put it inside the root directory:
    ```json
    {
        "catalog_url": "http://catalog:8080",
        "thingspeak_write_api_key": "your_channel_write_api_key",
        "thingspeak_read_api_key": "your_channel_read_api_key"
    }
    ```
5. Go to Firebase website, log in with your google account and create a new project to use with the IoTail companion app (Flutter)
6. Go into the project settings -> service account, click on Python and then on "Generate new private key". Confirm the generation.
7. Rename the json file to `firebase_account_key.json` and copy it to the root of this project
8. Go to https://www.mailgun.com/ and create an account. In the main page of your account, note the "sending domain", click on your account at the top right corner and go to "API Security", add a new key and copy it.
9. Create the file `.env` in the "catalog" folder with this structure:
```bash
MAILGUN_API_KEY= "your_mailgun_api_key"
MAILGUN_API_URL= "https://api.mailgun.net/v3/your_sending_domain/messages"
FROM_EMAIL_ADDRESS= "Your_Sender <your_sender@email.com>"
```
5. Run `docker-compose up --build` to start all services.

## Services

- Catalog: Manages system information
- Device Connector: Connect sensors to the IoT platform
- Camera: Manages video feed
- Data Analysis: Processes sensor data
- Reservation Manager: Handles kennel reservations
- ThingSpeak Adaptor: Integrates with ThingSpeak
- Disinfection System: Manages kennel disinfection

<!-- ## Usage

[Add usage instructions here]

## Contributing

[Add contribution guidelines here]

## License

[Add license information here] -->