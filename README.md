# NGSI-LD Proof-of-Concept: A Smart Building Scenario

This project serves as a practical demonstration of a real-time context management system built on the ETSI NGSI-LD standard. It simulates a multi-floor smart building environment where data from multiple, independent sensors is aggregated and monitored through a centralized Context Broker.

The primary goal is to illustrate the core principles of NGSI-LD, including hierarchical data modeling, multi-source data publishing, and event-driven subscriptions across multiple floors and rooms.

## Platform Compatibility

This project is developed and tested on macOS. The following table summarizes platform support and known differences:

| Feature | macOS | Linux | Windows |
|---------|-------|-------|---------|
| `./start.sh` and `./stop.sh` | Full support | Full support | Requires Git Bash or WSL |
| `tail -f logs/` | Native support | Native support | Requires PowerShell or WSL |
| `pkill` command | Native support | Native support | Requires `taskkill` alternative |
| Docker Desktop | Supported (Rosetta 2 emulation for ARM) | Native support | Native support |
| Python command | `python` or `python3` | Typically `python3` | Typically `python` |

### Windows Compatibility Notes

Users on Windows should employ one of the following approaches:

1. **Windows Subsystem for Linux 2 (WSL2)** - The preferred approach. All bash commands and shell operations function identically within WSL2 environment.

2. **Git Bash** - Install Git for Windows, which includes Git Bash shell. Execute scripts using `bash ./start.sh`.

3. **PowerShell with Manual Setup** - For systems without WSL2 or Git Bash support, follow the "Manual Setup" section and adapt commands as follows:
   - Bash script execution: Follow the manual provisioning steps outlined below
   - File monitoring: Use `Get-Content -Tail 10 -Wait logs/listener_101.log` instead of `tail -f`
   - Process termination: Use `taskkill /F /IM python.exe` instead of `pkill -f listener_room`

## Architecture

The system is composed of three distinct layers, demonstrating a decoupled, event-driven architecture:

1. **Context Broker (FIWARE Orion-LD):** Acts as the central data management system. It maintains the digital twin of the building, including its structure and the real-time state of its rooms. Data persistence is provided by a MongoDB database.

2. **Data Producers (producers/):** These Python scripts simulate IoT sensor devices that publish data updates to the Context Broker.
   - `producer_temp_101.py`: Temperature sensor simulator for Floor 1, Room 101
   - `producer_motion_101.py`: Motion/occupancy sensor simulator for Floor 1, Room 101
   - `producer_temp_201.py`: Temperature sensor simulator for Floor 2, Room 201
   - `producer_motion_201.py`: Motion/occupancy sensor simulator for Floor 2, Room 201

3. **Data Consumers (Python/Flask):**
   - `listeners/listener_room_101.py`: Notification listener service for Room 101 (port 3001)
   - `listeners/listener_room_201.py`: Notification listener service for Room 201 (port 3002)
   
   Each listener is isolated and processes only notifications for its designated room, providing independent monitoring channels for each physical space.

### System Architecture Diagram

```
    Floor 1 Producers              Floor 2 Producers
 [ producer_temp_101   ]        [   producer_temp_201 ]
 [ producer_motion_101 ]        [ producer_motion_201 ]
           |                              |
           | PATCH updates                | PATCH updates
           v                              v
 +----------------------------------------------------------+
 |              ORION-LD CONTEXT BROKER                     |
 |                                                          |
 |  Building:MainHQ                                         |
 |    └─ Floor:1                Floor:2                     |
 |         └─ Room:101           └─ Room:201                |
 |            • temp: 22.5          • temp: 19.3            |
 |            • occupancy: 1        • occupancy: 0          |
 |                                                          |
 |  Subscription:Room:101        Subscription:Room:201      |
 |          ↓                              ↓                |
 +----------------------------------------------------------+
      Port 3001                      Port 3002
        ↓                              ↓
  +--------------+            +--------------+
  | listener_    |            | listener_    |
  | room_101.py  |            | room_201.py  |
  +--------------+            +--------------+
```

## Data Model

The context data follows a hierarchical structure using NGSI-LD Property and Relationship attributes:

- **Building:** Top-level entity (urn:ngsi-ld:Building:MainHQ)
- **Floor:** Entities linked to the building via refBuilding relationship (urn:ngsi-ld:Floor:1 and urn:ngsi-ld:Floor:2)
- **Room:** Entities linked to their respective floors via refFloor relationship (urn:ngsi-ld:Room:101 and urn:ngsi-ld:Room:201)

This hierarchical model ensures data integration across multiple floors and rooms, supporting complex spatial queries over the context graph.

## Setup and Execution

### System Requirements

- Docker and Docker Compose
- Python 3.x with the following packages: `requests`, `Flask`
- Git Bash or WSL2 (Windows systems only)
- macOS or Linux (native bash support)

### Automated Execution

On macOS and Linux systems, first start the Docker containers, then execute the automation script:

```bash
# Step 1: Start Docker containers
docker compose up -d

# Step 2: Run the automation script
./start.sh
```

The automation script performs the following operations:
- Provisions all entities and relationships in the context broker
- Establishes subscription rules for room-based notifications
- Launches listener services (ports 3001 and 3002)
- Starts producer processes to generate sensor data

Monitor system output in separate terminals:

```bash
tail -f logs/listener_101.log
tail -f logs/listener_201.log
```

Terminate all processes using:

```bash
./stop.sh
```

### Manual Setup (Platform-Independent)

For systems without bash support or requiring granular control, follow these steps:

#### Step 1: Initialize Infrastructure

Launch the Docker containers:

```bash
docker compose up -d
```

#### Step 2: Provision Data Models

Create entities and subscriptions by executing the following curl commands:

```bash
# Create Building entity
curl -X POST "http://localhost:1026/ngsi-ld/v1/entities/" \
  -H "Content-Type: application/ld+json" -d @entities/building.json

# Create Floor entities
curl -X POST "http://localhost:1026/ngsi-ld/v1/entities/" \
  -H "Content-Type: application/ld+json" -d @entities/floor.json

curl -X POST "http://localhost:1026/ngsi-ld/v1/entities/" \
  -H "Content-Type: application/ld+json" -d @entities/floor2.json

# Create Room 101 (with Floor 1 relationship)
curl -X POST "http://localhost:1026/ngsi-ld/v1/entities/" \
  -H "Content-Type: application/ld+json" -d @entities/room_101.json

# Create Room 201 (with Floor 2 relationship)
curl -X POST "http://localhost:1026/ngsi-ld/v1/entities/" \
  -H "Content-Type: application/ld+json" -d @entities/room_201.json

# Create subscriptions
curl -X POST "http://localhost:1026/ngsi-ld/v1/subscriptions/" \
  -H "Content-Type: application/ld+json" -d @subscriptions/subscription_room_101.json

curl -X POST "http://localhost:1026/ngsi-ld/v1/subscriptions/" \
  -H "Content-Type: application/ld+json" -d @subscriptions/subscription_room_201.json
```

#### Step 3: Launch Components

Execute each component in separate terminal sessions:

**Session 1: Listener for Room 101**
```bash
python listeners/listener_room_101.py
```

**Session 2: Listener for Room 201**
```bash
python listeners/listener_room_201.py
```

**Session 3: Producers for Floor 1**
```bash
python producers/producer_temp_101.py &
python producers/producer_motion_101.py &
```

**Session 4: Producers for Floor 2**
```bash
python producers/producer_temp_201.py &
python producers/producer_motion_201.py &
```

## Project Structure

```
ngsi-ld-smart-building-demo/
├── start.sh                          Automated startup script (macOS/Linux)
├── stop.sh                           Cleanup script (macOS/Linux)
├── provision.sh                      Entity and subscription provisioning script
├── docker-compose.yml                Container orchestration configuration
├── README.md                         This documentation
├── AI_PROJECT_GUIDE.md              Technical reference documentation
├── entities/                         NGSI-LD entity definitions
│   ├── building.json
│   ├── floor.json
│   ├── floor2.json
│   ├── room_101.json
│   ├── room_201.json
│   └── room_update.json
├── producers/                        Sensor data producer implementations
│   ├── producer_temp_101.py
│   ├── producer_motion_101.py
│   ├── producer_temp_201.py
│   └── producer_motion_201.py
├── subscriptions/                    Broker subscription configurations
│   ├── subscription_room_101.json
│   └── subscription_room_201.json
├── listeners/                        Notification listener implementations
│   ├── listener_room_101.py
│   └── listener_room_201.py
└── logs/                             Runtime execution logs
```

## Key Definitions

- **Entity:** Digital representation of a physical object or space
- **Attribute:** Property of an entity with associated value and metadata
- **Relationship:** Link between entities defining hierarchical or associative relationships
- **Subscription:** Rule defining conditions for automatic notifications when entity state changes
- **Context Broker:** Central repository and management system for all contextual data
- **Notification:** Message sent by the broker when subscription conditions are satisfied

## System Ports

| Port | Service | Purpose |
|------|---------|---------|
| 1026 | Orion-LD | Context Broker API (internal to Docker) |
| 3001 | Flask | Listener for Room 101 notifications |
| 3002 | Flask | Listener for Room 201 notifications |
| 27017 | MongoDB | Data persistence (internal to Docker) |

## Troubleshooting

**Issue:** Docker containers fail to initialize
- Verify Docker Desktop is running: `docker ps`
- Check Docker service status and restart if necessary

**Issue:** Connection refused errors from producers or listeners
- Allow 5-10 seconds after `./start.sh` for services to become available
- Verify Docker container health: `docker ps`

**Issue:** No data received by listeners
- Verify subscriptions exist: `curl -s http://localhost:1026/ngsi-ld/v1/subscriptions/ | python -m json.tool`
- Check listener service is running on correct port
- Review logs for error messages

**Issue:** Port already in use
- Macros/Linux: `pkill -f listener_room`
- Windows: `taskkill /F /IM python.exe`
- Alternatively, restart Docker service

**Issue:** `./start.sh` execution fails on Windows
- Use WSL2 or Git Bash environment
- Alternatively, follow Manual Setup section

## References

For detailed technical documentation, implementation details, and system architecture analysis, refer to `AI_PROJECT_GUIDE.md`.
