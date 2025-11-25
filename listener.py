from flask import Flask, request
import json

app = Flask(__name__)

@app.route("/listener", methods=["POST"])
def listener():
    # Parse the incoming JSON payload
    content = request.json
    
    # NGSI-LD notifications usually send a "data" array.
    # We normalize the input to ensure we always iterate over a list.
    if isinstance(content, dict) and 'data' in content:
        data_list = content['data']
    elif isinstance(content, list):
        data_list = content
    else:
        data_list = [content]

    print("\n--- 🔔 NOTIFICATION RECEIVED ---")

    for entity in data_list:
        entity_id = entity.get('id', 'Unknown ID')
        
        print(f"📦 Entity: {entity_id}")
        
        # Log temperature update if present
        if 'temperature' in entity:
            val = entity['temperature']['value']
            print(f"   🌡️  Temperature: {val}")
            
        # Log occupancy update if present
        if 'occupancy' in entity:
            val = entity['occupancy']['value']
            print(f"   🏃 Occupancy:    {val}")

    print("-" * 30)
    
    # Acknowledge receipt to the Broker
    return "OK", 200

if __name__ == "__main__":
    print("📡 Context Monitor running on port 3000...")
    app.run(host='0.0.0.0', port=3000)