import argparse
import asyncio
from mavsdk import System


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--pipe", default="./comms.pipe")
    parser.add_argument("-s", "--system", default="udp://:14540")
    args = parser.parse_args()
    drone = System()
    print("Waiting for drone to connect...")
    await drone.connect(system_address=args.system)
    print("Drone connected.")
    while True:
        with open(args.pipe, 'r') as f:
            command = f.read()
        if command == "l":
            print("Landing")
            await drone.action.land()
        elif command == "h":
            print("Loitering")
            await drone.action.hold()
        elif command == "r":
            print("RTL")
            await drone.action.return_to_launch()
        elif len(command) > 0:
            print("Invalid command")

if __name__ == "__main__":
    asyncio.run(main())
