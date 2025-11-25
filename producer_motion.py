import requests
import json
import random
import time

# HEDEF: Room 001
ENTITY_ID = "urn:ngsi-ld:Room:001"
URL = f"http://localhost:1026/ngsi-ld/v1/entities/{ENTITY_ID}/attrs"
HEADERS = {"Content-Type": "application/ld+json"}
NGSI_LD_CONTEXT = ["https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"]

print(f"🏃🏃🏃 Motion Sensor (Pub 2) Started for {ENTITY_ID}...")

while True:
    try:
        # 0 (Boş) veya 1 (Dolu) üret
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
            status_text = "OCCUPIED (1)" if occupancy_value == 1 else "EMPTY (0)"
            print(f"--> Room Status: {status_text}")
        else:
            print(f"Error: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"Connection Error: {e}")
    
    time.sleep(7) # 7 saniyede bir güncelle (farklı zamanlama olsun)