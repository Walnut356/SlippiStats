import concurrent.futures
import os
from pathlib import Path
from typing import NamedTuple
import warnings
from collections import deque
from itertools import permutations
from math import degrees

import polars as pl

from ..enums.stage import Yoshis, get_ground
from ..enums.state import (
    ActionRange,
    ActionState,
    LCancel,
)
from ..event import Attack, Buttons
from ..game import Game
from ..util import Port, try_enum
from .common import (
    JoystickRegion,
    TechType,
    get_angle,
    get_joystick_region,
    get_post_di_angle,
    get_post_di_velocity,
    get_tech_type,
    is_damaged,
    is_dying,
    is_fastfalling,
    is_in_hitlag,
    is_in_hitstun,
    is_ledge_action,
    is_offstage,
    is_shielding,
    is_teching,
    just_entered_state,
    just_exited_state,
    just_input_l_cancel,
    just_took_damage,
)
from .computer import ComputerBase, IdentifierError, Player, PlayerCountError
from .stat_types import (
    DashData,
    Dashes,
    Data,
    LCancelData,
    LCancels,
    # RecoveryData,
    ShieldDropData,
    TakeHitData,
    TakeHits,
    TechData,
    Techs,
    WavedashData,
    Wavedashes,
)

# TODO probably reorganize thing_compute functions to thing_compute entry point + _thing_compute to do the calculation
# to allow for get_stats-like functionality that doesn't need an identifier.


class StatsComputer(ComputerBase):
    """
    Handles stats computation and stores the results

    Attributes:
        replay : Game
            The current parsed replay object
        replay_version : Start.SlippiVersion
            The parsed replay's version number. Can be compared to tuples and strings - e.g. (0, 1, 0), "0.1.0"
        replay_path : Pathlike | str
            Filepath used to parse the current replay if one was provided. Required for dolphin queue export
        players : list[Player]
            Contains metadata and all frames for each player in the game. Generated stats and combos are stored here
        queue : list[dict]
            formatted list of events used to create Clippi/Dolphin compatible json queues for playback

    Methods:
        prime_replay -> None
            Takes a Game object or a file path, parses the replay if necessary, and populates the correct information
            in the Computer object.
        get_player -> Player
            Takes an identifier (string connect code or physical port number), returns a
            Player object matching that identifier. Raises IdentifierError if the identifier is not found.
        get_opponent -> Player
            Takes an identifier (string connect code or physical port number), returns a Player object that does not
            match that identifier, if that identifier matches one player in the game.
        stats_compute -> list[Player]
            Optionally takes an identifier, returns a list of 1 or more Player objects for which stats were calculated.
            When an identifer is omitted, stats will be calculated for all Players in the game. Individual stats can be
            toggled using keyword arguments.
    """

    _wavedash_state: WavedashData | None
    _tech_state: TechData | None
    _dash_state: DashData | None
    _take_hit_state: TakeHitData | None
    # _recovery_state: RecoveryData | None

    def __init__(self, replay: os.PathLike | Game | str | None = None):
        self.players = []
        self._wavedash_state = None
        self._tech_state = None
        self._dash_state = None
        self._take_hit_state = None
        self._recovery_state = None
        if replay is not None:
            self.prime_replay(replay)
        else:
            self.replay = None

    def stats_compute(
        self,
        identifier: str | int | Port | None = None,
        wavedash=True,
        dash=True,
        tech=True,
        take_hit=True,
        l_cancel=True,
    ) -> Player | tuple[Player]:
        """
        Convenience function to calculate all stats for one or more players.

        If an identifier is provided, returns a single player object matching the identifier.

        If identifier is NOT provided, returns a tuple of both player objects.

        Args:
            identifier : str | int | Ports | None
                Defaults to None. str format "CODE#123". Ports/int correspond to physical ports p1-p4. If None,
                calculates stats for all players present in the game
            wavedash : bool
                Defaults to True. If false, wavedash calculation is skipped
            dash : bool
                Defaults to True. If false, dash calculation is skipped
            tech : bool
                Defaults to True. If false, tech calculation is skipped
            take_hit : bool
                Defaults to True. If false, take_hit calculation is skipped
            l_cancel : bool
                Defaults to True. If false, l_cancel calculation is skipped

        Returns:
            list[Player]
                length will always be 1 or 2.
        """
        if identifier is None:
            player_perms = permutations(self.players)
        else:
            player_perms = [(self.get_player(identifier), self.get_opponent(identifier))]

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
                self.l_cancel_compute(player=player)

        if identifier is not None:
            return self.get_player(identifier)
        else:
            return self.players

    # def stats_entry():

    def wavedash_compute(
        self,
        identifier: str | int | Port | None = None,
        *,
        player: Player | None = None,
    ) -> Wavedashes:
        """Accepts identifier connect code/port number, returns an interable container of WavedashData."""
        if identifier is None and player is None:
            raise ValueError("Compute functions require either a connect_code or player argument")

        if identifier is not None:
            player = self.get_player(identifier)

        for i, player_frame in enumerate(player.frames):
            player_state: ActionState | int = player_frame.post.state
            if i > 0:
                prev_player_frame = player.frames[i - 1]
                prev_player_state: ActionState | int = prev_player_frame.post.state

            # TODO add wavesurf logic?
            if player_state != ActionState.LAND_FALL_SPECIAL:
                continue

            if prev_player_state == ActionState.LAND_FALL_SPECIAL:
                continue

            # If we're in landfallspecial and weren't previously in landfallspecial:
            for j in range(0, 5):
                past_frame = player.frames[i - j]
                if (
                    Buttons.Physical.R in past_frame.pre.buttons.physical.pressed()
                    or Buttons.Physical.L in past_frame.pre.buttons.physical.pressed()
                ):
                    self._wavedash_state = WavedashData(
                        frame_index=i,
                        stocks_remaining=player_frame.post.stocks_remaining,
                        trigger_frame=0,
                        stick=player_frame.pre.joystick,
                        airdodge_frames=j,
                    )

                    for k in range(0, 5):
                        past_frame = player.frames[i - j - k]
                        if past_frame.post.state == ActionState.KNEE_BEND:
                            self._wavedash_state.trigger_frame = k
                            self._wavedash_state.waveland = False
                            break
            if self._wavedash_state is not None:
                player.stats.wavedashes.append(self._wavedash_state)

        return player.stats.wavedashes

    def dash_compute(
        self,
        identifier: str | None = None,
        player: Player | None = None,
    ) -> Dashes:
        """Accepts identifier connect code/port number, returns an interable container of DashData."""
        if identifier is None and player is None:
            raise ValueError("Compute functions require either a connect_code or player argument")

        if identifier is not None:
            player = self.get_player(identifier)

        for i, player_frame in enumerate(player.frames):
            if i < 2:
                continue
            player_post = player_frame.post
            player_state = player_post.state
            prev_player_frame = player.frames[i - 1]
            prev_player_state = prev_player_frame.post.state
            prev_prev_player_frame = player.frames[i - 2]
            prev_prev_player_state = prev_prev_player_frame.post.state

            # if last 2 states weren't dash and curr state is dash, start dash event
            # if the state pattern dash -> wait -> dash occurs, mark as dashdance
            # if prev prev state was dash, prev state was not dash, and curr state isn't dash, end dash event

            if just_entered_state(ActionState.DASH, player_state, prev_player_state):
                self._dash_state = DashData(
                    frame_index=i,
                    stocks_remaining=player_post.stocks_remaining,
                    direction=player_post.facing_direction.name,
                    start_pos=player_post.position.x,
                    is_dashdance=False,
                )

                if prev_player_state == ActionState.TURN and prev_prev_player_state == ActionState.DASH:
                    # if a dashdance pattern (dash -> turn -> dash) is detected, mark both dashes as part of dashdance
                    self._dash_state.is_dashdance = True
                    player.stats.dashes[-1].is_dashdance = True

            if just_exited_state(ActionState.DASH, player_state, prev_player_state):
                # finalize the dash and reset the state
                self._dash_state.end_pos = player_frame.post.position.x
                player.stats.dashes.append(self._dash_state)
                self._dash_state = None

        return player.stats.dashes

    def tech_compute(
        self,
        identifier: str | None = None,
        player: Player | None = None,
        opponent: Player | None = None,
    ) -> Techs:
        """Accepts identifier connect code/port number, returns an interable container of TechData."""
        if identifier is None and player is None:
            raise ValueError("Compute functions require either a connect_code or player argument")

        if identifier is not None:
            player = self.get_player(identifier)
            opponent = self.get_opponent(identifier)

        ground_check = True
        if self.replay_version < (2, 0, 0):
            ground_check = False
            warnings.warn(
                f"""Limited computation: some fields in tech_compute() require at least replay version 2.0.0,
                          got replay version: {self.replay_version}""",
                RuntimeWarning,
            )

        self._tech_state = None
        for i, player_frame in enumerate(player.frames):
            if i == 0:
                continue
            player_state = player_frame.post.state
            prev_player_frame = player.frames[i - 1]
            prev_player_state = prev_player_frame.post.state

            # TODO logical error: false positive on raw walljump. Check if they were in walltech beforehand?
            curr_teching = is_teching(player_state)
            was_teching = is_teching(prev_player_state)

            # Close out active techs if we were teching, and save some processing power if we weren't
            if not curr_teching:
                if was_teching and self._tech_state is not None:
                    if is_damaged(player_state):
                        self._tech_state.was_punished = True
                    player.stats.techs.append(self._tech_state)
                    self._tech_state = None
                continue

            opponent_frame = opponent.frames[i]

            # If we are, create a tech event, and start filling out fields based on the info we have
            if not was_teching:
                self._tech_state = TechData(
                    frame_index=i,
                    stocks_remaining=player_frame.post.stocks_remaining,
                    position=player_frame.post.position,
                    is_on_platform=player_frame.post.position.y > 5,  # kindof arbitrary, but it should work
                )

                if opponent_frame.post.most_recent_hit:
                    self._tech_state.last_hit_by = try_enum(Attack, opponent_frame.post.most_recent_hit)
                if ground_check:
                    self._tech_state.ground_id = get_ground(self.replay.start.stage, player_frame.post.last_ground_id)

            # this allows the tech data to update exactly once on the frame where the option is chosen
            # (e.g. missed tech -> tech right)
            # this matters for the positional checks, as we only want the earliest possible position values for
            # each "decision" or "event" that happens during the tech situation
            if player_state == prev_player_state:
                continue

            tech_type = get_tech_type(player_state, player_frame.post.facing_direction)

            match tech_type:
                case TechType.MISSED_TECH:
                    self._tech_state.is_missed_tech = True
                    self._tech_state.jab_reset = False

                case TechType.JAB_RESET:
                    self._tech_state.jab_reset = True
                # TODO If opponent isn't dead
                case TechType.TECH_LEFT | TechType.MISSED_TECH_ROLL_LEFT:
                    opnt_relative_position = opponent_frame.post.position.x - player_frame.post.position.x
                    if player_frame.post.facing_direction > 0:
                        self._tech_state.towards_center = True
                    else:
                        self._tech_state.towards_center = False
                    if opnt_relative_position > 0:
                        self._tech_state.towards_opponent = True
                    else:
                        self._tech_state.towards_opponent = False
                case TechType.TECH_RIGHT | TechType.MISSED_TECH_ROLL_RIGHT:
                    opnt_relative_position = opponent_frame.post.position.x - player_frame.post.position.x
                    if player_frame.post.facing_direction > 0:
                        self._tech_state.towards_center = False
                    else:
                        self._tech_state.towards_center = True
                    if opnt_relative_position > 0:
                        self._tech_state.towards_opponent = False
                    else:
                        self._tech_state.towards_opponent = True

                case _:  # Tech in place, getup attack
                    pass

            self._tech_state.tech_type = tech_type
        return player.stats.techs

    def take_hit_compute(
        self,
        identifier: str | None = None,
        player: Player | None = None,
        opponent: Player | None = None,
    ) -> TakeHits:
        """Accepts identifier connect code/port number, returns an interable container of TakeHitData."""
        if identifier is None and player is None:
            raise ValueError("Compute functions require either a connect_code or player argument")

        if identifier is not None:
            player = self.get_player(identifier)
            opponent = self.get_opponent(identifier)

        if self.replay_version < (2, 0, 0):
            warnings.warn(
                f"""No computation: take_hit_compute() requires at least replay version 2.0.0,
                          got replay version: {self.replay_version}""",
                RuntimeWarning,
            )
            return player.stats.take_hits

        knockback_check = True
        if self.replay_version < (3, 5, 0):
            knockback_check = False
            warnings.warn(
                f"""Partial computation: take_hit_compute() DI and knockback calculations
                require at least replay version 3.5.0, got replay version {self.replay_version}.""",
                RuntimeWarning,
            )

        for i, player_frame in enumerate(player.frames):
            if i == 0:
                continue
            prev_player_frame = player.frames[i - 1]
            opponent_frame = opponent.frames[i]

            # right now i don't care about shield SDI/ASDI but i may change this down the line
            # it requires slightly different logic
            in_hitlag = is_in_hitlag(player_frame.post.flags) and not is_shielding(prev_player_frame.post.state)
            was_in_hitlag = is_in_hitlag(prev_player_frame.post.flags) and not is_shielding(
                prev_player_frame.post.state
            )

            # this whole block basically calculates DI and KB trajectories and outputs the event
            if not in_hitlag:
                if was_in_hitlag and self._take_hit_state is not None:
                    self._take_hit_state.end_pos = prev_player_frame.post.position

                    effective_stick = player_frame.pre.joystick
                    match get_joystick_region(player_frame.pre.joystick):
                        case JoystickRegion.UP:
                            effective_stick.x = 0
                        case JoystickRegion.DOWN:
                            effective_stick.x = 0
                        case JoystickRegion.LEFT:
                            effective_stick.y = 0
                        case JoystickRegion.RIGHT:
                            effective_stick.y = 0

                        case JoystickRegion.DEAD_ZONE:
                            effective_stick.x = 0
                            effective_stick.y = 0
                        case _:
                            pass

                    self._take_hit_state.di_stick_pos = effective_stick

                    if knockback_check:
                        if self._take_hit_state.kb_velocity.x != 0.0 and self._take_hit_state.kb_velocity.y != 0.0:
                            self._take_hit_state.final_kb_angle = get_post_di_angle(
                                effective_stick, self._take_hit_state.kb_velocity
                            )

                            di_efficacy = (
                                abs(self._take_hit_state.final_kb_angle - self._take_hit_state.kb_angle) / 18
                            ) * 100
                            # modulo magic to truncate to 2 decimal place
                            # see: https://stackoverflow.com/a/49183117
                            self._take_hit_state.di_efficacy = di_efficacy - di_efficacy % 1e-2
                        else:
                            self._take_hit_state.final_kb_angle = self._take_hit_state.kb_angle

                        self._take_hit_state.final_kb_velocity = get_post_di_velocity(
                            self._take_hit_state.final_kb_angle,
                            self._take_hit_state.kb_velocity,
                        )

                    cstick = get_joystick_region(player_frame.pre.cstick)
                    if cstick != JoystickRegion.DEAD_ZONE:
                        self._take_hit_state.asdi = cstick
                    else:
                        self._take_hit_state.asdi = get_joystick_region(player_frame.pre.joystick)

                    self._take_hit_state._find_valid_sdi()

                    player.stats.take_hits.append(self._take_hit_state)
                    self._take_hit_state = None
                continue

            if not was_in_hitlag and just_took_damage(player_frame.post.percent, prev_player_frame.post.percent):
                self._take_hit_state = TakeHitData()
                self._take_hit_state.frame_index = i
                self._take_hit_state.last_hit_by = try_enum(Attack, opponent_frame.post.most_recent_hit)
                self._take_hit_state.state_before_hit = player.frames[i - 1].post.state
                self._take_hit_state.start_pos = player_frame.post.position
                self._take_hit_state.percent = player_frame.post.percent
                self._take_hit_state.grounded = not player_frame.post.is_airborne
                if knockback_check:
                    self._take_hit_state.kb_velocity = player_frame.post.knockback_speed
                    self._take_hit_state.kb_angle = degrees(get_angle(player_frame.post.knockback_speed))
                else:
                    self._take_hit_state.kb_velocity = None
                    self._take_hit_state.kb_angle = None

                if ActionRange.SQUAT_START <= prev_player_frame.post.state < ActionRange.SQUAT_END:
                    self._take_hit_state.crouch_cancel = True
                else:
                    self._take_hit_state.crouch_cancel = False
            # TODO this failed during all_stats(), DF had 1872 entries.
            # file:'Modern Replays\\FATK#202 (Yoshi) vs NUT#356 (Falco) on YS - 12-21-22 11.43pm .slp'
            # possibly fixed by changing <= ActionRange.AERIAL_ATTACK_END to <= ActionRange.SQUAT_END

            if self._take_hit_state is not None:
                self._take_hit_state.stick_regions_during_hitlag.append(get_joystick_region(player_frame.pre.joystick))
                self._take_hit_state.hitlag_frames += 1

        return player.stats.take_hits

    def l_cancel_compute(
        self,
        identifier: str | None = None,
        player: Player | None = None,
    ) -> LCancels:
        """Accepts identifier connect code/port number, returns an interable container of LCancelData."""
        if identifier is None and player is None:
            raise ValueError("Compute functions require either a connect_code or player argument")

        if identifier is not None:
            player = self.get_player(identifier)

        if self.replay_version < (2, 0, 0):
            warnings.warn(
                f"""No computation: l_cancel_compute() requires at least replay version 2.0.0,
                          got replay version: {self.replay_version}""",
                RuntimeWarning,
            )
            return player.stats.l_cancels

        # l_cancel_window: int | None = None
        # input_frame: int | None = None
        during_hitlag: bool = False
        trigger_input_frame = None
        for i, player_frame in enumerate(player.frames):
            l_cancel = player_frame.post.l_cancel
            if just_input_l_cancel(player_frame, player.frames[i - 1]):
                trigger_input_frame = i
                during_hitlag = is_in_hitlag(player_frame.post.flags)

            # TODO possible compatibility mode in the future
            # if player_just_input:
            #     l_cancel_window = 7

            #     if player_in_hitlag:
            #         during_hitlag = True

            # if player_in_hitlag and l_cancel_window is not None:
            #     pass
            # else:
            #     l_cancel_window -= 1
            #     # if you're more than 8 frames early, you probably weren't trying to l cancel
            #     if l_cancel_window <= 8:
            #         l_cancel_window = None

            if l_cancel == LCancel.NOT_APPLICABLE:
                continue

            # If you're more than a few frames early, it probably wasn't an l cancel input
            if trigger_input_frame is not None and (trigger_input_frame := trigger_input_frame - i) > 15:
                # unless you input during hitlag
                if (not during_hitlag) and trigger_input_frame < 25:
                    trigger_input_frame = None

            # Same deal if you're more than 5 frames late, but we also prioritize early over late
            if not (did_l_cancel := l_cancel == LCancel.SUCCESS) and trigger_input_frame is not None:
                for j in range(1, 6):
                    if just_input_l_cancel(player.frames[i + j], player.frames[i + j - 1]):
                        trigger_input_frame = j

            match player_frame.post.state:
                case ActionState.LANDING_AIR_N:
                    move = Attack.NAIR
                case ActionState.LANDING_AIR_F:
                    move = Attack.FAIR
                case ActionState.LANDING_AIR_B:
                    move = Attack.BAIR
                case ActionState.LANDING_AIR_HI:
                    move = Attack.UAIR
                case ActionState.LANDING_AIR_LW:
                    move = Attack.DAIR
                case _:
                    move = None
            if move is None:
                match player_frame.post.state:
                    case ActionState.ATTACK_AIR_N:
                        move = Attack.NAIR
                    case ActionState.ATTACK_AIR_F:
                        move = Attack.FAIR
                    case ActionState.ATTACK_AIR_B:
                        move = Attack.BAIR
                    case ActionState.ATTACK_AIR_HI:
                        move = Attack.UAIR
                    case ActionState.ATTACK_AIR_LW:
                        move = Attack.DAIR
                    case _:
                        move = None

            # Basically we're trying to match some form of aerial state. In situations where a player inputs an attack
            # on the same frame that they land, they won't be in an aerial attack state on their pre or post frame, so
            # we have to use the landing lag. Except if you get hit on the same frame that you land, the l cancel counts
            # even though you never enter the landlag state. If both happen, I could just use inputs on that frame to
            # grab the attempted attack but...
            # If you never enter the aerial animation AND you never enter the landlag animation, should that even count
            # towards l cancels?
            # In my eyes probably not? In the same way that slideoffs shouldn't count against you. Not l-cancelling has
            # no net impact in this scenario, and there's many cases where it could be another intended input entirely.
            # It happens infrequently enough that i don't think it'll matter that much, but if my numbers don't match
            # slippi-js, this is why.
            if move is None:
                continue

            player.stats.l_cancels.append(
                LCancelData(
                    frame_index=i,
                    stocks_remaining=player_frame.post.stocks_remaining,
                    move=move,
                    l_cancel=did_l_cancel,
                    trigger_input_frame=trigger_input_frame,
                    position=get_ground(self.replay.start.stage, player_frame.post.last_ground_id),
                    fastfall=is_fastfalling(player.frames[i - 1].post.flags),
                    during_hitlag=during_hitlag,
                )
            )

        player.stats.l_cancels._percentage()
        return player.stats.l_cancels

    # TODO probably refactor into out of shield data
    def shield_drop_compute(
        self,
        identifier: str | None = None,
        player: Player | None = None,
        opponent: Player | None = None,
    ) -> TakeHits:
        """Accepts identifier connect code/port number, returns an interable container of ShieldDropData."""
        if identifier is None and player is None:
            raise ValueError("Compute functions require either a connect_code or player argument")

        if identifier is not None:
            player = self.get_player(identifier)
            opponent = self.get_opponent(identifier)

        stage = self.replay.start.stage

        for i, player_frame in enumerate(player.frames):
            if i == 0:
                continue
            player_state = player_frame.post.state
            prev_player_frame = player.frames[i - 1]
            prev_player_state = prev_player_frame.post.state

            # can't use is_shielding() because you can't shielddrop during the guard release animation,
            # so it would false positive on drop shield -> first frame drop through platform
            player_was_shielding = (
                prev_player_state == ActionState.GUARD
                or prev_player_state == ActionState.GUARD_ON
                or prev_player_state == ActionState.GUARD_REFLECT
                or prev_player_state == ActionState.GUARD_SET_OFF
            )

            if player_state == ActionState.PASS and player_was_shielding:
                for j in range(1, 8):
                    past_frame = player.frames[i - j]
                    if past_frame.post.state == ActionState.GUARD_SET_OFF:
                        oo_shieldstun_frame = j
                        break
                else:
                    oo_shieldstun_frame = None

                player.stats.shield_drops.append(
                    ShieldDropData(
                        frame_index=i,
                        position=get_ground(stage, player_frame.post.last_ground_id),
                        oo_shieldstun_frame=oo_shieldstun_frame,
                    )
                )
                # TODO check for shieldstun and maybe followup option

        return player.stats.shield_drops

    # def ledge_action_compute():

    # def recovery_compute(
    #     self,
    #     identifier: str | None = None,
    #     player: Player | None = None,
    #     opponent: Player | None = None,
    # ) -> TakeHits:
    #     """Accepts identifier connect code/port number, returns an interable container of RecoveryData."""
    #     if identifier is None and player is None:
    #         raise ValueError("Compute functions require either a connect_code or player argument")

    #     if identifier is not None:
    #         player = self.get_player(identifier)
    #         opponent = self.get_opponent(identifier)

    #     stage = self.replay.start.stage

    #     for i, player_frame in enumerate(player.frames):
    #         opponent_frame = opponent.frames[i]

    #         player_state = player_frame.post.state
    #         player_position = player_frame.post.position
    #         player_just_offstage = is_offstage(player_position, stage) and not is_offstage(
    #             player.frames[i - 1].post.position, stage
    #         )
    #         player_in_hitstun = is_in_hitstun(player_frame.post.flags)

    #         if self._recovery_state is None and player_just_offstage and player_in_hitstun:
    #             self._recovery_state = RecoveryData(frame_index=i, last_hit_by=opponent_frame.post.position)

    #         if self._recovery_state is None:
    #             continue

    #         # record furthest position outward/hitstun end/knockback end/distance from ledge?
    #         # check resources - double jump, find a way to track marth/luigi side B juice, walljump
    #         # record every move used (with character enum), special attention to resource useage
    #         # look for end (death, land on stage/platform, grab ledge)
    #         # attempt to discern SD's (never stops moving towards ledge,
    #         # special move direction towards blast zone + dist to ledge, etc.)
    #         # retroactively assign meaning to previous actions (i.e. most recent action was "recovery move")
    #         # maybe record opponent position?
    #         # outcome, "reason": Death, ledge, stage, hit offstage, hit onstage | ledge hog, SD, pineapple, too far,

    #         player_is_dead = is_dying(player_state)
    #         player_is_ledge = is_ledge_action(player_state)
    #         player_did_land = (
    #             not player_frame.post.is_airborne
    #             and get_ground(stage, player_frame.post.last_ground_id) != Yoshis.RANDALL
    #         )

    # def track_


def _eef(file, connect_code):
    try:
        thing = StatsComputer(file).stats_compute(connect_code).stats
    except (IdentifierError, PlayerCountError):
        return (None, file)
    return (thing, file)


def get_stats(directory: os.PathLike | str, connect_code: str) -> NamedTuple:
    """Multiprocessed stats computation for handling bulk replays. Invalid replays and replays with no players matching
    the given identifier are automatically skipped.

    Args:
        directory : os.PathLike | str
            Path of the directory the replays are stored in
        connect_code : str
            Connect code str, format "CODE#123"
    Returns:
        NamedTuple[pl.DataFrame]
            Each element corresponds to a dataframe containing all stats for each processed replay.



    """
    thing = []
    for item in Data():
        thing.append(item.to_polars())

    Box = NamedTuple(
        "Box",
        wavedashes=pl.DataFrame,
        dashes=pl.DataFrame,
        techs=pl.DataFrame,
        take_hits=pl.DataFrame,
        l_cancels=pl.DataFrame,
    )
    count = 0

    with os.scandir(directory) as dir:
        with concurrent.futures.ProcessPoolExecutor() as executor:
            futures = {
                executor.submit(_eef, os.path.join(directory, entry.name), connect_code)
                for entry in dir
                if ".slp" in entry.name
            }

            # dasdf = concurrent.futures.wait(futures, return_when=concurrent.futures.FIRST_EXCEPTION)

            # print("okay")

            for future in concurrent.futures.as_completed(futures):
                if future.exception() is not None:
                    print(future.exception())
                    continue

                data, fpath = future.result()
                count += 1
                print(f"{count}: {fpath}")

                if data is None:
                    continue

                for i, item in enumerate(data):
                    df = item.to_polars()
                    try:
                        thing[i] = pl.concat([thing[i], df], how="vertical")
                    except Exception as e:
                        pass
                pass
                data = None

    for item in thing:
        item = item.sort(pl.col("date_time"))
    dfs = Box(
        thing[0],
        thing[1],
        thing[2],
        thing[3],
        thing[4],
    )
    return dfs
