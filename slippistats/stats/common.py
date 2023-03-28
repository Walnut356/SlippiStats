from collections.abc import Callable
from enum import Enum
from math import (
    atan2,
    cos,
    degrees,
    isclose,
    radians,
    sin,
    sqrt,
    tau,
)

# from ..enums.character import InGameCharacter
from ..controller import Buttons
from ..enums.stage import Stage
from ..enums.state import (
    ActionRange,
    ActionState,
    Field2,
    Field4,
)
from ..event import Frame, Position, Velocity
from ..util import IntEnum

# ---------------------------------------------------------------------------- #
#                                 State Helpers                                #
# ---------------------------------------------------------------------------- #


def just_entered_state(
    action_state: int | Callable,
    curr_state: ActionState | int,
    prev_state: ActionState | int,
) -> bool:
    # TODO test this
    if isinstance(action_state, Callable):
        return action_state(curr_state) and not action_state(prev_state)

    return curr_state == action_state and prev_state != action_state


def just_exited_state(
    action_state: int, curr_state: ActionState | int, prev_state: ActionState | int
) -> bool:
    if isinstance(action_state, Callable):
        return action_state(prev_state) and not action_state(curr_state)

    return prev_state == action_state and curr_state != action_state


def just_input_l_cancel(
    curr_frame: Frame.Port.Data, prev_frame: Frame.Port.Data
) -> bool:
    curr = curr_frame.pre.buttons.logical
    prev = prev_frame.pre.buttons.logical

    return (
        Buttons.Logical.R in curr
        or Buttons.Logical.L in curr
        or Buttons.Logical.Z in curr
        or Buttons.Logical.TRIGGER_ANALOG in curr
    ) and not (
        Buttons.Logical.R in prev
        or Buttons.Logical.L in prev
        or Buttons.Logical.Z in prev
        or Buttons.Logical.TRIGGER_ANALOG in prev
    )


def just_took_damage(percent: int, prev_percent: int) -> bool:
    return not isclose(percent, prev_percent, abs_tol=1e-03)


def is_damaged(action_state: int) -> bool:
    """Recieves action state, returns whether or not the player is in a damaged state.
    This includes all generic variants."""
    return (
        (ActionRange.DAMAGE_START <= action_state <= ActionRange.DAMAGE_END)
        or action_state == ActionState.DOWN_DAMAGE_U
        or action_state == ActionState.DOWN_DAMAGE_D
    )  # Jab reset states, prevents combo counter from ignoring them if not checking hitstun


def is_in_hitstun(flags: list[IntEnum]) -> bool:
    """Recieves StateFlags, returns whether or not the hitstun bitflag is active.
    Always returns false on older replays that do not support stateflags."""
    for field in flags:
        if Field4.HIT_STUN in field:
            return True
    else:
        return False


def is_in_hitlag(flags: list[IntEnum]) -> bool:
    """Recieves StateFlags, returns whether or not the hitlag bitflag is active.
    Always returns false on older replays that do not support stateflags."""
    for field in flags:
        if Field2.HIT_LAG in field:
            return True
    else:
        return False


def is_grabbed(action_state: int) -> bool:
    return ActionRange.CAPTURE_START <= action_state <= ActionRange.CAPTURE_END


def is_cmd_grabbed(action_state: int) -> bool:
    """Reieves action state, returns whether or not player is command grabbed (falcon up b, kirby succ, cargo throw, etc)"""
    # Includes sing, bury, ice, cargo throw, mewtwo side B, koopa claw, kirby suck, and yoshi egg
    return (
        (
            ActionRange.COMMAND_GRAB_RANGE1_START
            <= action_state
            <= ActionRange.COMMAND_GRAB_RANGE1_END
        )
        or (
            ActionRange.COMMAND_GRAB_RANGE2_START
            <= action_state
            <= ActionRange.COMMAND_GRAB_RANGE2_END
        )
    ) and not action_state == ActionState.BARREL_WAIT


def is_teching(action_state: int) -> bool:
    """Recieves action state, returns whether or not it falls into the tech action states, includes walljump/ceiling techs"""
    return (
        ActionRange.TECH_START <= action_state <= ActionRange.TECH_END
        or ActionRange.DOWN_START <= action_state <= ActionRange.DOWN_END
        or action_state == ActionState.FLY_REFLECT_CEIL
        or action_state == ActionState.FLY_REFLECT_WALL
    )


def is_dying(action_state: int) -> bool:
    """Reieves action state, returns whether or not player is in the dying animation from any blast zone"""
    return ActionRange.DYING_START <= action_state <= ActionRange.DYING_END


def is_downed(action_state: int) -> bool:
    """Recieves action state, returns whether or not player is downed (i.e. missed tech)"""
    return ActionRange.DOWN_START <= action_state <= ActionRange.DOWN_END


def is_offstage(position: Position, stage) -> bool:
    """Recieves current frame and stage ID, returns whether or not the player is outside the X coordinates denoting the on-stage bounds"""
    stage_bounds = [0, 0]

    if position.y < -5:
        return True

    # I manually grabbed these values using uncle punch and just moving as close to the edge as I could and rounding away from 0.
    # They don't cover 100% of cases (such as being underneath BF), but it's accurate enough for most standard edgeguard situations
    # In the future I'll add a Y value check, but i'll handle that when i handle ading Y value for juggles.
    match stage:
        case Stage.FOUNTAIN_OF_DREAMS:
            stage_bounds = [-64, 64]
        case Stage.YOSHIS_STORY:
            stage_bounds = [-56, 56]
        case Stage.DREAM_LAND_N64:
            stage_bounds = [-73, 73]
        case Stage.POKEMON_STADIUM:
            stage_bounds = [-88, 88]
        case Stage.BATTLEFIELD:
            stage_bounds = [-67, 67]
        case Stage.FINAL_DESTINATION:
            stage_bounds = [-89, 89]

    return position.x < stage_bounds[0] or position.x > stage_bounds[1]


def is_shielding(action_state: int) -> bool:
    """Recieves action state, returns whether or not it falls into the guard action states"""
    return ActionRange.GUARD_START <= action_state <= ActionRange.GUARD_END


def is_shield_broken(action_state: int) -> bool:
    """Recieves action state, returns whether or not it falls into the guard_break action states"""
    return ActionRange.GUARD_BREAK_START <= action_state <= ActionRange.GUARD_BREAK_END


def is_dodging(action_state: int) -> bool:
    """Recieves action state and returns whether or not it falls into the 'dodging' category.
    Category includes shielded escape options (roll, spot dodge, airdodge)"""
    return ActionRange.DODGE_START <= action_state <= ActionRange.DODGE_END


def did_lose_stock(
    curr_frame: Frame.Port.Data.Post, prev_frame: Frame.Port.Data.Post
) -> bool:
    """Recieves current and previous frame, returns stock difference between the two"""
    if not curr_frame or not prev_frame:
        return False
    return prev_frame.stocks_remaining - curr_frame.stocks_remaining > 0


def is_ledge_action(action_state: int):
    """Recieves action state, returns whether or not player is currently hanging from the ledge, or doing any ledge action."""
    return (
        ActionRange.LEDGE_ACTION_START <= action_state <= ActionRange.LEDGE_ACTION_END
    )


def is_wavedashing(
    action_state: int, port: int, frame_index: int, all_frames: list[Frame]
) -> bool:
    if action_state != ActionState.ESCAPE_AIR:
        return False
    for i in range(1, 4):
        if (
            all_frames[frame_index - i].ports[port].leader.post.state
            == ActionState.LAND_FALL_SPECIAL
        ):
            return True
    return False


def is_maybe_juggled(position: Position, is_airborne: bool, stage: Stage) -> bool:
    if is_airborne is not None:
        if not is_airborne:
            return False

        match stage:
            case Stage.FOUNTAIN_OF_DREAMS:
                stage_bounds = 42
            case Stage.YOSHIS_STORY:
                stage_bounds = 42
            case Stage.DREAM_LAND_N64:
                stage_bounds = 51
            case Stage.POKEMON_STADIUM:
                # similar side plat heights to yoshi's, so we can steal the top plat height as well
                stage_bounds = 42
            case Stage.BATTLEFIELD:
                stage_bounds = 54
            case Stage.FINAL_DESTINATION:
                # No plats, so we'll just use a lower-than-average value
                stage_bounds = 35
            case _:
                return False

    return position.y >= stage_bounds


def is_special_fall(state: int) -> bool:
    return ActionRange.FALL_SPECIAL_START <= state <= ActionRange.FALL_SPECIAL_END


def is_upb_lag(state: int, prev_state: int) -> bool:
    return (
        state == ActionState.LAND_FALL_SPECIAL
        and prev_state != ActionState.LAND_FALL_SPECIAL
        and prev_state != ActionState.KNEE_BEND
        and prev_state != ActionState.ESCAPE_AIR
        and (
            prev_state <= ActionRange.CONTROLLED_JUMP_START
            or prev_state >= ActionRange.CONTROLLED_JUMP_END
        )
    )


def is_aerial_land_lag(state: int) -> bool:
    return ActionRange.AERIAL_LAND_LAG_START <= state <= ActionRange.AERIAL_LAND_LAG_END


def is_slideoff_action(state: int) -> bool:
    # TODO make sure this list is exhaustive (oh wait i forgot B moves =I)
    # maybe there's required pre-frame air states? Otherwise could check is_airborne and didn't take damage
    # for slideoffs, the possible action states on the next frame should be:
    # double jump, air-fall, air-attack, air-b move or airdodge
    return (
        (ActionState.JUMP_AERIAL_F <= state <= ActionRange.ACTIONABLE_AIR_END)
        or (ActionRange.AERIAL_ATTACK_START <= state <= ActionState.ATTACK_AIR_LW)
        or (ActionState.ESCAPE_AIR == state)
    )


# VERY untested, probably don't use
# def is_recovery_lag(character: InGameCharacter, state: ActionState) -> bool:
#     return state.value in RECOVERY_LAG[character]


def get_death_direction(action_state: int) -> str:
    match action_state:
        case 0:
            return "Bottom"
        case 1:
            return "Left"
        case 2:
            return "Right"
        case 3, 4, 5, 6, 7, 8, 9, 10:
            return "Top"
        case _:
            return "Invalid Action State"


class TechType(Enum):
    TECH_IN_PLACE = 0
    TECH_LEFT = 1
    TECH_RIGHT = 2
    GET_UP_ATTACK = 3
    MISSED_TECH = 4
    WALL_TECH = 5
    MISSED_WALL_TECH = 6
    WALL_JUMP_TECH = 7
    CEILING_TECH = 8
    MISSED_CEILING_TECH = 9
    JAB_RESET = 10
    MISSED_TECH_GET_UP = 11
    MISSED_TECH_ROLL_RIGHT = 12
    MISSED_TECH_ROLL_LEFT = 13


# yapf: disable
def get_tech_type(action_state: int, direction) -> TechType | None:
    match action_state:
        case ActionState.PASSIVE:
            return TechType.TECH_IN_PLACE
        case ActionState.DOWN_STAND_U | ActionState.DOWN_STAND_D:
            return TechType.MISSED_TECH_GET_UP

        case ActionState.PASSIVE_STAND_F:
            if direction > 0:
                return TechType.TECH_RIGHT
            else:
                return TechType.TECH_LEFT
        case ActionState.DOWN_FOWARD_U | ActionState.DOWN_FOWARD_D:
            if direction > 0:
                return TechType.MISSED_TECH_ROLL_RIGHT
            else:
                return TechType.MISSED_TECH_ROLL_LEFT

        case ActionState.PASSIVE_STAND_B:
            if direction > 0:
                return TechType.TECH_LEFT
            else:
                return TechType.TECH_RIGHT
        case   ActionState.DOWN_BACK_U | ActionState.DOWN_BACK_D:
            if direction > 0:
                return TechType.MISSED_TECH_ROLL_LEFT
            else:
                return TechType.MISSED_TECH_ROLL_RIGHT

        case ActionState.DOWN_ATTACK_U | ActionState.DOWN_ATTACK_D:
            return TechType.GET_UP_ATTACK

        case ActionState.DOWN_BOUND_U | ActionState.DOWN_BOUND_D | ActionState.DOWN_WAIT_D | ActionState.DOWN_WAIT_U:
            return TechType.MISSED_TECH

        case ActionState.DOWN_DAMAGE_U | ActionState.DOWN_DAMAGE_D:
            return TechType.JAB_RESET

        case ActionState.PASSIVE_WALL:
            return TechType.WALL_TECH

        case ActionState.PASSIVE_WALL_JUMP:
            return TechType.WALL_JUMP_TECH

        case ActionState.PASSIVE_CEIL:
            return TechType.CEILING_TECH

        case _:
            return None
# yapf: enable

# ---------------------------------------------------------------------------- #
#                                 Calc Helpers                                 #
# ---------------------------------------------------------------------------- #


class JoystickRegion(IntEnum):
    """Deadzone is -1, directions start at 1. Cardinals are even, diagonals are odd"""

    DEAD_ZONE = -1
    UP = 0
    UP_RIGHT = 1
    RIGHT = 2
    DOWN_RIGHT = 3
    DOWN = 4
    DOWN_LEFT = 5
    LEFT = 6
    UP_LEFT = 7


# yapf: disable
def get_joystick_region(stick_position: Position) -> JoystickRegion:
    region = JoystickRegion.DEAD_ZONE

    stick_x, stick_y = stick_position.x, stick_position.y

    if (stick_x >= 0.2875 and stick_y >= 0.2875):
        region = JoystickRegion.UP_RIGHT

    elif (stick_x >= 0.2875 and stick_y <= -0.2875):
        region = JoystickRegion.DOWN_RIGHT

    elif (stick_x <= -0.2875 and stick_y <= -0.2875):
        region = JoystickRegion.DOWN_LEFT

    elif (stick_x <= -0.2875 and stick_y >= 0.2875):
        region = JoystickRegion.UP_LEFT

    elif stick_y >= 0.2875:
        region = JoystickRegion.UP

    elif stick_x >= 0.2875:
        region = JoystickRegion.RIGHT

    elif stick_y <= -0.2875:
        region = JoystickRegion.DOWN

    elif stick_x <= -0.2875:
        region = JoystickRegion.LEFT

    return region
# yapf: enable


def get_total_velocity(player_frame_post: Frame.Port.Data.Post) -> Velocity | None:
    # If we don't have one velocity value, we don't have any so we can just return
    if player_frame_post.self_air_speed is None:
        return None

    if player_frame_post.is_airborne:
        return player_frame_post.self_air_speed + player_frame_post.knockback_speed
    else:
        return player_frame_post.self_ground_speed + player_frame_post.knockback_speed


def get_angle(point: Velocity | Position):
    # atan2 returns 0 to 180 and 0 to -180.
    # By adding tau (2 * pi) and wrapping around tau, we normalize to the familiar 0-360
    return (atan2(point.y, point.x) + tau) % tau


def get_post_di_angle(joystick: Position, knockback: Position):
    kb_angle = get_angle(knockback)
    joystick_angle = get_angle(joystick)

    angle_diff = kb_angle - joystick_angle
    if angle_diff > 180:
        angle_diff -= 360

    perp_dist = sin(angle_diff) * sqrt((joystick.x**2) + (joystick.y**2))
    angle_offset = (perp_dist**2) * 18

    if angle_offset > 18:
        angle_offset = 18
    if -180 < angle_diff < 0:
        angle_offset *= -1

    return degrees(kb_angle) - angle_offset


def get_post_di_velocity(post_kb_angle: float, og_kb: Velocity):
    magnitude = sqrt(og_kb.x**2 + og_kb.y**2)
    post_kb_angle = radians(post_kb_angle)
    return Velocity(cos(post_kb_angle) * magnitude, sin(post_kb_angle) * magnitude)


def max_di_angles(angle):
    angles = [angle - 90, angle + 90]

    if angles[0] < 180:
        angles[0] += 360
    if angles[1] > 180:
        angles[1] -= 360
    return angles


def calc_damage_taken(
    curr_frame: Frame.Port.Data.Post, prev_frame: Frame.Port.Data.Post
) -> float:
    """Recieves current and previous frames, returns float of the difference in damage between the two"""
    percent = curr_frame.percent
    prev_percent = prev_frame.percent

    return percent - prev_percent


# ---------------------------------------------------------------------------- #
#                                Output Helpers                                #
# ---------------------------------------------------------------------------- #


def get_playback_header() -> dict:
    return {
        "mode": "queue",
        "replay": "",
        "isRealTimeMode": False,
        "outputOverlayFiles": True,
        "queue": [],
    }
