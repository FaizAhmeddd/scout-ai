import numpy as np

# FIFA Laws of the Game marking dimensions (metres). Pitch length/width vary by stadium; markings do not.
PENALTY_BOX_WIDTH = 40.32
PENALTY_BOX_LENGTH = 16.5
GOAL_BOX_WIDTH = 18.32
GOAL_BOX_LENGTH = 5.5
CENTRE_CIRCLE_RADIUS = 9.15
PENALTY_SPOT_DISTANCE = 11.0


def pitch_keypoints(length: float, width: float) -> np.ndarray:
    """The 32 pitch landmarks in metres, in the keypoint order of Roboflow's football-pitch-detection model.

    Origin is the top-left corner flag; x runs along the touchline (0..length), y across the pitch (0..width).
    Ordering follows roboflow/sports `SoccerPitchConfiguration.vertices` (MIT licence).
    """
    mid_x, mid_y = length / 2, width / 2
    box_top, box_bottom = (width - PENALTY_BOX_WIDTH) / 2, (width + PENALTY_BOX_WIDTH) / 2
    goal_top, goal_bottom = (width - GOAL_BOX_WIDTH) / 2, (width + GOAL_BOX_WIDTH) / 2
    far_box_x = length - PENALTY_BOX_LENGTH
    far_goal_x = length - GOAL_BOX_LENGTH
    return np.array(
        [
            (0, 0), (0, box_top), (0, goal_top), (0, goal_bottom), (0, box_bottom), (0, width),
            (GOAL_BOX_LENGTH, goal_top), (GOAL_BOX_LENGTH, goal_bottom),
            (PENALTY_SPOT_DISTANCE, mid_y),
            (PENALTY_BOX_LENGTH, box_top), (PENALTY_BOX_LENGTH, goal_top),
            (PENALTY_BOX_LENGTH, goal_bottom), (PENALTY_BOX_LENGTH, box_bottom),
            (mid_x, 0), (mid_x, mid_y - CENTRE_CIRCLE_RADIUS), (mid_x, mid_y + CENTRE_CIRCLE_RADIUS), (mid_x, width),
            (far_box_x, box_top), (far_box_x, goal_top), (far_box_x, goal_bottom), (far_box_x, box_bottom),
            (length - PENALTY_SPOT_DISTANCE, mid_y),
            (far_goal_x, goal_top), (far_goal_x, goal_bottom),
            (length, 0), (length, box_top), (length, goal_top), (length, goal_bottom), (length, box_bottom), (length, width),
            (mid_x - CENTRE_CIRCLE_RADIUS, mid_y), (mid_x + CENTRE_CIRCLE_RADIUS, mid_y),
        ],
        dtype=np.float32,
    )
