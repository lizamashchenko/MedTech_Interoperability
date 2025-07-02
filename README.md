# MedTech_Interoperability

## Description
This repository represents a solution to interoperability communication between medical devices using FHIR standart. It implements multiple approaches to communication and allows multiple devices to be connected to the main server, and a client which displays the data in real-time.

- Local coomunication: for when the server and code is running on the same computer
- Websockets: for communication over the local area network (LAN)

## Prerequisite
The communication is done via the server. For testing it was decided to use HAPI FHIR sandbox. You can find the documentation on the [official website](https://hapifhir.io/). Follow the instruction on their [GitHub repository](https://github.com/jamesagnew/hapi-fhir)

## Usage
1. First start the HAPI FHIR server following instructions on [GitHub](https://github.com/hapifhir/hapi-fhir-jpaserver-starter)
2. After this navigate to the folder with the desired communication type
```bash
cd name-of-folder
```

For local communication:
1. Start the medical device simulators. Multiple instances are supported
   ```bash
    python .\medical-device-simulator.py <patient-id>
   ```
2. Start the observer
   ```bash
   python .\observer.py
   ```
3. Navigate to http://127.0.0.1:5000/ to see the webpage

For websocket communication:
1. Start the medical devices
   ```bash
   python .\translator_socket.py
   ```
2. Start the observer
   ```bash
   python .\app_socket.py
   ```
   
