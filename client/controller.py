import os
import json
import errno
import fcntl
import asyncio
import argparse
from utils import makepipe
from mavsdk import System


async def read_pipe(pipe_path: str, command_queue: asyncio.Queue):
    while True:
        fd = os.open(pipe_path, os.O_RDONLY | os.O_NONBLOCK)
        if fd < 0:
            raise FileNotFoundError(pipe_path)
        try:
            data = os.read(fd, 1)
        except BlockingIOError:
            fcntl.fcntl(fd, fcntl.F_SETFL, fcntl.fcntl(
                fd, fcntl.F_GETFL) ^ os.O_NONBLOCK)
            data = os.read(fd, 1)
            await command_queue.put(data.decode().strip())
        except Exception as e:
            print(e)
        finally:
            os.close(fd)
            await asyncio.sleep(0.1)


async def pub_telemetry(pipe_path: str, telemetry_queue: asyncio.Queue):
    while True:
        msg = await telemetry_queue.get()
        msg = json.dumps(msg)
        fd = None
        try:
            fd = os.open(pipe_path, os.O_WRONLY | os.O_NONBLOCK)
            os.write(fd, msg.encode())
            os.write(fd, "\n".encode())
        except Exception as e:
            if e.args[0] == errno.ENXIO:
                await asyncio.sleep(0.5)
                continue
            print(e)
        finally:
            if fd:
                os.close(fd)


async def monitor_position(drone: System, queue: asyncio.Queue):
    """Monitor drone telemetry and print position updates."""
    async for position in drone.telemetry.position():
        await queue.put({
            "type": "position",
            "data": {
                "latitude_deg": f"{position.latitude_deg:.6f}",
                "longitude_deg": f"{position.longitude_deg:.6f}",
                "relative_altitude_m": f"{position.relative_altitude_m:.6f}",
            }
        })


async def monitor_battery(drone: System, queue: asyncio.Queue):
    """Monitor drone battery status."""
    async for battery in drone.telemetry.battery():
        await queue.put({
            "type": "battery",
            "data": {
                "id": battery.id,
                "remaining_percent": battery.remaining_percent,
            }
        })


async def monitor_mode(drone: System, queue: asyncio.Queue):
    """Monitor drone current flight mode."""

    async for mode in drone.telemetry.flight_mode():
        await queue.put({
            "type": "flight_mode",
            "data": {
                "mode": str(mode)
            }
        })


async def process_commands(drone: System, command_queue: asyncio.Queue):
    """Process commands from the queue and apply them to the drone."""
    while True:
        command = await command_queue.get()

        if command == "l":
            print("Landing")
            await drone.action.land()
        elif command == "h":
            print("Hold/Loiter")
            await drone.action.hold()
        elif command == "r":
            print("Return to Launch")
            await drone.action.return_to_launch()
        else:
            print(f"Unknown command: {command}")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--command_pipe", default="./comms.pipe")
    parser.add_argument("-t", "--telemetry_pipe", default="./tele.pipe")
    parser.add_argument("-s", "--system", default="udp://:14540")
    args = parser.parse_args()

    makepipe(args.telemetry_pipe)
    command_queue = asyncio.Queue()
    telemetry_queue = asyncio.Queue()

    drone = System()
    print("Waiting for drone to connect...")
    await drone.connect(system_address=args.system)

    async for state in drone.core.connection_state():
        if state.is_connected:
            print("Drone connected!")
            break

    # Create concurrent tasks
    tasks = [
        asyncio.create_task(read_pipe(args.command_pipe, command_queue)),
        asyncio.create_task(monitor_position(drone, telemetry_queue)),
        asyncio.create_task(monitor_battery(drone, telemetry_queue)),
        asyncio.create_task(monitor_mode(drone, telemetry_queue)),
        asyncio.create_task(process_commands(drone, command_queue)),
        asyncio.create_task(pub_telemetry(
            args.telemetry_pipe, telemetry_queue)),
    ]

    try:
        # Run all tasks concurrently
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        print("\nShutting down...")
        # Cancel all tasks
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
