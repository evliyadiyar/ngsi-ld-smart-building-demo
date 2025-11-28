from flask import Flask, request
import json
from datetime import datetime
import logging
import sys

# Suppress Flask logging
logging.getLogger('flask').setLevel(logging.ERROR)
logging.getLogger('werkzeug').setLevel(logging.ERROR)

app = Flask(__name__)
app.logger.disabled = True

ROOM_ID = "urn:ngsi-ld:Room:101"

@app.route("/listener", methods=["POST"])
def listener():
    content = request.json
    
    if isinstance(content, dict) and 'data' in content:
        data_list = content['data']
    elif isinstance(content, list):
        data_list = content
    else:
        data_list = [content]

    for entity in data_list:
        entity_id = entity.get('id', '')
        
        # Only process Room 101
        if entity_id != ROOM_ID:
            continue
            
        timestamp = datetime.now().strftime("%H:%M:%S")
        updates = []
        
        if 'temperature' in entity:
            temp = entity['temperature']['value']
            updates.append(f"{temp}°C")
        
        if 'occupancy' in entity:
            occ = entity['occupancy']['value']
            updates.append(f"Occupancy: {occ}")
        
        if updates:
            output = f"[{timestamp}] {' | '.join(updates)}"
            print(output, flush=True)
            sys.stdout.flush()
    
    return "OK", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=3001, debug=False, use_reloader=False, threaded=True)
