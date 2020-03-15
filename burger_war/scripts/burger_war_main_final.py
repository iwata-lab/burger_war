#!/usr/bin/env python
# -*- coding: utf-8 -*-
import rospy
import random
import tf
import json
import math
import actionlib
import actionlib_msgs
import smach
import smach_ros
import roslib.packages
from geometry_msgs.msg    import Twist
from std_msgs.msg         import Float32

rospy.init_node("burger_war_main_node")#smath_filesでtfを使用するため,init_nodeする前にtf_listerner()があるとエラー
from smach_files          import *

# Global変数
target_location_global = ""


class Setup(smach.State):

    def __init__(self):
        smach.State.__init__(self, outcomes=["finish"])

    def execute(self, userdata):

        overlaytext.publish("Setup now ...")
        rospy.sleep(1)

        if rospy.get_param("/send_id_to_judge/side") == "r":
            move_base.pub_initialpose_for_burger_war()
        else:
            move_base.pub_initialpose_for_burger_war()
        
        rospy.sleep(1)
        return "finish"


class Commander(smach.State):

    def __init__(self):
        smach.State.__init__(self, outcomes=["move", "fight", "commander", "game_finish"])

        self.is_enemy_close = False
        self.notice_length  = 0.8

    def execute(self, userdata):
        global target_location_global

        self.is_enemy_close = True if tf_util.get_the_length_to_enemy() < self.notice_length else False

        #各状況に合わせて状態遷移
        if self.is_enemy_close == True:
            return "fight"
        else:
            target_location_global = maker.get_next_location_name()
            if target_location_global == "":
                rospy.sleep(1)
                return "commander"
            else:
                return "move"

class Move(smach.State):

    def __init__(self):
        smach.State.__init__(self, outcomes=["finish"])
        self.notice_length = 0.8

    def execute(self, userdata):
        global target_location_global

        goal = json_util.generate_movebasegoal_from_locationname(target_location_global)
        overlaytext.publish("Move to " + target_location_global)

        #移動開始
        move_base.send_goal(goal)        
        start_moving_time = rospy.Time.now()
        
        while start_moving_time + rospy.Duration(25) > rospy.Time.now():
            rospy.sleep(0.5)

            if (tf_util.get_the_length_to_enemy() < self.notice_length) or (maker.get_next_location_name() != target_location_global):#敵が近づいてきた場合or目標地点が変化した場合
                move_base.cancel_goal()
                break
            elif maker.is_maker_mine(target_location_global) == True:
                move_base.cancel_goal()
                overlaytext.publish("Get the maker[" + target_location_global + "].")
                rospy.sleep(1.0)
                break
            elif move_base.get_current_status() == "SUCCEEDED":#到着したがマーカーを取れていない
                twist.publish_back_twist()
                break
            elif move_base.get_current_status() != "SUCCEEDED" and move_base.get_current_status() != "ACTIVE":#slam失敗した場合
                twist.publish_back_twist()
                break

        return "finish"


class Fight(smach.State):#敵が付近に存在する場合は、敵のマーカーをトラッキング

    def __init__(self):
        smach.State.__init__(self, outcomes=["finish"])
        self.angular_weight = 1.50
        self.notice_length  = 0.80

    def execute(self, userdata):

        start_fight_time = rospy.Time.now()
        while True:
            move_base.cancel_goal()
            overlaytext.publish("STATE: Fight\nlength = " + str(tf_util.get_the_length_to_enemy())[:6])
            if tf_util.get_the_length_to_enemy() > self.notice_length:
                break
            elif start_fight_time + rospy.Duration(5) < rospy.Time.now():#10sでタイムアウト
                twist.publish_back_twist()
                break

            # Twistのpublish
            target_angular = tf_util.get_the_radian_to_enemy() * self.angular_weight
            twist.publish_rotate_twist(target_angular)

        return "finish"


if __name__ == "__main__":

    rospy.init_node("burger_war_main_node")
    rospy.loginfo("Start burger war main program.")

    sm = smach.StateMachine(outcomes=["Game_finish"])
    with sm:
        smach.StateMachine.add("Setup",     Setup(),     transitions={"finish": "Commander"})
        smach.StateMachine.add("Commander", Commander(), transitions={"move": "Move", "fight": "Fight", "commander": "Commander", "game_finish": "Game_finish"})
        smach.StateMachine.add("Move",      Move(),      transitions={"finish": "Commander"})
        smach.StateMachine.add("Fight",     Fight(),     transitions={"finish": "Commander"})

    sis = smach_ros.IntrospectionServer("server", sm, "/BURGER_WAR_TASK")
    sis.start()
    sm.execute()
    sis.stop()
