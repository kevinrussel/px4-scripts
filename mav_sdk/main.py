import asyncio
from mavsdk import System
import math
import json
import time
latest = {}

## This is all to calculate the distance using the camera
IMAGE_WIDTH = 1280
HORIZONTAL_FOV = 1.74  # radians
CUBE_WIDTH_M = 1.0
FOCAL_LENGTH_PX = IMAGE_WIDTH / (
    2 * math.tan(HORIZONTAL_FOV / 2)
)

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


def process_detection(data):
    if not data["visible"]:
        return None

    width = data["image_width"]
    height = data["image_height"]

    center_x = data["center_x"]
    center_y = data["center_y"]
    box_width = data["box_width"]

    error_x = center_x - width / 2
    error_y = center_y - height / 2

    distance = estimate_distance(box_width)

    return {
        "error_x": error_x,
        "error_y": error_y,
        "distance_m": distance,
    }



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
    alt_up = home_alt

    counter = 1
    while True:
        alt_up = alt_up + 1
        await drone.action.goto_location(home_lat,home_long,alt_up, 90)
        await wait_for_altitude(drone,alt_up)
        ans = process_detection(latest)
        if(ans is not None):
            print(f"It is visible {ans}")
            if(counter % 20 == 0):
                print(f"Holding: {ans}")
                break
            print(f"Seen image {ans}")
    await drone.action.hold()
        
    

    

    
    

asyncio.run(run())