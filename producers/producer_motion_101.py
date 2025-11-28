import requests
import json
import random
import time

# Room 101 (Floor 1)
ENTITY_ID = "urn:ngsi-ld:Room:101"
URL = f"http://localhost:1026/ngsi-ld/v1/entities/{ENTITY_ID}/attrs"
HEADERS = {"Content-Type": "application/ld+json"}
NGSI_LD_CONTEXT = ["https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"]

print(f"Motion sensor producer started for {ENTITY_ID}")

while True:
    try:
        occupancy_value = random.choice([0, 1])

        payload = {
            "occupancy": {
                "type": "Property",
                "value": occupancy_value
            },
            "@context": NGSI_LD_CONTEXT
        }

        response = requests.patch(URL, headers=HEADERS, data=json.dumps(payload))

        if response.status_code == 204:
            status_text = "occupied" if occupancy_value == 1 else "empty"
            print(f"[Room 101] Occupancy: {status_text}")
        else:
            print(f"Error: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"Connection Error: {e}")

    time.sleep(7)