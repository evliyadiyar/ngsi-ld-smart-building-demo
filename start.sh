#!/bin/bash

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Starting NGSI-LD Smart Building Demo...${NC}\n"
mkdir -p logs

# This start script only launches local producers and listeners.
# Provisioning (entities/subscriptions) is handled by `provision.sh`.

echo -e "${BLUE}Starting components (listeners + producers)...${NC}\n"

# Stop old processes
pkill -f "listener_room" 2>/dev/null || true
pkill -f "producer_" 2>/dev/null || true
sleep 1

echo -e "${BLUE}Starting components...${NC}\n"

# Start listeners (each room separate)
nohup env PYTHONUNBUFFERED=1 python listeners/listener_room_101.py > logs/listener_101.log 2>&1 &
echo -e "${GREEN}✓${NC} Listener Room 101 started"

nohup env PYTHONUNBUFFERED=1 python listeners/listener_room_201.py > logs/listener_201.log 2>&1 &
echo -e "${GREEN}✓${NC} Listener Room 201 started"

sleep 1

# Start producers
python producers/producer_temp_101.py > logs/producer_temp_101.log 2>&1 &
echo -e "${GREEN}✓${NC} Room 101 Producers started"

python producers/producer_motion_101.py > logs/producer_motion_101.log 2>&1 &

python producers/producer_temp_201.py > logs/producer_temp_201.log 2>&1 &
echo -e "${GREEN}✓${NC} Room 201 Producers started"

python producers/producer_motion_201.py > logs/producer_motion_201.log 2>&1 &

echo ""
echo -e "${GREEN}System running!${NC}"
echo -e "${BLUE}View logs:${NC}"
echo "  tail -f logs/listener_101.log"
echo "  tail -f logs/listener_201.log"
echo ""
echo -e "${BLUE}Stop:${NC} ./stop.sh"
echo ""
