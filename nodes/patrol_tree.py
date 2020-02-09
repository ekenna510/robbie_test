#!/usr/bin/env python

"""
    patrol_tree.py - Version 1.0 2013-03-18
    
    Navigate a series of waypoints while monitoring battery levels.
    Uses the pi_trees package to implement a behavior tree task manager.
    
    Created for the Pi Robot Project: http://www.pirobot.org
    Copyright (c) 2013 Patrick Goebel.  All rights reserved.

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.
    
    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details at:
    
    http://www.gnu.org/licenses/gpl.html
"""

import rospy
from std_msgs.msg import Float32
from geometry_msgs.msg import Twist
#from rbx2_msgs.srv import *
from pi_trees_ros.pi_trees_ros import *
from robbie_test.task_setup import *
from sensor_msgs.msg import BatteryState
#from phoenix_robot.clean_house_tasks_tree import *
from robbie_test.autodock import AutoDock


class BlackBoard():
    def __init__(self):
        self.battery_level = None
        self.charging = None

class Patrol():
    def __init__(self):
        rospy.init_node("patrol_tree")

        # Set the shutdown function (stop the robot)
        rospy.on_shutdown(self.shutdown)
        
        # Initialize a number of parameters and variables
        setup_task_environment(self)

        # Initialize the black board
        self.blackboard = BlackBoard()

        # Create a list to hold the move_base tasks
        MOVE_BASE_TASKS = list()
        
        n_waypoints = len(self.waypoints)
        
        # Create simple action navigation task for each waypoint
        for i in range(n_waypoints + 1):
            goal = MoveBaseGoal()
            goal.target_pose.header.frame_id = 'map'
            goal.target_pose.header.stamp = rospy.Time.now()
            goal.target_pose.pose = self.waypoints[i % n_waypoints]
            
            move_base_task = SimpleActionTask("MOVE_BASE_TASK_" + str(i), "move_base", MoveBaseAction, goal, result_timeout=40,
 reset_after=False)
            
            MOVE_BASE_TASKS.append(move_base_task)
        
        # Set the docking station pose
        goal = MoveBaseGoal()
        goal.target_pose.header.frame_id = 'map'
        goal.target_pose.header.stamp = rospy.Time.now()
        goal.target_pose.pose = self.docking_station_pose
        
        # Assign the docking station pose to a move_base action task
        NAV_DOCK_TASK = SimpleActionTask("NAV_DOC_TASK", "move_base", MoveBaseAction, goal, result_timeout=30,
reset_after=True)
        
        # Create the root node
        BEHAVE = Sequence("BEHAVE")
        
        # Create the "stay healthy" selector
        STAY_HEALTHY = Selector("STAY_HEALTHY")
        
        # Create the patrol loop decorator
        LOOP_PATROL = Loop("LOOP_PATROL", iterations=self.n_patrols)
        
        # Add the two subtrees to the root node in order of priority
        BEHAVE.add_child(STAY_HEALTHY)
        BEHAVE.add_child(LOOP_PATROL)
        
        # Create the patrol iterator
        PATROL = Iterator("PATROL")
        
        # Add the move_base tasks to the patrol task
        for task in MOVE_BASE_TASKS:
            PATROL.add_child(task)
  
        # Add the patrol to the loop decorator
        LOOP_PATROL.add_child(PATROL)
        
        # Add the battery check and recharge tasks to the "stay healthy" task
        with STAY_HEALTHY:
            # Monitor the fake battery level by subscribing to the /battery_level topic
            MONITOR_BATTERY = MonitorTask("MONITOR_BATTERY", "battery_state", BatteryState, self.monitor_battery)

            # The check battery condition (uses MonitorTask) battery_level
            CHECK_BATTERY = CallbackTask("BATTERY_OK?", self.check_battery)  

            # Set the fake battery level back to 100 using a ServiceTask
            #CHARGE_COMPLETE = ServiceTask("CHARGE_COMPLETE", "/set_battery_level", SetBatteryLevel, 11.5, result_cb=self.recharge_cb)

            # The charge robot task (uses ServiceTask)
            #CHARGE_ROBOT = ServiceTask("CHARGE_ROBOT", "battery_simulator/set_battery_level", SetBatteryLevel, 100, result_cb=self.recharge_cb)
            CHARGING = RechargeRobot("CHARGING", interval=3, blackboard=self.blackboard,topic="/setbatterylevel")
            
            RECHARGE = Sequence("RECHARGE", [NAV_DOCK_TASK, CHARGING], reset_after=True)
             
            # Build the recharge sequence using inline construction
            #RECHARGE = Sequence("RECHARGE", [NAV_DOCK_TASK, AUTODOCK])
                
            # Add the check battery and recharge tasks to the stay healthy selector
            STAY_HEALTHY.add_child(CHECK_BATTERY)
            STAY_HEALTHY.add_child(RECHARGE)
                
        # Display the tree before beginning execution
        print "Patrol Behavior Tree"
        print_tree(BEHAVE)
        
        # Run the tree
        while not rospy.is_shutdown():
            BEHAVE.run()
            rospy.sleep(0.1)

    def monitor_battery(self, msg):
        # Store the battery level as published on the fake battery level topic
        self.blackboard.battery_level = msg.voltage
        rospy.loginfo("monitor_battery - level: " + str(self.blackboard.battery_level))
    def check_battery(self):
        if self.blackboard.charging:
            return False
        if self.blackboard.battery_level is None:
            return None
        elif self.blackboard.battery_level < self.low_battery_threshold:
            rospy.loginfo("LOW BATTERY - level: " + str(self.blackboard.battery_level))
            return False
        else:
            return True

    def recharge_cb(self, result):
        rospy.loginfo("BATTERY CHARGED!")
            
    def shutdown(self):
        rospy.loginfo("Stopping the robot...")
        self.move_base.cancel_all_goals()
        self.cmd_vel_pub.publish(Twist())
        rospy.sleep(1)
        
class RechargeRobot(Task):
    def __init__(self, name, interval=3, blackboard=None,topic=None):
        super(RechargeRobot, self).__init__(name)
       
        self.name = name
        self.interval = interval
        self.blackboard = blackboard
        
        self.timer = 0
        self.topic = topic
        self.pub = rospy.Publisher(topic, Float32, queue_size=10)
        self.voltage = 12.4
        rospy.loginfo("recharge init")
         
    def run(self):
        if self.timer == 0:
            rospy.loginfo("CHARGING THE ROBOT!")
            self.pub.publish(self.voltage)            
        if self.timer < self.interval:
            self.blackboard.charging = True
            self.timer += .5
            rospy.sleep(0.1)
            return TaskStatus.RUNNING
        else:
            rospy.loginfo("CHARGED")
            return TaskStatus.SUCCESS
    
    def reset(self):
        self.status = None
        self.timer = 0


if __name__ == '__main__':
    tree = Patrol()

