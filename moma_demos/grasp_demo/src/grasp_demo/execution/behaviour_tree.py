import py_trees
import py_trees_ros

from grasp_demo.msg import (
    ScanSceneAction,
    ScanSceneGoal,
    GraspAction,
    GraspGoal,
    DropGoal,
    DropAction,
)
from action_client import ActionClient_ResultSaver, ActionClient_BBgoal

import std_msgs


def generate_grasp_goal_msg(target_grasp):
    goal = GraspGoal()
    goal.target_grasp_pose = target_grasp.selected_grasp_pose
    return goal


def get_bt_scan_grasp_drop(subtree=None):
    # Action: scan
    action_scan_goal = ScanSceneGoal()
    action_scan = ActionClient_ResultSaver(
        name="action_scan",
        action_spec=ScanSceneAction,
        action_goal=action_scan_goal,
        action_namespace="pointcloud_scan_action",
        set_flag_instead_result=False,
    )

    check_grasp_computed = py_trees.blackboard.CheckBlackboardVariable(
        name="Grasp computed?",
        variable_name="action_scan_result",
        clearing_policy=py_trees.common.ClearingPolicy.NEVER,
    )

    button_next = py_trees_ros.subscribers.WaitForData(
        name="Button next?",
        topic_name="/manipulation_actions/next",
        topic_type=std_msgs.msg.Empty,
    )

    root_scan = py_trees.composites.Selector(
        children=[
            check_grasp_computed,
            py_trees.composites.Sequence(
                children=[button_next, action_scan]
                if subtree is None
                else [subtree, button_next, action_scan]
            ),
        ]
    )

    # Action: grasp
    action_grasp = ActionClient_BBgoal(
        name="action_grasp",
        action_spec=GraspAction,
        action_namespace="grasp_action",
        goal_gen_callback=generate_grasp_goal_msg,
        bb_goal_var_name="action_scan_result",
        set_flag_instead_result=True,
    )

    check_object_in_hand = py_trees.blackboard.CheckBlackboardVariable(
        name="Object in hand?",
        variable_name="action_grasp_result",
        expected_value=True,
        clearing_policy=py_trees.common.ClearingPolicy.ON_INITIALISE,
    )

    button_next = py_trees_ros.subscribers.WaitForData(
        name="Button next?",
        topic_name="/manipulation_actions/next",
        topic_type=std_msgs.msg.Empty,
    )

    root_grasp = py_trees.composites.Selector(
        children=[
            check_object_in_hand,
            py_trees.composites.Sequence(
                children=[root_scan, button_next, action_grasp]
            ),
        ]
    )

    # Action: drop
    action_drop_goal = DropGoal()
    action_drop = ActionClient_ResultSaver(
        name="action_drop",
        action_spec=DropAction,
        action_goal=action_drop_goal,
        action_namespace="drop_action",
        set_flag_instead_result=True,
    )

    check_object_at_target = py_trees.blackboard.CheckBlackboardVariable(
        name="Object at target?",
        variable_name="action_drop_result",
        expected_value=True,
        clearing_policy=py_trees.common.ClearingPolicy.ON_INITIALISE,
    )

    button_next = py_trees_ros.subscribers.WaitForData(
        name="Button next?",
        topic_name="/manipulation_actions/next",
        topic_type=std_msgs.msg.Empty,
    )

    root_drop = py_trees.composites.Selector(
        children=[
            check_object_at_target,
            py_trees.composites.Sequence(
                children=[root_grasp, button_next, action_drop]
            ),
        ]
    )

    return root_drop


def get_root():
    # For a sketch of the tree layout, see here (slide 2): https://docs.google.com/presentation/d/1swC5c1mbVn2TRDar-y0meTbrC9BUHnT9XWYPeFJlNxM/edit#slide=id.g70bc070381_0_32

    # -------- Add reset button -----------------------------------------

    reset_root = py_trees.composites.Sequence()
    button_reset = py_trees_ros.subscribers.WaitForData(
        name="Button reset?",
        topic_name="/manipulation_actions/reset",
        topic_type=std_msgs.msg.Empty,
    )
    var_reset = py_trees.blackboard.SetBlackboardVariable(
        variable_name="do_reset", variable_value=True
    )
    reset_root.add_children([button_reset, var_reset])

    reset_exec_root = py_trees.composites.Sequence()
    check_var_reset = py_trees.blackboard.CheckBlackboardVariable(
        name="Check reset var", variable_name="do_reset", expected_value=True
    )
    clear_var_reset = py_trees.blackboard.ClearBlackboardVariable(
        variable_name="do_reset"
    )
    reset_action1 = py_trees.blackboard.ClearBlackboardVariable(
        name="Clear grasp pose", variable_name="target_grasp_pose"
    )
    reset_action2 = py_trees.blackboard.SetBlackboardVariable(
        name="Set object not in hand",
        variable_name="object_in_hand",
        variable_value=False,
    )
    reset_exec_root.add_children(
        [check_var_reset, clear_var_reset, reset_action1, reset_action2]
    )

    # -------- Add nodes writing to blackboard -----------------------------------------

    bb_root = py_trees.composites.Sequence()

    # grasp2bb = py_trees_ros.subscribers.ToBlackboard(name="grasp2bb",
    #                                                  topic_name="/panda_demo/grasp_pose",
    #                                                  topic_type=std_msgs.msg.String,
    #                                                  blackboard_variables="grasp_pose",
    #                                                  initialise_variables=None
    #                                                 )
    # bb_root.add_child(grasp2bb)

    # -------- Add nodes with condition checks and actions -----------------------------

    action_root = py_trees.composites.Selector()

    action_root.add_child(reset_exec_root)

    check_obj_in_ws = py_trees.behaviours.Success(name="Object in workspace?")
    action_root.add_child(py_trees.decorators.Inverter(check_obj_in_ws))

    # check_obj_in_hand = py_trees.behaviours.Failure(name="Object in hand?")
    check_obj_in_hand = py_trees.blackboard.CheckBlackboardVariable(
        name="Object in hand?", variable_name="object_in_hand", expected_value=True
    )

    # check_grasp_pose_known = py_trees.behaviours.Failure(name="Grasp pose known?")
    check_grasp_pose_known = py_trees.blackboard.CheckBlackboardVariable(
        name="Grasp pose known?", variable_name="target_grasp_pose"
    )

    # Action: compute grasp
    button_compute_grasp = py_trees_ros.subscribers.WaitForData(
        name="Button compute grasp?",
        topic_name="/manipulation_actions/scan",
        topic_type=std_msgs.msg.Empty,
    )
    scan_goal = ScanSceneGoal()
    scan_goal.num_scan_poses = 5
    action_get_grasp = ActionClient_ResultSaver(
        name="Action compute grasp",
        action_spec=ScanSceneAction,
        action_goal=scan_goal,
        action_namespace="pointcloud_scan_action",
        bb_var_name="target_grasp_pose",
    )
    composite_exec_get_grasp = py_trees.composites.Sequence(
        children=[button_compute_grasp, action_get_grasp]
    )

    composite_compute_grasp = py_trees.composites.Selector(
        children=[check_grasp_pose_known, composite_exec_get_grasp]
    )

    # Action: execute grasp
    button_do_grasp = py_trees_ros.subscribers.WaitForData(
        name="Button do grasp?",
        topic_name="/manipulation_actions/grasp",
        topic_type=std_msgs.msg.Empty,
    )
    action_grasp = py_trees.behaviours.Running(name="Action do grasp")
    action_grasp = ActionClient_BBgoal(
        name="Action do grasp",
        action_spec=GraspAction,
        action_namespace="grasp_action",
        goal_gen_callback=generate_grasp_goal_msg,
        bb_var_name="target_grasp_pose",
    )
    set_object_in_hand_condition = py_trees.blackboard.SetBlackboardVariable(
        name="Set object in hand", variable_name="object_in_hand", variable_value=True
    )
    clear_target_grasp_pose = py_trees.blackboard.ClearBlackboardVariable(
        name="Clear grasp pose", variable_name="target_grasp_pose"
    )
    composite_do_grasp = py_trees.composites.Sequence(
        children=[
            composite_compute_grasp,
            button_do_grasp,
            action_grasp,
            clear_target_grasp_pose,
            set_object_in_hand_condition,
        ]
    )

    composite_check_in_hand = py_trees.composites.Selector(
        children=[check_obj_in_hand, composite_do_grasp]
    )

    # Action: drop object
    button_drop = py_trees_ros.subscribers.WaitForData(
        name="Button drop object?",
        topic_name="/manipulation_actions/stow",
        topic_type=std_msgs.msg.Empty,
    )
    drop_goal = DropGoal()
    action_drop = py_trees_ros.actions.ActionClient(
        name="Action drop object",
        action_spec=DropAction,
        action_goal=drop_goal,
        action_namespace="drop_action",
    )
    set_object_not_in_hand_condition = py_trees.blackboard.SetBlackboardVariable(
        name="Set object not in hand",
        variable_name="object_in_hand",
        variable_value=False,
    )
    composite_drop = py_trees.composites.Sequence(
        children=[
            composite_check_in_hand,
            button_drop,
            action_drop,
            set_object_not_in_hand_condition,
        ]
    )

    action_root.add_child(composite_drop)

    # -------- Return root -----------------------------------------
    root = py_trees.composites.Parallel(children=[reset_root, bb_root, action_root])

    return root


class PandaTree:
    def __init__(self, debug=False):

        if debug:
            py_trees.logging.level = py_trees.logging.Level.DEBUG

        self._root = get_root()
        self.tree = py_trees_ros.trees.BehaviourTree(self._root)

        self.show_tree_console()

    def show_tree_console(self):
        print("=" * 20)
        print("Behavior tree:")
        print("-" * 20)
        py_trees.display.print_ascii_tree(self.tree.root)
        print("=" * 20)

    def setup(self):
        self.tree.setup(timeout=15)
