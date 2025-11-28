import requests
import json
import random
import time

# Room 201 (Floor 2)
ENTITY_ID = "urn:ngsi-ld:Room:201"
URL = f"http://localhost:1026/ngsi-ld/v1/entities/{ENTITY_ID}/attrs"
HEADERS = {"Content-Type": "application/ld+json"}

# Context
NGSI_LD_CONTEXT = ["https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"]

print(f"Thermostat producer started for {ENTITY_ID}")

while True:
    try:
        new_temp = round(random.uniform(18.0, 28.0), 2)

        payload = {
            "temperature": {
                "type": "Property",
                "value": new_temp
            },
            "@context": NGSI_LD_CONTEXT
        }

        response = requests.patch(URL, headers=HEADERS, data=json.dumps(payload))

        if response.status_code == 204:
            print(f"[Room 201] Temperature: {new_temp}°C")
        else:
            print(f"Error: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"Connection Error: {e}")

    time.sleep(6)
