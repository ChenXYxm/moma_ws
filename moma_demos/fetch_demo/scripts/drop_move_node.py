#!/usr/bin/env python

import actionlib
from fetch_demo.msg import DropMoveAction, DropMoveResult
import rospy
from grasp_demo.utils import create_robot_connection
from fetch_demo.common import MovingActionServer
from actionlib_msgs.msg import GoalStatus


class DropActionServer(MovingActionServer):
    """
        When called, this action should navigate the base and arm to a pre-specified position,
        then open the gripper to drop the grasped object. 
    """

    def __init__(self):
        action_name = "drop_move_action"
        self.action_server = actionlib.SimpleActionServer(
            action_name, DropMoveAction, execute_cb=self.drop_cb, auto_start=False
        )

        self._read_joint_configurations()
        self._connect_yumi()
        self._read_waypoints()

        self.action_server.start()
        rospy.loginfo("Drop move action server started.")

    def _read_waypoints(self):
        waypoints = rospy.get_param("drop_waypoints")
        self._retract_waypoint = waypoints["retract_waypoint"]
        self._drop_waypoints = waypoints["drop_waypoints"]

    def _read_joint_configurations(self):
        self._search_joints_r = rospy.get_param("search_joiloopnts_r")
        self._ready_joints_l = rospy.get_param("ready_joints_l")
        self._home_joints_l = rospy.get_param("home_joints_l")

    def _connect_yumi(self):
        self._left_arm = create_robot_connection("yumi_left_arm")
        self._right_arm = create_robot_connection("yumi_right_arm")

    def drop_cb(self, msg):
        rospy.loginfo("Start approaching object")
        result = DropMoveResult()

        state = self._visit_waypoint(self._retract_waypoint)
        if state == GoalStatus.PREEMPTED:
            rospy.loginfo("Got preemption request")
            self.action_server.set_preempted()
            return
        elif state == GoalStatus.ABORTED:
            rospy.logerr(
                "Failed to navigate to approach waypoint " + self._retract_waypoint
            )
            self.action_server.set_aborted()
            return

        self._left_arm.goto_joint_target(self._home_joints_l, max_velocity_scaling=0.5)
        self._right_arm.goto_joint_target(
            self._search_joints_r, max_velocity_scaling=0.5
        )

        for waypoint in self._drop_waypoints:
            state = self._visit_waypoint(waypoint)
            if state == GoalStatus.PREEMPTED:
                rospy.loginfo("Got preemption request")
                self.action_server.set_preempted()
                return
            elif state == GoalStatus.ABORTED:
                rospy.logerr("Failed to navigate to approach waypoint " + waypoint)
                self.action_server.set_aborted()
                return

        self._left_arm.goto_joint_target(self._ready_joints_l, max_velocity_scaling=0.5)
        self._left_arm.release()

        rospy.loginfo("Finished dropping")
        self.action_server.set_succeeded(result)


def main():
    rospy.init_node("drop_move_action_node")
    DropActionServer()
    rospy.spin()


if __name__ == "__main__":
    main()
