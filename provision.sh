#!/usr/bin/env bash

# Provision script: create entities and subscriptions in Orion-LD
# Run this once (or re-run to create missing items). This script is simple and
# ignores 409 responses (entity already exists) to be idempotent.

BASE_URL="http://localhost:1026/ngsi-ld/v1"
HEADERS=( -H "Content-Type: application/ld+json" )

echo "Provisioning entities..."

# If entities already exist, delete them first so we recreate clean copies.
# This ensures a reproducible demo state.
ENTITIES=(
	"urn:ngsi-ld:Building:MainHQ"
	"urn:ngsi-ld:Floor:1"
	"urn:ngsi-ld:Floor:2"
	"urn:ngsi-ld:Room:101"
	"urn:ngsi-ld:Room:201"
)

for e in "${ENTITIES[@]}"; do
	echo "Checking entity: $e"
	code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/entities/$e") || code=0
	if [ "$code" = "200" ]; then
		echo "  Found existing $e — deleting..."
		curl -s -X DELETE "$BASE_URL/entities/$e" >/dev/null 2>&1 && echo "  Deleted $e"
	else
		echo "  Not present (HTTP $code)"
	fi
done

# Create entities (fresh)
echo "Creating Building..."
curl -s -o /dev/null -w "  HTTP %{http_code}\n" -X POST "$BASE_URL/entities/" "${HEADERS[@]}" -d @entities/building.json || true

echo "Creating Floor 1..."
curl -s -o /dev/null -w "  HTTP %{http_code}\n" -X POST "$BASE_URL/entities/" "${HEADERS[@]}" -d @entities/floor.json || true

echo "Creating Floor 2..."
curl -s -o /dev/null -w "  HTTP %{http_code}\n" -X POST "$BASE_URL/entities/" "${HEADERS[@]}" -d @entities/floor2.json || true

echo "Creating Room 101..."
curl -s -o /dev/null -w "  HTTP %{http_code}\n" -X POST "$BASE_URL/entities/" "${HEADERS[@]}" -d @entities/room_101.json || true

echo "Creating Room 201..."
curl -s -o /dev/null -w "  HTTP %{http_code}\n" -X POST "$BASE_URL/entities/" "${HEADERS[@]}" -d @entities/room_201.json || true

echo "\nProvisioning subscriptions..."

# Remove any existing demo subscriptions that target our listeners to avoid duplicates
SUB_ENDPOINTS=("http://host.docker.internal:3001/listener" "http://host.docker.internal:3002/listener")
for u in "${SUB_ENDPOINTS[@]}"; do
	echo "Checking subscriptions for endpoint: $u"
	if command -v jq >/dev/null 2>&1; then
		ids=$(curl -s "$BASE_URL/subscriptions/" | jq -r --arg u "$u" '.[] | select(.notification.endpoint.uri==$u) | .id')
	else
		ids=$(URI="$u" curl -s "$BASE_URL/subscriptions/" | python3 -c 'import sys,json,os; data=json.load(sys.stdin); u=os.environ.get("URI"); out=[s.get("id") for s in data if s.get("notification",{}).get("endpoint",{}).get("uri")==u]; print("\n".join([str(x) for x in out]))')
	fi

	for id in $ids; do
		if [ -n "$id" ]; then
			curl -s -X DELETE "$BASE_URL/subscriptions/$id" >/dev/null 2>&1 && echo "  Deleted subscription: $id"
		fi
	done
done

echo "Creating subscription for Room 101..."
curl -s -o /dev/null -w "  HTTP %{http_code}\n" -X POST "$BASE_URL/subscriptions/" "${HEADERS[@]}" -d @subscriptions/subscription_room_101.json || true

echo "Creating subscription for Room 201..."
curl -s -o /dev/null -w "  HTTP %{http_code}\n" -X POST "$BASE_URL/subscriptions/" "${HEADERS[@]}" -d @subscriptions/subscription_room_201.json || true

echo "\nOptional: apply attribute update (room_update.json) via PATCH if desired:"
echo "curl -s -X PATCH \"$BASE_URL/entities/urn:ngsi-ld:Room:101/attrs\" -H 'Content-Type: application/ld+json' -d @entities/room_update.json"

echo "Provisioning complete."
