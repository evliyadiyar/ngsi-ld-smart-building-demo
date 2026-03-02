#!/usr/bin/env python3
"""
NGSI-LD Subscription Creator
Creates subscriptions for entity changes and sends notifications to listener
"""

import requests
import json
import sys
import logging
import argparse

# Configuration
ORION_URL = "http://localhost:1026/ngsi-ld/v1"
CONTEXT = "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"

# Listener endpoint (Flask server on host machine)
# Use host.docker.internal for Docker containers to access host
# Port 5001 (not 5000, which is used by macOS AirPlay Receiver)
LISTENER_URL = "http://host.docker.internal:5001/notify"


def subscription_exists(subscription_id: str) -> bool:
    """Check if subscription exists in Orion-LD"""
    url = f"{ORION_URL}/subscriptions/{subscription_id}"

    try:
        response = requests.get(url, timeout=10)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def create_subscription(subscription_data: dict, skip_if_exists: bool = False) -> bool:
    """Create a subscription in Orion-LD"""
    sub_id = subscription_data.get('id', '')

    # Check if subscription already exists (optional)
    if skip_if_exists and sub_id:
        if subscription_exists(sub_id):
            logging.info(f"⚠ Subscription already exists, skipping: {sub_id}")
            logging.info(f"  Entity type: {subscription_data.get('entities', [{}])[0].get('type', 'N/A')}")
            return True

    url = f"{ORION_URL}/subscriptions/"
    headers = {
        "Content-Type": "application/ld+json"
    }

    try:
        response = requests.post(url, json=subscription_data, headers=headers, timeout=10)

        if response.status_code == 201:
            # Extract subscription ID from Location header
            location = response.headers.get('Location', '')
            sub_id_from_location = location.split('/')[-1] if location else sub_id
            logging.info(f"✓ Created subscription: {sub_id_from_location}")
            logging.info(f"  Entity type: {subscription_data.get('entities', [{}])[0].get('type', 'N/A')}")
            logging.info(f"  Description: {subscription_data.get('description', 'N/A')}")
            return True
        elif response.status_code == 409:
            logging.warning(f"⚠ Subscription already exists (409 Conflict): {sub_id}")
            logging.warning(f"  This should not happen if --skip-clean is used properly")
            return True
        else:
            logging.error(f"✗ Failed to create subscription: {response.status_code}")
            logging.error(f"  Response: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        logging.error(f"✗ Connection error: {e}")
        return False


def delete_subscription(subscription_id: str) -> bool:
    """Delete a subscription from Orion-LD"""
    url = f"{ORION_URL}/subscriptions/{subscription_id}"

    try:
        response = requests.delete(url, timeout=10)

        if response.status_code == 204:
            logging.info(f"✓ Deleted subscription: {subscription_id}")
            return True
        elif response.status_code == 404:
            logging.warning(f"⚠ Subscription not found: {subscription_id}")
            return True
        else:
            logging.error(f"✗ Failed to delete subscription: {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        logging.error(f"✗ Connection error: {e}")
        return False


def list_subscriptions() -> list:
    """List all subscriptions in Orion-LD"""
    url = f"{ORION_URL}/subscriptions/"
    headers = {
        "Accept": "application/ld+json"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f"✗ Failed to list subscriptions: {response.status_code}")
            return []

    except requests.exceptions.RequestException as e:
        logging.error(f"✗ Connection error: {e}")
        return []


def clean_all_subscriptions():
    """Delete all subscriptions"""
    logging.info("Cleaning existing subscriptions...")

    subscriptions = list_subscriptions()

    if not subscriptions:
        logging.info("No subscriptions to delete")
        return

    for sub in subscriptions:
        sub_id = sub.get('id', '').split('/')[-1]
        if sub_id:
            delete_subscription(sub_id)

    logging.info(f"✓ Deleted {len(subscriptions)} subscriptions")


def create_energy_device_subscription(listener_url: str, skip_if_exists: bool = False) -> bool:
    """Create subscription for all EnergyDevice entities"""
    subscription = {
        "id": "urn:ngsi-ld:Subscription:EnergyDevices",
        "type": "Subscription",
        "description": "Notify on EnergyDevice property changes",
        "entities": [
            {
                "type": "EnergyDevice"
            }
        ],
        "watchedAttributes": ["activePower", "dailyEnergyConsumed", "apparentPower"],
        "notification": {
            "endpoint": {
                "uri": listener_url,
                "accept": "application/json"
            },
            "format": "normalized"
        },
        "@context": [CONTEXT]
    }

    return create_subscription(subscription, skip_if_exists=skip_if_exists)


def create_sensor_subscription(listener_url: str, skip_if_exists: bool = False) -> bool:
    """Create subscription for all Sensor entities"""
    subscription = {
        "id": "urn:ngsi-ld:Subscription:Sensors",
        "type": "Subscription",
        "description": "Notify on Sensor property changes",
        "entities": [
            {
                "type": "Sensor"
            }
        ],
        "watchedAttributes": ["temperature", "relativeHumidity", "occupancy", "doorState"],
        "notification": {
            "endpoint": {
                "uri": listener_url,
                "accept": "application/json"
            },
            "format": "normalized"
        },
        "@context": [CONTEXT]
    }

    return create_subscription(subscription, skip_if_exists=skip_if_exists)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='NGSI-LD Subscription Manager',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create subscriptions (default: cleans old ones first)
  python3 create_subscriptions.py

  # Skip cleanup, only create if not exists (no duplicates)
  python3 create_subscriptions.py --skip-clean

  # List existing subscriptions
  python3 create_subscriptions.py --list

  # Clean all subscriptions only
  python3 create_subscriptions.py --clean-only

  # Custom listener endpoint
  python3 create_subscriptions.py --listener http://192.168.1.100:5001/notify
        """
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List existing subscriptions'
    )
    parser.add_argument(
        '--skip-clean',
        action='store_true',
        help='Skip deleting existing subscriptions (default: always clean first)'
    )
    parser.add_argument(
        '--clean-only',
        action='store_true',
        help='Only clean existing subscriptions (do not create new ones)'
    )
    parser.add_argument(
        '--listener',
        type=str,
        default=LISTENER_URL,
        help=f'Listener endpoint URL (default: {LISTENER_URL})'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Update listener URL if specified
    listener_url = args.listener if args.listener else LISTENER_URL

    # Setup logging
    log_level = logging.INFO if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(message)s'
    )

    # Banner
    print("=" * 60)
    print("NGSI-LD Subscription Manager")
    print("=" * 60)
    print(f"Target: {ORION_URL}")
    print(f"Listener: {listener_url}")
    print("=" * 60)
    print()

    # List subscriptions
    if args.list:
        subscriptions = list_subscriptions()
        if subscriptions:
            print(f"Found {len(subscriptions)} subscriptions:\n")
            for sub in subscriptions:
                sub_id = sub.get('id', 'N/A')
                description = sub.get('description', 'N/A')
                entity_type = sub.get('entities', [{}])[0].get('type', 'N/A')
                print(f"  ID: {sub_id}")
                print(f"  Description: {description}")
                print(f"  Entity Type: {entity_type}")
                print()
        else:
            print("No subscriptions found.")
        return

    # Clean existing subscriptions (unless --skip-clean)
    if not args.skip_clean:
        clean_all_subscriptions()
        print()
    else:
        logging.info("Skipping cleanup (--skip-clean flag used)")
        logging.info("Will skip creation if subscriptions already exist\n")

    if args.clean_only:
        print("Cleanup completed.")
        return

    # Create new subscriptions
    print("Creating subscriptions...\n")

    success_count = 0

    # Pass skip_if_exists=True when --skip-clean is used
    skip_if_exists = args.skip_clean

    if create_energy_device_subscription(listener_url, skip_if_exists=skip_if_exists):
        success_count += 1

    if create_sensor_subscription(listener_url, skip_if_exists=skip_if_exists):
        success_count += 1

    print()
    print("=" * 60)
    print(f"✓ Created {success_count}/2 subscriptions")
    print("=" * 60)
    print()
    print("Subscriptions are now active!")
    print(f"Notifications will be sent to: {listener_url}")
    print()
    print("Next steps:")
    print("  1. Start the listener: python3 listener.py")
    print("  2. Run the producer: python3 producer.py --fast --limit 100")
    print("  3. Check listener output for notifications")


if __name__ == "__main__":
    main()
