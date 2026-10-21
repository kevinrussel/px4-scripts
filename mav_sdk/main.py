import asyncio
from mavsdk import System
import math
import json
import time
latest = {}
class BoxListener(asyncio.DatagramProtocol):

    def datagram_received(self, data, addr):
        latest.update(json.loads(data), t = time.time())
        return


async def wait_for_altitude(drone: System,target_relative_height: float):
    
    async for position in drone.telemetry.position():
        if (abs(position.absolute_altitude_m - target_relative_height) < 1.0):
            return

def estimate_distance(box_width_px):
    if box_width_px <= 0:
        return None

    return (FOCAL_LENGTH_PX * CUBE_WIDTH_M) / box_width_px
    



async def run():
    drone = System()
    await drone.connect(system_address="udp://:14540")
    print("Waiting for drone...")

    loop = asyncio.get_running_loop()
    await loop.create_datagram_endpoint(BoxListener, local_addr=("127.0.0.1", 6969))
    
    async for state in drone.core.connection_state():
        if state.is_connected:
            print("connected")
            break
    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            print("Position estimation okay")
            break
    async for home in drone.telemetry.home():
        home_lat = home.latitude_deg
        home_long = home.longitude_deg
        home_alt = home.absolute_altitude_m
        break
    await drone.action.arm()
    await drone.action.takeoff()
    await asyncio.sleep(5.0)
    alt_up = 2 + home_alt
    alt_down = 1 +  home_alt

    CYCLES = 6
    for i in range(CYCLES):
        await drone.action.goto_location(home_lat,home_long,alt_up,90)

        await wait_for_altitude(drone,alt_up)
        print(latest)
        await drone.action.goto_location(home_lat,home_long,alt_down,90)

        await wait_for_altitude(drone,alt_down)
    

    

    
    

asyncio.run(run())