import requests
import json
import random
import time

# Room 101 (Floor 1)
ENTITY_ID = "urn:ngsi-ld:Room:101"
URL = f"http://localhost:1026/ngsi-ld/v1/entities/{ENTITY_ID}/attrs"
HEADERS = {"Content-Type": "application/ld+json"}

# Context
NGSI_LD_CONTEXT = ["https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"]

print(f"Thermostat producer started for {ENTITY_ID}")

while True:
    try:
        # rand btw 20.0 and 30.0
        new_temp = round(random.uniform(20.0, 30.0), 2)
        
        payload = {
            "temperature": {
                "type": "Property",
                "value": new_temp
            },
            "@context": NGSI_LD_CONTEXT
        }

        response = requests.patch(URL, headers=HEADERS, data=json.dumps(payload))
        
        if response.status_code == 204:
            print(f"[Room 101] Temperature: {new_temp}°C")
        else:
            print(f"Error: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"Connection Error: {e}")
    
    time.sleep(5) # update every 5 seconds