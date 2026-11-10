import asyncio
from mavsdk import System
import math
import json
import time
latest = {}
from mavsdk.offboard import VelocityBodyYawspeed
import numpy as np
## This is all to calculate the distance using the camera
IMAGE_WIDTH = 1280
HORIZONTAL_FOV = 1.74  # radians
CUBE_WIDTH_M = 1.0
FOCAL_LENGTH_PX = IMAGE_WIDTH / (
    2 * math.tan(HORIZONTAL_FOV / 2)
)

class VisualTracker:


    def __init__(self,width=1280, height=720):
        self.width = width
        self.height = height

        # Speeds that the drone moves at.
        self.k_p_yaw = 25.0
        self.k_p_alt = 0.8
        self.k_p_fwd = 2.0

        ## 8% tolerance to be within the center
        self.tol_x = 0.15
        self.tol_y = 0.15

        self.lock_enter_tol = 0.08
        self.lock_exit_tol = 0.15
        self.is_locked = False

        self.filtered_err_x = 0.0
        self.filtered_err_y = 0.0
        self.alpha = 0.35

        
    def compute_control(self,detection_data):

        if not detection_data:
            self.is_locked = False
            return 0.0,0.0,0.0,15.0, False

        # Normalize the erros for a -1 to 1 range.
        norm_err_x = detection_data["error_x"] / (self.width/2.0)
        norm_err_y = detection_data["error_y"] / (self.height / 2.0)


        self.filtered_err_x = (self.alpha * norm_err_x + (1.0 - self.alpha) * self.filtered_err_x)
        self.filtered_err_y = (self.alpha * norm_err_y + (1.0 - self.alpha) * self.filtered_err_y)

        ex= self.filtered_err_x
        ey = self.filtered_err_y
        if not self.is_locked:
            if abs(ex) < self.lock_exit_tol and abs(ey) < self.lock_enter_tol:
                self.is_locked = True
            else:
                if abs(ex) > self.lock_exit_tol:
                    self.is_locked = False


        is_aligned = ( abs(norm_err_x) < self.tol_x and abs(norm_err_y) < self.tol_y)

        # is_contact = dist is not None and (dist <= self.target_dist_m)
        

        # Centering
        yaw_rate = self.k_p_yaw * norm_err_x
        vel_down = self.k_p_alt * norm_err_y

        ## clamp limits
        yaw_rate = float(np.clip(yaw_rate, -30.0,30.0))
        vel_down = float(np.clip(vel_down, -1.0, 1.0))
        vel_forward = 2.0
        if not self.is_locked:
            vel_forward = 0.0


        return vel_forward, 0.0, vel_down, yaw_rate, is_aligned


        



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
    tracker = VisualTracker(width=1280,height=720)
    while True: 
        ans = process_detection(latest)
        vx, vy, vz, yawspeed, aligned = tracker.compute_control(ans)
        if ans is not None:
            # if contact:
            #     print("[SUCCESS] Reached target! Despawning/holding.")
            #     await drone.offboard.set_velocity_body(
            #         VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0)
            #     )
            #     break

            if not aligned:
                print(f"[CENTERING] err_x={ans.get('error_x', 0):.1f}, yaw={yawspeed:.1f}")
            else:
                print(f"[PURSUING] Aligned! Approaching at vx={vx:.1f} m/s")

            # Send setpoint to PX4
            await drone.offboard.set_velocity_body(
                VelocityBodyYawspeed(vx, vy, vz, yawspeed)
            )

            await asyncio.sleep(0.10)  # 10 Hz tick rate
        else:
            await drone.offboard.set_velocity_body(VelocityBodyYawspeed(vx,vy,vz,yawspeed))
            await asyncio.sleep(0.1)
        
    await drone.action.hold()
    print("About to sleep")
    await asyncio.sleep(10.0)
        
    

    

    
    

asyncio.run(run())