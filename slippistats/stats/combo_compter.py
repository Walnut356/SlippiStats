from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .common import *
from ..event import Position
from ..util import *

COMBO_LENIENCY = 45
PRE_COMBO_BUFFER_FRAMES = 60
POST_COMBO_BUFFER_FRAMES = 90

class ComboEvent(Enum):
    """Enumeration for combo states"""
    # strictly speaking this is unnecessary and unused at the moment. AFAIK this is meant to be used in conjunction with real time
    # parsing, which this parser *can* do. Maybe a future TODO to get it to work properly.
    COMBO_START = "COMBO_START"
    COMBO_EXTEND = "COMBO_EXTEND"
    COMBO_END = "COMBO_END"

@dataclass
class MoveLanded():
    """Contains all data for a single move connecting"""
    player: str = field(default_factory=str)
    frame: int = 0
    move_id: int = 0
    hit_count: int = 0
    damage: float = 0
    opponent_position: Optional[Position] = None

@dataclass
class ComboData():
    """Contains a single complete combo, including movelist
    Helper functions for filtering combos include:
    minimum_damage(num)
    minimum_length(num)
    total_damage()"""
    player: str = ""
    moves: List[MoveLanded] = field(default_factory=list)
    did_kill: bool = False
    death_direction: Optional[str] = None
    player_stocks: int = 4
    opponent_stocks: int = 4
    did_end_game: bool = False
    start_percent: float = 0.0
    current_percent: float = 0.0
    end_percent: float = 0.0
    start_frame: int = 0
    end_frame: int = 0

    # I could probably add a "combo_filters()" abstraction with keyword arguments, but that feels like it shoehorns a bit too much by limiting
    # possible filter options, akin to clippi. Until i have a more robust list of filters, i won't make that further abstraction
    def total_damage(self) -> float:
        """Calculates total damage of the combo"""
        return self.end_percent - self.start_percent

    def minimum_length(self, num: int | float) -> bool:
        """Recieves number, returns True if combo's move count is greater than number"""
        return len(self.moves) >= num
    
    def minimum_damage(self, num: int | float) -> bool:
        """Recieves number, returns True if combo's total damage was over number"""
        return self.total_damage() >= num

@dataclass
class ComboState(Base):
    """Contains info used during combo calculation to build the final combo"""
    combo: Optional[ComboData] = field(default_factory=ComboData())
    move: MoveLanded = field(default_factory=MoveLanded())
    reset_counter: int = 0
    last_hit_animation: Optional[int] = None
    event: Optional[ComboEvent] = None


class ComboComputer(ComputerBase):
    """Base class for parsing combo events, call .prime_replay(path) to set up the instance,
    and .combo_compute(connect_code) to populate the computer's .combos list. """

    combos: List[ComboData]
    combo_state: Optional[ComboState]
    queue: List[Dict]
    replay_path: Path

    def __init__(self):
        self.rules = None
        self.combos = []
        self.players = []
        self.all_frames = []
        self.combo_state = None
        self.metadata = None
        self.queue = []

    def reset_data(self):
        self.combos = []
        self.combo_state = ComboState()
        self.queue = []
    
    def json_export(self, c: ComboData):
        self.queue.append({})
        self.queue[-1]["path"] = self.replay_path
        self.queue[-1]["gameStartAt"] = self.metadata.date.strftime("%m/%d/%y %I:%M %p")
        self.queue[-1]["startFrame"] = c.start_frame - PRE_COMBO_BUFFER_FRAMES
        self.queue[-1]["endFrame"] = c.end_frame + POST_COMBO_BUFFER_FRAMES
        return self.queue

    def combo_compute(self, connect_code: Optional[str]=None, hitstun_check=True, hitlag_check=True, tech_check=True, downed_check=True, 
                      offstage_check=True, dodge_check=True, shield_check=True, shield_break_check=True, ledge_check=True) -> None:
        """Generates list of combos from the replay information parsed using prime_replay(), returns nothing. Output is accessible as a list 
        through ComboComputer.combos"""
    # Most people want combos from a specific player, so forcing a connect code requirement
    # will cover most usecases
        player_ports = None
        opponent_port = None
        
        if connect_code:
            player_ports, opponent_port = self.generate_player_ports(connect_code)
        else:
            player_ports = self.generate_player_ports(connect_code)
            
        for port_index, player_port in enumerate(player_ports):
        # This is super gross but the c++ in me says this is the least annoying way to do this for now
            if len(player_ports) == 2:
                opponent_port:int = player_ports[port_index - 1] # This will obviously only work for 2 ports max
            for i, frame in enumerate(self.all_frames):
            # player data is stored as list of frames -> individual frame -> port -> leader/follower -> pre/post frame data
            # we make an interface as soon as possible because that's awful
                player_frame = self.port_frame(player_port, frame).post
                opponent_frame = self.port_frame(opponent_port, frame).post

            # Frames are -123 indexed, so we can't just pull the frame's .index to acquire the previous frame
            # this is the sole reason for enumerating self.all_frames
                prev_player_frame = self.port_frame_by_index(player_port, i - 1).post
                prev_opponent_frame = self.port_frame_by_index(opponent_port, i - 1).post

                opnt_action_state = opponent_frame.state
                opnt_is_damaged = is_damaged(opnt_action_state)
                # Bitflags are used because the hitstun frame count is used for a bunch of other things as well
                opnt_is_in_hitstun = is_in_hitstun(opponent_frame.flags) and hitstun_check
                opnt_is_grabbed = is_grabbed(opnt_action_state)
                opnt_is_cmd_grabbed = is_cmd_grabbed(opnt_action_state)
                opnt_damage_taken = calc_damage_taken(opponent_frame, prev_opponent_frame)

            # "Keep track of whether actionState changes after a hit. Used to compute move count
            # When purely using action state there was a bug where if you did two of the same
            # move really fast (such as ganon's jab), it would count as one move. Added
            # the actionStateCounter at this point which counts the number of frames since
            # an animation started. Should be more robust, for old files it should always be
            # null and null < null = false" - official parser
                action_changed_since_hit = not (player_frame.state == self.combo_state.last_hit_animation)
                action_frame_counter = player_frame.state_age
                prev_action_counter = prev_player_frame.state_age
                action_state_reset = action_frame_counter < prev_action_counter
                if(action_changed_since_hit or action_state_reset):
                    self.combo_state.last_hit_animation = None

            # I throw in the extra hitstun check to make it extra robust in case the animations are weird for whatever reason
            # Don't include hitlag check unless you want shield hits to start combo events.
            # There might be false positives on self damage like fully charged roy neutral b
                if (opnt_is_damaged or
                    opnt_is_grabbed or
                    opnt_is_cmd_grabbed or
                    opnt_is_in_hitstun):

                    combo_started = False

                # if the opponent has been hit and there's no "active" combo, start a new combo
                    if self.combo_state.combo is None:
                        self.combo_state.combo = ComboData(
                            player=f"Port {player_port}",
                            player_stocks=player_frame.stocks_remaining,
                            opponent_stocks=opponent_frame.stocks_remaining,
                            start_frame=frame.index,
                            start_percent=prev_opponent_frame.percent,
                            current_percent=opponent_frame.percent,
                            end_percent=opponent_frame.percent
                            )
                        #FIXME errors out when parsing based on ports w/ genesis 9 console replays
                        # if self.players[player_port].connect_code:
                        #     self.combo_state.combo.player = self.players[player_port].connect_code
                        # else:


                        self.combos.append(self.combo_state.combo)

                        combo_started = True

                # if the opponent has been hit and we're sure it's not the same move, record the move's data
                    if opnt_damage_taken:
                        if self.combo_state.last_hit_animation is None:
                            self.combo_state.move = MoveLanded()
                            #FIXME errors out when parsing based on ports w/ genesis 9 console replays
                            # if self.players[player_port].connect_code:
                            #     self.combo_state.move.player = self.players[player_port].connect_code
                            # else:
                            self.combo_state.move.player = f"Port {player_port}"
                            self.combo_state.move.frame = frame.index
                            self.combo_state.move.move_id = player_frame.most_recent_hit
                            self.combo_state.move.hit_count = 0
                            self.combo_state.move.damage = 0
                            self.combo_state.move.opponent_position = opponent_frame.position

                            self.combo_state.combo.moves.append(self.combo_state.move)

                            if not combo_started:
                                self.combo_state.event = ComboEvent.COMBO_EXTEND

                        if self.combo_state.move:
                            self.combo_state.move.hit_count += 1
                            self.combo_state.move.damage += opnt_damage_taken

                        self.combo_state.last_hit_animation = prev_player_frame.state

                    if combo_started:
                        self.combo_state.event = ComboEvent.COMBO_START

            # If a combo hasn't started and no damage was taken this frame, just skip to the next frame
                if self.combo_state.combo is None:
                    continue

            # Otherwise check the rest of the relevant statistics and determine whether to continue or terminate the combo
                opnt_is_in_hitlag = is_in_hitlag(opponent_frame.flags) and hitlag_check
                opnt_is_teching = is_teching(opnt_action_state) and tech_check
                opnt_is_downed = is_downed(opnt_action_state) and downed_check
                opnt_is_dying = is_dying(opnt_action_state)
                opnt_is_offstage = is_offstage(opponent_frame.position, self.rules.stage) and offstage_check
                opnt_is_dodging = is_dodging(opnt_action_state) and dodge_check and not is_wavedashing(opnt_action_state, opponent_port, i, self.all_frames)
                opnt_is_shielding = is_shielding(opnt_action_state) and shield_check
                opnt_is_shield_broken = is_shield_broken(opnt_action_state) and shield_break_check
                opnt_did_lose_stock = did_lose_stock(opponent_frame, prev_opponent_frame)
                opnt_is_ledge_action = is_ledge_action(opnt_action_state) and ledge_check
                opnt_is_maybe_juggled = is_maybe_juggled(opponent_frame.position, opponent_frame.is_airborne, self.rules.stage) #TODO and juggled check
                opnt_is_special_fall = is_special_fall(opnt_action_state)
                opnt_is_upb_lag = is_upb_lag(opnt_action_state, prev_opponent_frame.state)
                # opnt_is_recovery_lag = is_recovery_lag(opponent_frame.character, opnt_action_state)
            
                if not opnt_did_lose_stock:
                    self.combo_state.combo.current_percent = opponent_frame.percent

                player_did_lose_stock = did_lose_stock(player_frame, prev_player_frame)


            # reset the combo timeout timer to 0 if the opponent meets the following conditions
            # list expanded from official parser to allow for higher combo variety and capture more of what we would count as "combos"
            # noteably, this list will allow mid-combo shield pressure and edgeguards to be counted as part of a combo
                if (opnt_is_damaged or # Action state range
                    opnt_is_grabbed or # Action state range
                    opnt_is_cmd_grabbed or # Action state range
                    opnt_is_in_hitlag or # Bitflags (will always fail with old replays)
                    opnt_is_in_hitstun or # Bitflags (will always fail with old replays)
                    opnt_is_shielding or # Action state range
                    opnt_is_offstage or # X and Y coordinate check
                    opnt_is_dodging or # Action state range
                    opnt_is_dying or # Action state range
                    opnt_is_downed or # Action state range
                    opnt_is_teching or # Action state range
                    opnt_is_ledge_action or # Action state range
                    opnt_is_shield_broken or # Action state range
                    opnt_is_maybe_juggled or # Y coordinate check
                    opnt_is_special_fall or #Action state range
                    opnt_is_upb_lag): # Action state range

                    self.combo_state.reset_counter = 0
                else:
                    self.combo_state.reset_counter += 1

                should_terminate = False

            # All combo termination checks below
                if opnt_is_dying:
                    self.combo_state.combo.death_direction = get_death_direction(opnt_action_state)

                if opnt_did_lose_stock:
                    self.combo_state.combo.did_kill = True
                    if opponent_frame.stocks_remaining == 0:
                        self.combo_state.combo.did_end_game = True

                    should_terminate = True

                if (self.combo_state.reset_counter > COMBO_LENIENCY or
                    player_did_lose_stock):
                    should_terminate = True

            # If the combo should end, finalize the values, reset the temp storage
                if should_terminate:
                    self.combo_state.combo.end_frame = frame.index
                    self.combo_state.combo.end_percent = prev_opponent_frame.percent
                    self.combo_state.event = ComboEvent.COMBO_END

                    self.combo_state.combo = None
                    self.combo_state.move = None

def generate_clippi_header():
    header: Dict = {
        "mode": "queue",
        "replay": "",
        "isRealTimeMode": False,
        "outputOverlayFiles": True,
        "queue": [
        ]
        }
    return header

