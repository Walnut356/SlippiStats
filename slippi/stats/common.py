from enum import Enum
from math import atan2, degrees, tau
from os import PathLike
from typing import Any, Optional

from ..event import Frame, Position, Start, StateFlags, Velocity
from ..game import Game
from ..enums.state import ActionRange, ActionState
from ..enums.character import InGameCharacter
from ..enums.stage import Stage
from ..metadata import Metadata
from ..util import *


class ComputerBase():

    rules: Optional[Start]
    players: list[Metadata.Player]
    placements: Optional[list[int]]
    did_win: Optional[bool]
    all_frames: list[Frame]
    metadata: Optional[Metadata]
    queue: list[dict]
    replay_path: PathLike | str

    def prime_replay(self, replay: PathLike | Game | str, retain_data=False) -> None:
        """Parses a replay and loads the relevant data into the combo computer. Call combo_compute(connect_code) to extract combos
        from parsed replay"""
        if isinstance(replay, PathLike) or isinstance(replay, str):
            parsed_replay = Game(replay)
            self.replay_path = replay
        elif isinstance(replay, Game):
            parsed_replay = replay
            self.replay_path = ""
        else:
            raise TypeError("prime_replay accepts only PathLikes, strings, and Game objects.")

        self.rules = parsed_replay.start
        self.players = [player for player in parsed_replay.metadata.players if player is not None]
        self.all_frames = parsed_replay.frames
        self.metadata = parsed_replay.metadata
        self.placements = parsed_replay.end.player_placements
        self.did_win = None

            
        if not retain_data:
            self.reset_data()

    #FIXME the entry/return on this is dumb and I need to restructure it so it's useable anywhere outside of the stats calc
    def generate_player_ports(self, connect_code=None) -> Any: #difficult to express proper type hint
        player_port = -1
        opponent_port = -1
        if connect_code:
            for i, player in enumerate(self.players):
                if player.connect_code == connect_code.upper():
                    player_port = i
                else:
                    opponent_port = i
            if player_port == opponent_port: return [[], None]
            # TODO raise exception? log warning?
            # currently returns nothing so program will continue and stats calc will do nothing
            return [[player_port], opponent_port]
        else:
        # If there's no connect code, extract the port values of both *active* ports
            player_ports = [i for i, x in enumerate(self.rules.players) if x is not None]
        # And if there's more than 2 active ports, we return an empty list which should skip processing.
        # TODO make this an exception, but one that doesn't kill the program? Or just some way to track which replays don't get processed
            if len(player_ports) > 2:
                return []
            return player_ports
        
    def port_frame(self, port:int, frame: Frame) -> Frame.Port.Data:
        return frame.ports[port].leader
    
    def port_frame_by_index(self, port: int, index: int) -> Frame.Port.Data:
        return self.all_frames[index].ports[port].leader
    
    def reset_data(self):
        return
    
    def is_winner(self, identifier: int | str) -> bool:
        if isinstance(identifier, str):
            identifier = self.generate_player_ports(identifier)[0][0]
        return True if self.placements[identifier] == 0 else False



# Action state ranges are listed in id.py

def just_entered_state(action_state: int, curr: Frame.Port.Data | int, prev: Frame.Port.Data | int) -> bool:
    # TODO test this
    """Accepts state or frame, or post-frame"""
    for frame in [curr, prev]:
        if isinstance(frame, Frame.Port.Data):
            frame = frame.post.state
        if isinstance(frame, Frame.Port.Data.Post):
            frame = frame.state
        if isinstance(frame, int):
            pass

    return curr == action_state and prev != action_state

def is_damaged(action_state: int) -> bool:
    """Recieves action state, returns whether or not the player is in a damaged state.
    This includes all generic variants."""
    return (ActionRange.DAMAGE_START <= action_state <= ActionRange.DAMAGE_END)

def is_in_hitstun(flags: StateFlags) -> bool:
    """Recieves StateFlags, returns whether or not the hitstun bitflag is active.
    Always returns false on older replays that do not support stateflags."""
    if StateFlags.HIT_STUN in flags:
        return True
    else:
        return False

def is_in_hitlag(flags: StateFlags) -> bool:
    """Recieves StateFlags, returns whether or not the hitlag bitflag is active.
    Always returns false on older replays that do not support stateflags."""
    if StateFlags.HIT_LAG in flags:
        return True
    else:
        return False

def is_grabbed(action_state: int) -> bool:
    return (ActionRange.CAPTURE_START <= action_state <= ActionRange.CAPTURE_END)

def is_cmd_grabbed(action_state: int) -> bool:
    """Reieves action state, returns whether or not player is command grabbed (falcon up b, kirby succ, cargo throw, etc)"""
    #Includes sing, bury, ice, cargo throw, mewtwo side B, koopa claw, kirby suck, and yoshi egg
    return (((ActionRange.COMMAND_GRAB_RANGE1_START <= action_state <= ActionRange.COMMAND_GRAB_RANGE1_END)
        or (ActionRange.COMMAND_GRAB_RANGE2_START <= action_state <= ActionRange.COMMAND_GRAB_RANGE2_END))
        and not action_state == ActionState.BARREL_WAIT)

def is_teching(action_state: int) -> bool:
    """Recieves action state, returns whether or not it falls into the tech action states, includes walljump/ceiling techs"""
    return (ActionRange.TECH_START <= action_state <= ActionRange.TECH_END or
    action_state == ActionState.FLY_REFLECT_CEIL or
    action_state == ActionState.FLY_REFLECT_WALL)

def is_dying(action_state: int) -> bool:
    """Reieves action state, returns whether or not player is in the dying animation from any blast zone"""
    return (ActionRange.DYING_START <= action_state <= ActionRange.DYING_END)

def is_downed(action_state: int) -> bool:
    """Recieves action state, returns whether or not player is downed (i.e. missed tech)"""
    return (ActionRange.DOWN_START <= action_state <= ActionRange.DOWN_END)

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

    return (position.x < stage_bounds[0] or position.x > stage_bounds[1])

def is_shielding(action_state: int) -> bool:
    """Recieves action state, returns whether or not it falls into the guard action states"""
    return (ActionRange.GUARD_START <= action_state <= ActionRange.GUARD_END)

def is_shield_broken(action_state: int) -> bool:
    """Recieves action state, returns whether or not it falls into the guard_break action states"""
    return (ActionRange.GUARD_BREAK_START <= action_state <= ActionRange.GUARD_BREAK_END)

def is_dodging(action_state: int) -> bool:
    """Recieves action state and returns whether or not it falls into the 'dodging' category.
    Category includes shielded escape options (roll, spot dodge, airdodge)"""
    return (ActionRange.DODGE_START <= action_state <= ActionRange.DODGE_END)

def did_lose_stock(curr_frame: Frame.Port.Data.Post, prev_frame: Frame.Port.Data.Post) -> bool:
    """Recieves current and previous frame, returns stock difference between the two"""
    if not curr_frame or  not prev_frame:
        return False
    return prev_frame.stocks_remaining - curr_frame.stocks_remaining > 0

def calc_damage_taken(curr_frame: Frame.Port.Data.Post, prev_frame: Frame.Port.Data.Post) -> float:
    """Recieves current and previous frames, returns float of the difference in damage between the two"""
    percent = curr_frame.percent
    prev_percent = prev_frame.percent

    return percent - prev_percent

def is_ledge_action(action_state: int):
    """Recieves action state, returns whether or not player is currently hanging from the ledge, or doing any ledge action."""
    return ActionRange.LEDGE_ACTION_START <= action_state <= ActionRange.LEDGE_ACTION_END

def is_wavedashing(action_state: int, port:int,  frame_index: int, all_frames: list[Frame]) -> bool:
    if action_state != ActionState.ESCAPE_AIR:
        return False
    for i in range(1, 4):
        if (all_frames[frame_index - i].ports[port].leader.post.state == ActionState.LAND_FALL_SPECIAL):
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

def is_upb_lag(state:int, prev_state:int) -> bool:
    return (state == ActionState.LAND_FALL_SPECIAL and
            prev_state != ActionState.LAND_FALL_SPECIAL and
            prev_state != ActionState.KNEE_BEND and
            prev_state != ActionState.ESCAPE_AIR and
            (prev_state <= ActionRange.CONTROLLED_JUMP_START or
            prev_state >= ActionRange.CONTROLLED_JUMP_END))

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

def get_tech_type(action_state: int, direction) -> TechType | None:
    match action_state:
        case ActionState.PASSIVE | ActionState.DOWN_STAND_U | ActionState.DOWN_STAND_D:
            return TechType.TECH_IN_PLACE
        case ActionState.PASSIVE_STAND_F | ActionState.DOWN_FOWARD_U | ActionState.DOWN_FOWARD_D:
            if direction > 0: return TechType.TECH_RIGHT
            else: return TechType.TECH_LEFT
        case ActionState.PASSIVE_STAND_B | ActionState.DOWN_BACK_U | ActionState.DOWN_BACK_D:
            if direction > 0: return TechType.TECH_LEFT
            else: return TechType.TECH_RIGHT
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
    elif (stick_y >= 0.2875):
        region = JoystickRegion.UP
    elif (stick_x >= 0.2875):
        region = JoystickRegion.RIGHT
    elif (stick_y <= -0.2875):
        region = JoystickRegion.DOWN
    elif (stick_x <= -0.2875):
        region = JoystickRegion.LEFT

    return region

def get_total_velocity(player_frame_post: Frame.Port.Data.Post) -> Optional[Velocity]:
    # If we don't have one velocity value, we don't have any so we can just return
    if player_frame_post.self_air_speed is None:
        return None

    if player_frame_post.is_airborne:
        return player_frame_post.self_air_speed + player_frame_post.knockback_speed
    else:
        return player_frame_post.self_ground_speed + player_frame_post.knockback_speed
    
def get_angle(point: Velocity | Position):
    return degrees(atan2(point.y, point.x))

def max_di_angles(angle):
        angles = [angle - 90, angle + 90]
    
        if angles[0] < 180:
            angles[0] += 360
        if angles[1] > 180:
            angles[1] -= 360
        return angles

