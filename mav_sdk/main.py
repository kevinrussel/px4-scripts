import asyncio
from mavsdk import System

async def run():
    drone = System()
    await drone.connect(system_address="udp://:14540")
    print("Waiting for drone...")
    await drone.action.arm()
    await drone.action.takeoff()
    

asyncio.run(run())