# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Cherum is a backup emergency control system for drones with a client-server architecture:
- **Server**: Flask web app that stores commands and tracks drone connections
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
pip install mavsdk requests

# Run client (requires TOKEN environment variable)
export TOKEN="your-jwt-token-here"
python poller.py &
python controller.py
```

### Docker Deployment

```bash
# Build and run server container
cd server
docker build -t cherum-server .
docker run -p 80:80 cherum-server
```

## Architecture

### Server Components

- **Flask App** (`/server/cherum/__init__.py`): Main application with endpoints:
  - `/` - Web interface
  - `/command` - Receives commands from UI
  - `/fetch` - API endpoint for clients (JWT protected)
  - `/done/<id>` - Marks commands complete (JWT protected)
  - `/last/connection` - Returns last client connection time
  - `/health` - Health check

- **Database** (`schema.sql`):
  - `commands` table: Stores drone commands with status
  - `pings` table: Tracks client connections

- **JWT Auth** (`jwt.py`): Handles token creation and validation

### Client Components

- **Poller** (`poller.py`): 
  - Polls server every 0.5 seconds
  - Writes command abbreviations to named pipe: `l` (land), `h` (hold/loiter), `r` (return to launch)
  
- **Controller** (`controller.py`):
  - Reads commands from named pipe
  - Executes drone commands via MAVSDK
  - Default drone connection: UDP port 14540

### Communication Flow

1. User clicks command button in web UI
2. Server stores command in database
3. Client poller fetches command via authenticated API
4. Poller writes abbreviated command to named pipe
5. Controller reads pipe and sends MAVLink command to drone
6. Poller marks command as done on server

## Key Development Notes

- Client requires `TOKEN` environment variable with valid JWT
- Named pipe `comms.pipe` must exist for client communication
- Server uses Central Mexico timezone (UTC-6) for display
- Connection timeout threshold is 10 seconds
- Only the latest unprocessed command is fetched by clients