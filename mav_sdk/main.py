import asyncio
from mavsdk import System
import math
async def wait_for_altitude(drone: System,target_relative_height: float):
    
    async for position in drone.telemetry.position():
        if (abs(position.absolute_altitude_m - target_relative_height) < 1.0):
            return
    


async def run():
    drone = System()
    await drone.connect(system_address="udp://:14540")
    print("Waiting for drone...")

    async for home in drone.telemetry.home():
        home_lat = home.latitude_deg
        home_long = home.longitude_deg
        home.alt = home.absolute_altitude_m
    await drone.action.arm()
    await drone.action.takeoff()
    await asyncio.sleep(5.0)

    alt_up = 30 + home.alt
    CYCLES = 6
    for i in range(CYCLES):
        await drone.action.goto_location(home_lat,home_long,alt_up)

        await

    

    
    

asyncio.run(run())