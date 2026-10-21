#!/usr/bin/env python3
from gz.transport13 import Node
from gz.msgs10.entity_factory_pb2 import EntityFactory
from gz.msgs10.entity_pb2 import Entity

from gz.msgs10.boolean_pb2 import Boolean
from gz.msgs10.pose_v_pb2 import Pose_V
import time
import json
import math
import random
class box:


    def random_z_value(self):
        return random.randint(20,50)
    def random_x_value(self):
        return random.randint(20,50)

    def delete_box(self):
        node = Node()
        req = Entity()
        req.name = "target_box"
        req.type = 2

        response = node.request(
            "/world/default/remove",
            req,
            Entity,
            Boolean,
            timeout=1000
        )
        
        return response

    def callback_function(self,message):
        for pose in message.pose:
            if pose.name == self.drone_name:
                distance = math.dist((self.x, self.y, self.z), (pose.position.x, pose.position.y, pose.position.z))
                print(f"The distance is {distance}")
                if distance <= 1.0:
                    response = self.delete_box()
                    if response:
                        self.deleted_box = True
                        random_x = self.random_x_value()
                        self.x = random_x
                        # random_z = self.random_z_value()
                        # self.z = random_z 
                break
        if(self.deleted_box):
            self.spawn_box(self.x,self.y,self.z,self.w)
            self.deleted_box = False
        

        
    def spawn_box(self,x_position,y_position,z_position,w_position):
        service = self.create_service
        self.req.sdf_filename = self.sdf_filename
        self.req.name = self.entity_name
        self.req.pose.position.x = x_position
        self.req.pose.position.y = y_position
        self.req.pose.position.z = z_position
        self.req.pose.orientation.w = w_position
        

        return self.node.request(service, self.req, EntityFactory, Boolean, timeout=1000)
    def __init__(self):
        self.node = Node()
        self.req = EntityFactory()
        with open('box_config.json') as file:
             config_file= json.load(file)
        self.x = config_file["x_position"] 
        self.y = config_file["y_position"] 
        self.z = config_file["z_position"] 
        self.w = config_file["w_position"] 
        self.create_service = "/world/default/create"
        self.sdf_filename = config_file["sdf_filename"]
        self.sdf_filename = config_file["sdf_filename"]
        self.entity_name = config_file["name"] 
        self.deleted_box = False

        response = self.spawn_box(self.x,self.y,self.z,self.w)
        
        self.drone_name = config_file["DRONE_NAME"]
        if response:
            print("Spawned successfully")
        else:
            print("Spawn failed")

        topic_name = "/world/default/dynamic_pose/info"

        self.node.subscribe(Pose_V, topic_name, self.callback_function)

        try:
            while True:
                time.sleep(0.001)
        except KeyboardInterrupt:
            pass   


spawn_box = box()