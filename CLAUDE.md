# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Cherum is a backup emergency control system for drones with a client-server architecture:
- **Server**: Flask web app that stores commands, tracks connections, and manages telemetry data
- **Client**: Python scripts that poll the server for commands and control the drone via MAVLink

## Common Commands

### Server Development

```bash
# Install dependencies
cd server
pip install -e .

# Initialize database
flask db:create

# Generate JWT token for client authentication
flask jwt:create

# Run development server
flask run --debug

# Run production server (with Waitress)
waitress-serve --host=0.0.0.0 --port=80 cherum:create_app
```

### Client Development

```bash
# Install dependencies
cd client
pip install -r requirements.txt

# Run client components individually
export TOKEN="your-jwt-token-here"
python poller.py &
python controller.py &
python telemetry.py

# OR use the start script (with tmux)
./start.sh /dev/ttyUSB0 http://server-url
```

### Docker Deployment

```bash
# Build and run server container
cd server
docker build -t cherum-server .
docker run -p 80:80 cherum-server

# OR use docker-compose for full stack
docker-compose up
```

## Architecture

### Server Components

- **Flask App** (`/server/cherum/__init__.py`): Main application with endpoints:
  - `/` - Web interface with control buttons and telemetry display
  - `/command` - Receives commands from UI
  - `/fetch` - API endpoint for clients (JWT protected)
  - `/done/<id>` - Marks commands complete (JWT protected)
  - `/last/connection` - Returns last client connection time
  - `/telemetry` - Stores/retrieves drone telemetry data
  - `/last/telemetry` - Gets latest telemetry data
  - `/health` - Health check endpoint

- **Database**:
  - **SQLite** (`schema.sql`): 
    - `commands` table: Stores drone commands with status
    - `pings` table: Tracks client connections
  - **InfluxDB**: Time-series telemetry data storage

- **JWT Auth** (`jwt.py`): Handles token creation and validation

- **Web Interface** (`templates/index.html`, `static/`):
  - Emergency control buttons (Land, Loiter/Hold, Return to Launch)
  - Real-time telemetry display (altitude, battery, GPS, etc.)
  - Live map with drone position (Leaflet)
  - WebRTC video stream with YOLOv8 object detection
  - Connection status monitoring

### Client Components

- **Poller** (`poller.py`): 
  - Polls server every 0.5 seconds
  - Writes command abbreviations to named pipe: `l` (land), `h` (hold/loiter), `r` (return to launch)
  
- **Controller** (`controller.py`):
  - Reads commands from named pipe
  - Executes drone commands via MAVSDK
  - Default drone connection: UDP port 14540

- **Telemetry** (`telemetry.py`):
  - Sends drone telemetry data to server
  - Updates battery, position, altitude, and status information

- **Start Script** (`start.sh`):
  - Uses tmux to manage all client processes
  - Configures serial device and server URL

### Communication Flow

1. User clicks command button in web UI
2. Server stores command in database
3. Client poller fetches command via authenticated API
4. Poller writes abbreviated command to named pipe
5. Controller reads pipe and sends MAVLink command to drone
6. Poller marks command as done on server
7. Telemetry script continuously sends drone data to server

## Key Development Notes

- Client requires `TOKEN` environment variable with valid JWT
- Named pipe `comms.pipe` must exist for client communication
- Server uses Central Mexico timezone (UTC-6) for display
- Connection timeout threshold is 10 seconds
- Only the latest unprocessed command is fetched by clients
- WebRTC stream expects video at `ws://localhost:8002/ws`
- Object detection expects YOLO server at `ws://localhost:8001/ws`