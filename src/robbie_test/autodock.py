#!/usr/bin/env pyth
import rospy
from pi_trees_ros.pi_trees_ros import *

# do nothing
class AutoDock(Task):
  def __init__(self,name):
    Task.__init__(self,name)
    rospy.loginfo("autodock")
  def run(self):
    pass

