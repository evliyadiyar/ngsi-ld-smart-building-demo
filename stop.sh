#!/bin/bash

# NGSI-LD Smart Building Demo - Stop Script

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Stopping NGSI-LD Smart Building Demo...${NC}\n"

# Kill by process name (more reliable)
echo -e "${BLUE}Stopping processes...${NC}"

pkill -f "listener_room"
echo -e "${GREEN}✓${NC} Listeners stopped"

pkill -f "producer_temp_101.py"
echo -e "${GREEN}✓${NC} Room 101 - Temperature Producer stopped"

pkill -f "producer_motion_101.py"
echo -e "${GREEN}✓${NC} Room 101 - Motion Producer stopped"

pkill -f "producer_temp_201.py"
echo -e "${GREEN}✓${NC} Room 201 - Temperature Producer stopped"

pkill -f "producer_motion_201.py"
echo -e "${GREEN}✓${NC} Room 201 - Motion Producer stopped"

# Clean up PID file
rm -f .pids

# Remove subscriptions that target our listeners (prevent duplicates on restart)
echo -e "\n${BLUE}Removing demo subscriptions (if any)...${NC}"
ENDPOINTS=("http://host.docker.internal:3001/listener" "http://host.docker.internal:3002/listener")
for uri in "${ENDPOINTS[@]}"; do
	echo -e "Removing subscriptions for ${uri}"
	if command -v jq >/dev/null 2>&1; then
		ids=$(curl -s http://localhost:1026/ngsi-ld/v1/subscriptions/ | jq -r --arg u "$uri" '.[] | select(.notification.endpoint.uri==$u) | .id')
	else
		# Use an inline python one-liner as a fallback (avoid heredoc to prevent quoting errors)
		ids=$(URI="$uri" curl -s http://localhost:1026/ngsi-ld/v1/subscriptions/ | python3 -c 'import sys, json, os
data = json.load(sys.stdin)
u = os.environ.get("URI")
out = []
for s in data:
	try:
		if s.get("notification", {}).get("endpoint", {}).get("uri") == u:
			out.append(s.get("id"))
	except Exception:
		pass
print("\n".join([str(x) for x in out]))')
	fi

	for id in $ids; do
		if [ -n "$id" ]; then
			curl -s -X DELETE "http://localhost:1026/ngsi-ld/v1/subscriptions/$id" >/dev/null 2>&1 && echo -e "  ${GREEN}Deleted:${NC} $id"
		fi
	done
done

sleep 1

echo ""
echo -e "${BLUE}=== AVAILABLE COMMANDS ===${NC}"
echo -e "View Docker containers:"
echo -e "  ${BLUE}docker ps${NC}"
echo ""
echo -e "Stop Docker containers:"
echo -e "  ${BLUE}docker compose down${NC}"
echo ""
echo -e "Remove all data (including MongoDB):"
echo -e "  ${BLUE}docker compose down -v${NC}"
echo ""
echo -e "${GREEN}All Python processes stopped!${NC}\n"
