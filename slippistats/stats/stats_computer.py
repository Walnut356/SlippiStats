from os import PathLike
from typing import Optional
from itertools import permutations

from ..enums import ActionState, ActionRange
from ..event import Attack, Buttons, Frame
from ..game import Game
from ..util import try_enum
from .common import (JoystickRegion,
                     TechType,
                     get_angle,
                     get_joystick_region,
                     get_tech_type, is_aerial_land_lag,
                     is_in_hitlag,
                     is_shielding, is_slideoff_action,
                     is_teching,
                     just_entered_state,
                     just_exited_state,)
from .computer import ComputerBase, Player
from .stat_types import (WavedashData, Wavedashes,
                        DashData, Dashes,
                        TechData, TechState, Techs,
                        TakeHitData, TakeHits,
                        LCancelData, LCancels,)


class StatsComputer(ComputerBase):

    wavedash_state: Optional[WavedashData]
    tech_state: Optional[TechState]
    dash_state: Optional[DashData]
    take_hit_state: Optional[TakeHitData]

    def __init__(self, replay: Optional[PathLike | Game | str]=None):
        self.players = []
        self.wavedash_state = None
        self.tech_state = None
        self.dash_state = None
        self.take_hit_state = None
        if replay is not None:
            self.prime_replay(replay)
        else:
            self.replay = None




    def stats_compute (self,
                       connect_code: Optional[str]=None,
                       wavedash=True,
                       dash=True,
                       tech=True,
                       take_hit=True,
                       l_cancel=True) -> list[Player]:

        if connect_code is None:
            player_perms = permutations(self.players)
        else:
            player_perms = (self.get_player(connect_code), self.get_opponent(connect_code))

        for player, opponent in player_perms:
            if wavedash:
                self.wavedash_compute(player=player)
            if dash:
                self.dash_compute(player=player)
            if tech:
                self.tech_compute(player=player, opponent=opponent)
            if take_hit:
                self.take_hit_compute(player=player, opponent=opponent)
            if l_cancel:
                self.l_cancel_compute(player=player, opponent=opponent)

    # def stats_entry():

    def wavedash_compute(self,
                         connect_code:Optional[str]=None,
                         player: Optional[Player]=None,) -> Wavedashes:
        if connect_code is None and player is None:
            raise ValueError("Compute functions require either a connect_code or player argument")

        if connect_code is not None:
            player = self.get_player(connect_code)


        for i, player_frame in enumerate(player.frames):
            player_state: ActionState | int = player_frame.post.state
            prev_player_frame = player.frames[i-1]
            prev_player_state: ActionState | int = prev_player_frame.post.state

            #TODO add wavesurf logic?
            if player_state != ActionState.LAND_FALL_SPECIAL:
                continue

            if prev_player_state == ActionState.LAND_FALL_SPECIAL:
                continue

            # If we're in landfallspecial and weren't previously in landfallspecial:
            for j in range(0, 5):
                past_frame = player.frames[i - j]
                if (Buttons.Physical.R in past_frame.pre.buttons.physical.pressed() or
                    Buttons.Physical.L in past_frame.pre.buttons.physical.pressed()):
                    self.wavedash_state = WavedashData(i, 0, player_frame.pre.joystick, j)

                    for k in range(0, 5):
                        past_frame = player.frames[i - j - k]
                        if past_frame.post.state == ActionState.KNEE_BEND:
                            self.wavedash_state.r_frame = k
                            self.wavedash_state.waveland = False
                            break

            player.stats.wavedashes.append(self.wavedash_state)

        #TODO think of some better way to return things
        return player.stats.wavedashes

    def dash_compute(self,
                         connect_code:Optional[str]=None,
                         player: Optional[Player]=None,) -> Dashes:

        if connect_code is None and player is None:
            raise ValueError("Compute functions require either a connect_code or player argument")

        if connect_code is not None:
            player = self.get_player(connect_code)


        for i, player_frame in enumerate(player.frames):
            player_state = player_frame.post.state
            prev_player_frame = player.frames[i - 1]
            prev_player_state = prev_player_frame.post.state
            prev_prev_player_frame = player.frames[i - 2]
            prev_prev_player_state = prev_prev_player_frame.post.state

            # if last 2 states weren't dash and curr state is dash, start dash event
            # if the state pattern dash -> wait -> dash occurs, mark as dashdance
            # if prev prev state was dash, prev state was not dash, and curr state isn't dash, end dash event

            if just_entered_state(ActionState.DASH, player_state, prev_player_state):
                self.dash_state = DashData(frame_index=i,
                                                direction=player_frame.post.facing_direction.name,
                                                start_pos=player_frame.post.position.x,
                                                is_dashdance=False)

                if prev_player_state == ActionState.TURN and prev_prev_player_state == ActionState.DASH:
                    # if a dashdance pattern (dash -> turn -> dash) is detected, mark both dashes as part of dashdance
                    self.dash_state.is_dashdance = True
                    player.stats.dashes[-1].is_dashdance = True

            if just_exited_state(ActionState.DASH, player_state, prev_player_state):
                # If not dashing for 2 consecutive frames, finalize the dash and reset the state
                self.dash_state.end_pos = player_frame.post.position.x
                player.stats.dashes.append(self.dash_state)
                self.dash_state = None

        return player.stats.dashes

    def tech_compute(self,
                         connect_code:Optional[str]=None,
                         player: Optional[Player]=None,
                         opponent:Optional[Player]=None,) -> Techs:
        if connect_code is None and player is None:
            raise ValueError("Compute functions require either a connect_code or player argument")

        if connect_code is not None:
            player = self.get_player(connect_code)
            opponent = self.get_opponent(connect_code)

        for i, player_frame in enumerate(player.frames):
                player_state = player_frame.post.state
                prev_player_frame = player.frames[i-1]
                prev_player_state = prev_player_frame.post.state


                #TODO logical error: false positive on raw walljump. Check if they were in walltech beforehand?
                curr_teching = is_teching(prev_player_state)
                was_teching = is_teching(prev_player_state)

            # Close out active techs if we were teching, and save some processing power if we weren't
                if not curr_teching:
                    if was_teching and self.tech_state is not None:
                        player.stats.techs.append(self.tech_state.tech)
                        self.tech_state = None
                    continue

                opponent_frame = opponent.frames[i]

            # If we are, create a tech event, and start filling out fields based on the info we have
                if not was_teching:
                    self.tech_state = TechState()
                    if opponent_frame.post.most_recent_hit:
                        self.tech_state.tech.last_hit_by = try_enum(Attack, opponent_frame.post.most_recent_hit).name
                    self.tech_state.tech.position = player_frame.post.position
                    self.tech_state.tech.is_on_platform = player_frame.post.position.y > 5 # Arbitrary value, i'll have to fact check this

                tech_type = get_tech_type(player_state, player_frame.post.facing_direction)

                self.tech_state.tech.tech_type = tech_type.name

                if player_state == self.tech_state.last_state:
                    continue

                self.tech_state.last_state = player_state

                match tech_type:
                    case TechType.MISSED_TECH, TechType.MISSED_WALL_TECH, TechType.MISSED_CEILING_TECH:
                        self.tech_state.tech.is_missed_tech = True
                        self.tech_state.tech.jab_reset = False

                    case TechType.JAB_RESET:
                        self.tech_state.tech.jab_reset = True

                    case TechType.TECH_LEFT:
                        opnt_relative_position = opponent_frame.post.position.x - player_frame.post.position.x
                        if player_frame.post.facing_direction > 0:
                            self.tech_state.tech.towards_center = True
                        else:
                            self.tech_state.tech.towards_center = False
                        if opnt_relative_position > 0:
                            self.tech_state.tech.towards_opponent = True
                        else:
                            self.tech_state.tech.towards_opponent = False
                    case TechType.TECH_RIGHT:
                        opnt_relative_position = opponent_frame.post.position.x - player_frame.post.position.x
                        if player_frame.post.facing_direction > 0:
                            self.tech_state.tech.towards_center = False
                        else:
                            self.tech_state.tech.towards_center = True
                        if opnt_relative_position > 0:
                            self.tech_state.tech.towards_opponent = False
                        else:
                            self.tech_state.tech.towards_opponent = True

                    case _: # Tech in place, getup attack
                        pass
        return player.stats.techs


    def take_hit_compute(self,
                         connect_code:Optional[str]=None,
                         player: Optional[Player]=None,
                         opponent:Optional[Player]=None,) -> TakeHits:
        if connect_code is None and player is None:
            raise ValueError("Compute functions require either a connect_code or player argument")

        if connect_code is not None:
            player = self.get_player(connect_code)
            opponent = self.get_opponent(connect_code)

        for i, player_frame in enumerate(player.frames):
                prev_player_frame = player.frames[i - 1]
                opponent_frame = opponent.frames[i]

                # right now i don't care about shield SDI/ASDI but i may change this down the line
                # it requires slightly different logic
                in_hitlag = is_in_hitlag(player_frame.post.flags) and not is_shielding(prev_player_frame.post.state)
                was_in_hitlag = is_in_hitlag(prev_player_frame.post.flags) and not is_shielding(prev_player_frame.post.state)


                if not in_hitlag:
                    if was_in_hitlag:
                        self.take_hit_state.end_position = prev_player_frame.post.position
                        self.take_hit_state.last_hit_by = try_enum(Attack, opponent_frame.post.most_recent_hit)
                        self.take_hit_state.final_knockback_angle = get_angle(player_frame.post.knockback_speed)
                        self.take_hit_state.di_angle = player_frame.pre.joystick
                        self.take_hit_state.final_knockback_velocity = player_frame.post.knockback_speed

                        stick = get_joystick_region(player_frame.pre.cstick)
                        if stick != JoystickRegion.DEAD_ZONE:
                            self.take_hit_state.asdi = stick
                        else:
                            self.take_hit_state.asdi = get_joystick_region(player_frame.pre.joystick)

                        self.take_hit_state.find_valid_sdi()

                        player.stats.take_hits.append(self.take_hit_state)
                    continue

                if not was_in_hitlag:
                    self.take_hit_state = TakeHitData()
                    self.take_hit_state.start_position = player_frame.post.position
                    self.take_hit_state.percent = player_frame.post.percent
                    self.take_hit_state.grounded = not player_frame.post.is_airborne
                    self.take_hit_state.knockback_velocity = player_frame.post.knockback_speed
                    self.take_hit_state.knockback_angle = get_angle(player_frame.post.knockback_speed)
                    if ActionRange.SQUAT_START <= prev_player_frame.post.state <= ActionRange.SQUAT_END:
                        self.take_hit_state.crouch_cancel = True
                    else:
                        self.take_hit_state.crouch_cancel = False
                #TODO this failed during all_stats(), DF had 1872 entries.
                # file:'Modern Replays\\FATK#202 (Yoshi) vs NUT#356 (Falco) on YS - 12-21-22 11.43pm .slp'
                # possibly fixed by changing <= ActionRange.AERIAL_ATTACK_END to <= ActionRange.SQUAT_END
                self.take_hit_state.stick_regions_during_hitlag.append(get_joystick_region(player_frame.pre.joystick))
                self.take_hit_state.hitlag_frames += 1

        return player.stats.take_hits


    def l_cancel_compute(self,
                         connect_code:Optional[str]=None,
                         player: Optional[Player]=None,) -> LCancels:

        if connect_code is None and player is None:
            raise ValueError("Compute functions require either a connect_code or player argument")

        if connect_code is not None:
            player = self.get_player(connect_code)

        for i, player_frame in enumerate(player.frames):
            player_state = player_frame.post.state
            l_cancel = player_frame.post.l_cancel

            if l_cancel == 0:
                continue

            trigger_input_frame: Optional[int] = None
            slideoff = False
            # Check for l/r press 20 frames prior and l/r press and/or slideoff up to 10 frames after
            for j in range(10):
                # Because we're counting away from the landing frame, we want the first input and no others
                if (trigger_input_frame is None and
                    Buttons.logical.R in player.frames[i + j].pre.buttons or
                    Buttons.logical.L in player.frames[i + j].pre.buttons):
                    trigger_input_frame = j
                    continue

                if (is_aerial_land_lag(player_state) and is_slideoff_action(player.frames[i - 1].post.state)):
                    slideoff = True

            for j in range(20):
                # Here we can just immediately exit the loop since there's nothing else we need to check for
                if (Buttons.logical.R in player.frames[i - j].pre.buttons or
                    Buttons.logical.L in player.frames[i - j].pre.buttons):
                    trigger_input_frame = -j
                    break

            player.stats.l_cancels.append(LCancelData(
                frame_index=i,
                move=player.frames[i - 1].post.state,
                l_cancel=True if l_cancel == 1 else False,
                trigger_input_frame=trigger_input_frame,
                slideoff=slideoff
                ))


    # def recovery_compute(self, connect_code: Optional[str]=None):
    #     player_ports: list[int]
    #     opponent_port: int

    #     if connect_code:
    #         player_ports, opponent_port = self.generate_player_ports(connect_code)
    #         self.did_win = self.is_winner(connect_code)
    #     else:
    #         player_ports = self.generate_player_ports()

    #     for port_index, player_port in enumerate(player_ports):
    #         if len(player_ports) == 2:
    #             opponent_port = player_ports[port_index - 1] # Only works for 2 ports
    #         self.data.l_cancel = LCancelData(player_port, connect_code)

    #         for i, frame in enumerate(self.all_frames):
    #             player_frame = self.port_frame(player_port, frame)
    #             opponent_frame = self.port_frame(opponent_port, frame)

    #             player_is_offstage = is_offstage(player_frame.post.position, self.rules.stage)
    #             player_was_offstage = is_offstage(player_frame.post.position, self.rules.stage)
    #             player_in_hitstun = is_in_hitstun(player_frame.post.state)

    #             if not player_is_offstage: continue

    #             if not player_was_offstage: continue
