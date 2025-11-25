# NGSI-LD Proof-of-Concept: A Smart Building Scenario

This project serves as a practical demonstration of a real-time context management system built on the ETSI NGSI-LD standard. It simulates a smart building environment where data from multiple, independent sensors is aggregated and monitored through a centralized Context Broker.

The primary goal is to illustrate the core principles of NGSI-LD, including hierarchical data modeling, multi-source data publishing, and event-driven subscriptions.

## Architecture

The system is composed of three distinct layers, demonstrating a decoupled, event-driven architecture:

1.  **Context Broker (`FIWARE Orion-LD`):** Acts as the central nervous system. It maintains the digital twin of the building, including its structure and the real-time state of its rooms. It is powered by a MongoDB database for persistence.

2.  **Data Producers (`Python Scripts`):** These scripts simulate IoT devices that publish data to the Context Broker.
    *   `producer_temp.py`: Represents a thermostat, periodically sending `temperature` updates for a specific room.
    *   `producer_motion.py`: Represents a motion sensor, sending `occupancy` status updates for the same room.

3.  **Data Consumer (`Python/Flask`):**
    *   `listener.py`: A lightweight web service that acts as a notification endpoint. It subscribes to changes in the room's context and logs the received data, effectively acting as a monitoring dashboard.

### Architectural Diagram

The diagram below illustrates the flow of information between the components. The producers and the consumer are fully decoupled, communicating only through the Orion-LD Context Broker.

```
 (Producer 1: Thermostat)         (Producer 2: Motion Sensor)
 [ producer_temp.py ]              [ producer_motion.py ]
           |                                 |
           | 1. PATCH (temperature)          | 2. PATCH (occupancy)
           v                                 v
 +-------------------------------------------------------------+
 |                  ORION-LD CONTEXT BROKER                    |
 |                                                             |
 | +-----------------------+      +-------------------------+  |
 | | Digital Twin / Entity |      |      Subscription       |  |
 | | urn:ngsi-ld:Room:001  |----->| watches [temp, occup]   |  |
 | | { temp: 22.5,         |      |                         |
 | |   occupancy: 1 }      |      +-------------------------+  |
 | +-----------------------+             | 4. NOTIFY           |
 |                                       |                     |
 +-------------------------------------------------------------+
                                         |
                                         v
                               +-------------------------+
                               |  (Consumer: Monitor)    |
                               |  [ listener.py ]        |
                               |                         |
                               |  Receives notification  |
                               +-------------------------+
```

## Data Model

The context data is structured hierarchically using NGSI-LD's `Property` and `Relationship` attributes to create a linked data graph.

-   **Building:** The top-level entity (`urn:ngsi-ld:Building:MainHQ`).
-   **Floor:** A child entity linked to the building via a `refBuilding` relationship.
-   **Room:** A child entity linked to a floor via a `refFloor` relationship.

This model ensures that data is not siloed but is part of a larger, queryable context.

## Getting Started

Follow these steps to set up and run the entire simulation.

### Prerequisites

-   Docker & Docker Compose
-   Python 3.x
-   `requests` and `Flask` Python libraries (`pip install requests Flask`)

### 1. Launch the Infrastructure

Start the Orion-LD Context Broker and MongoDB database.

```bash
docker-compose up -d
```

### 2. Provision the Data Models

Before running the simulation, you must create the initial `Room` entity, establish the hierarchy, and set up the subscription. Execute the following commands in your terminal.

```bash
# 1. Create the initial Room entity
curl -X POST "http://localhost:1026/ngsi-ld/v1/entities/" -H "Content-Type: application/ld+json" -d "{\"id\":\"urn:ngsi-ld:Room:001\",\"type\":\"Room\",\"temperature\":{\"type\":\"Property\",\"value\":21.0},\"@context\":[\"https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld\"]}"

# 2. Create the Building and Floor entities
curl -X POST "http://localhost:1026/ngsi-ld/v1/entities/" -H "Content-Type: application/ld+json" -d "@building.json"
curl -X POST "http://localhost:1026/ngsi-ld/v1/entities/" -H "Content-Type: application/ld+json" -d "@floor.json"

# 3. Link the Room to the Floor and add the occupancy attribute
curl -X POST "http://localhost:1026/ngsi-ld/v1/entities/urn:ngsi-ld:Room:001/attrs" -H "Content-Type: application/ld+json" -d "@room_update.json"

# 4. Create the subscription to monitor the room
curl -X POST "http://localhost:1026/ngsi-ld/v1/subscriptions/" -H "Content-Type: application/ld+json" -d "@subscription.json"
```

### 3. Run the Simulation

Open three separate terminals and run the Python scripts.

**Terminal 1: Start the Listener**
```bash
python listener.py
```

**Terminal 2: Start the Temperature Producer**
```bash
python producer_temp.py
```

**Terminal 3: Start the Motion Producer**
```bash
python producer_motion.py
```

The listener terminal will now display real-time notifications as the producers update the room's context, demonstrating the complete end-to-end data flow.