import asyncio
from mavsdk import System
import math
import json
import time
latest = {}
from mavsdk.offboard import VelocityBodyYawspeed
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
        if (abs(position.absolute_altitude_m - target_relative_height) < 0.3):
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
    await drone.action.goto_location(home_lat,home_long,20,90)
    await wait_for_altitude(drone,20)
    counter = 1
    second_counter = 0

    await drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
    try:
        await drone.offboard.start()
        print("-- Offboard started")
    except Exception as e:
        print(f"Failed to start offboard: {e}")
        return
    while True: 
        if(counter % 50 == 0):
            break
        ans = process_detection(latest)
        if(ans not None):
    
        print(f"It is visible {ans}")
        counter +=1
        await asyncio.sleep(0.25)

        if(ans["error_y"] > -100 and ans["error_y"] < 100):
            second_counter +=1
            if(second_counter % 5 == 0):
                while True:
                    await drone.offboard.set_velocity_body(VelocityBodyYawspeed(1.0, 0.0, 0.0, 0.0))
                    print("Moving forward for 5s")
                    await asyncio.sleep(5)
                    await drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))

    await drone.action.hold()
    print("About to sleep")
    await asyncio.sleep(10.0)
        
    

    

    
    

asyncio.run(run())