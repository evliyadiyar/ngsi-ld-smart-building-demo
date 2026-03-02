#!/usr/bin/env python3
"""
NGSI-LD Notification Listener
Receives notifications from Orion-LD subscriptions and exports data for ML
"""

from flask import Flask, request, jsonify
import json
import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import argparse

app = Flask(__name__)

# Configuration
OUTPUT_DIR = Path(__file__).parent / "ml_data"
OUTPUT_DIR.mkdir(exist_ok=True)

# Statistics
stats = {
    "total_notifications": 0,
    "energy_device_updates": 0,
    "sensor_updates": 0,
    "errors": 0
}


def extract_property_data(entity: Dict[str, Any]) -> Dict[str, Any]:
    """Extract property values from NGSI-LD entity"""
    data = {
        "entity_id": entity.get("id", "unknown"),
        "entity_type": entity.get("type", "unknown")
    }

    # Extract all properties (excluding metadata fields)
    for key, value in entity.items():
        if key in ["id", "type", "@context", "refRoom", "refFloor", "refBuilding"]:
            continue

        if isinstance(value, dict) and value.get("type") == "Property":
            property_value = value.get("value")
            observed_at = value.get("observedAt")

            data[key] = property_value
            data[f"{key}_observedAt"] = observed_at

            # Include unit code if present
            if "unitCode" in value:
                data[f"{key}_unit"] = value["unitCode"]

    return data


def write_to_csv(data: Dict[str, Any], entity_type: str):
    """Write notification data to CSV - one file per property to avoid timestamp mismatches"""

    # Get all properties (excluding metadata)
    properties = [k for k in data.keys() if not k.endswith('_observedAt') and not k.endswith('_unit') and k not in ['entity_id', 'entity_type']]

    if not properties:
        logging.warning(f"  ⚠️ No properties found in notification")
        stats["errors"] += 1
        return

    logging.debug(f"  Properties: {properties}")

    # Write each property to its own CSV file
    files_written = 0

    for prop in properties:
        # Get property metadata
        value = data.get(prop)
        observed_at = data.get(f"{prop}_observedAt")
        unit = data.get(f"{prop}_unit")

        # Skip if no observedAt (invalid data)
        if not observed_at:
            logging.warning(f"  ⚠️ No observedAt for {prop}, skipping")
            continue

        # Determine filename and fieldnames based on property
        filename = f"{prop}_data.csv"
        fieldnames = ["entity_id", prop, "observedAt"]
        if unit:
            fieldnames.append("unit")

        filepath = OUTPUT_DIR / filename
        file_exists = filepath.exists()

        try:
            with open(filepath, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)

                if not file_exists:
                    writer.writeheader()

                # Write row with proper column names
                row = {
                    "entity_id": data.get("entity_id"),
                    prop: value,
                    "observedAt": observed_at
                }
                if unit:
                    row["unit"] = unit

                writer.writerow(row)

            files_written += 1
            logging.debug(f"  ✓ Wrote {prop} to {filename}")

        except Exception as e:
            logging.error(f"  ✗ Failed to write {prop} to {filename}: {e}")
            stats["errors"] += 1

    if files_written > 0:
        logging.info(f"  ✓ Wrote {files_written} properties to CSV files")


@app.route('/notify', methods=['POST'])
def handle_notification():
    """Handle NGSI-LD notification"""
    global stats

    stats["total_notifications"] += 1

    try:
        # Get notification data
        notification = request.get_json()

        if not notification:
            logging.warning("Received empty notification")
            return jsonify({"status": "error", "message": "Empty notification"}), 400

        # Extract subscription ID and entities
        subscription_id = notification.get("subscriptionId", "unknown")
        entities = notification.get("data", [])

        logging.info(f"\n[Notification #{stats['total_notifications']}]")
        logging.info(f"Subscription: {subscription_id}")
        logging.info(f"Entities: {len(entities)}")

        # Process each entity in the notification
        for entity in entities:
            entity_id = entity.get("id", "unknown")
            entity_type = entity.get("type", "unknown")

            logging.info(f"\n  Entity: {entity_id}")
            logging.info(f"  Type: {entity_type}")

            # Extract property data
            property_data = extract_property_data(entity)

            # Log property values
            for key, value in property_data.items():
                if not key.endswith("_observedAt") and not key.endswith("_unit") and key not in ["entity_id", "entity_type", "timestamp"]:
                    logging.info(f"    {key}: {value}")

            # Write to CSV for ML
            write_to_csv(property_data, entity_type)

            # Update statistics
            if entity_type == "EnergyDevice":
                stats["energy_device_updates"] += 1
            elif entity_type == "Sensor":
                stats["sensor_updates"] += 1

        return jsonify({"status": "success", "processed": len(entities)}), 200

    except Exception as e:
        logging.error(f"Error processing notification: {e}")
        stats["errors"] += 1
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/stats', methods=['GET'])
def get_stats():
    """Get listener statistics"""
    return jsonify(stats), 200


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "stats": stats}), 200


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='NGSI-LD Notification Listener',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start listener on default port (5000)
  python3 listener.py

  # Start listener on custom port
  python3 listener.py --port 8080

  # Enable verbose logging
  python3 listener.py --verbose

Endpoints:
  POST /notify    - Receive NGSI-LD notifications
  GET  /stats     - View listener statistics
  GET  /health    - Health check
        """
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5001,
        help='Port to listen on (default: 5001)'
    )
    parser.add_argument(
        '--host',
        type=str,
        default='0.0.0.0',
        help='Host to bind to (default: 0.0.0.0)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.INFO if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    # Banner
    print("=" * 60)
    print("NGSI-LD Notification Listener")
    print("=" * 60)
    print(f"Listening on: http://{args.host}:{args.port}")
    print(f"Notification endpoint: POST /notify")
    print(f"ML data output: {OUTPUT_DIR}")
    print("=" * 60)
    print("\nPress Ctrl+C to stop\n")

    # Disable Flask's default request logging (we handle it ourselves)
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    # Start Flask server
    try:
        app.run(host=args.host, port=args.port, debug=False)
    except KeyboardInterrupt:
        print("\n\nListener stopped.")
        print("\nStatistics:")
        print(f"  Total notifications: {stats['total_notifications']}")
        print(f"  Energy device updates: {stats['energy_device_updates']}")
        print(f"  Sensor updates: {stats['sensor_updates']}")
        print(f"  Errors: {stats['errors']}")


if __name__ == "__main__":
    main()
