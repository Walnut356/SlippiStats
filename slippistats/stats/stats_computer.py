import concurrent.futures
import os
import warnings
from itertools import permutations
from math import degrees

import polars as pl

from ..enums.ground import Yoshis, get_ground
from ..enums.state import (
    ActionRange,
    ActionState,
    LCancel,
)
from ..event import Attack, Buttons
from ..game import Game
from ..util import try_enum
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
from .computer import ComputerBase, Player
from .stat_types import (
    DashData,
    Dashes,
    LCancelData,
    LCancels,
    RecoveryData,
    ShieldDropData,
    TakeHitData,
    TakeHits,
    TechData,
    Techs,
    TechState,
    WavedashData,
    Wavedashes,
)


class StatsComputer(ComputerBase):
    wavedash_state: WavedashData | None
    tech_state: TechState | None
    dash_state: DashData | None
    take_hit_state: TakeHitData | None
    recovery_state: RecoveryData | None

    def __init__(self, replay: os.PathLike | Game | str | None = None):
        self.players = []
        self.wavedash_state = None
        self.tech_state = None
        self.dash_state = None
        self.take_hit_state = None
        self.recovery_state = None
        if replay is not None:
            self.prime_replay(replay)
        else:
            self.replay = None

    def stats_compute(
        self,
        connect_code: str | None = None,
        wavedash=True,
        dash=True,
        tech=True,
        take_hit=True,
        l_cancel=True,
    ) -> list[Player]:
        if connect_code is None:
            player_perms = permutations(self.players)
        else:
            player_perms = [(self.get_player(connect_code), self.get_opponent(connect_code))]

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

        return self.players

    # def stats_entry():

    def wavedash_compute(
        self,
        connect_code: str | None = None,
        player: Player | None = None,
    ) -> Wavedashes:
        if connect_code is None and player is None:
            raise ValueError("Compute functions require either a connect_code or player argument")

        if connect_code is not None:
            player = self.get_player(connect_code)

        for i, player_frame in enumerate(player.frames):
            player_state: ActionState | int = player_frame.post.state
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
                    self.wavedash_state = WavedashData(i, 0, player_frame.pre.joystick, j)

                    for k in range(0, 5):
                        past_frame = player.frames[i - j - k]
                        if past_frame.post.state == ActionState.KNEE_BEND:
                            self.wavedash_state.r_frame = k
                            self.wavedash_state.waveland = False
                            break

            player.stats.wavedashes.append(self.wavedash_state)

        # TODO think of some better way to return things
        return player.stats.wavedashes

    def dash_compute(
        self,
        connect_code: str | None = None,
        player: Player | None = None,
    ) -> Dashes:
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
                self.dash_state = DashData(
                    frame_index=i,
                    direction=player_frame.post.facing_direction.name,
                    start_pos=player_frame.post.position.x,
                    is_dashdance=False,
                )

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

    def tech_compute(
        self,
        connect_code: str | None = None,
        player: Player | None = None,
        opponent: Player | None = None,
    ) -> Techs:
        if connect_code is None and player is None:
            raise ValueError("Compute functions require either a connect_code or player argument")

        if connect_code is not None:
            player = self.get_player(connect_code)
            opponent = self.get_opponent(connect_code)

        self.tech_state = TechState()
        for i, player_frame in enumerate(player.frames):
            player_state = player_frame.post.state
            prev_player_frame = player.frames[i - 1]
            prev_player_state = prev_player_frame.post.state

            # TODO logical error: false positive on raw walljump. Check if they were in walltech beforehand?
            curr_teching = is_teching(player_state)
            was_teching = is_teching(prev_player_state)

            # Close out active techs if we were teching, and save some processing power if we weren't
            if not curr_teching:
                if was_teching and self.tech_state.tech is not None:
                    if is_damaged(player_state):
                        self.tech_state.tech.was_punished = True
                    player.stats.techs.append(self.tech_state.tech)
                    self.tech_state.tech = None
                    self.tech_state.last_state = -1
                continue

            opponent_frame = opponent.frames[i]

            # If we are, create a tech event, and start filling out fields based on the info we have
            if not was_teching:
                self.tech_state.tech = TechData()
                self.tech_state.tech.frame_index = i
                if opponent_frame.post.most_recent_hit:
                    self.tech_state.tech.last_hit_by = try_enum(Attack, opponent_frame.post.most_recent_hit).name
                self.tech_state.tech.position = player_frame.post.position
                self.tech_state.tech.is_on_platform = (
                    player_frame.post.position.y > 5
                )  # Arbitrary value, i'll have to fact check this

            if player_state == self.tech_state.last_state:
                continue

            self.tech_state.last_state = player_state

            tech_type = get_tech_type(player_state, player_frame.post.facing_direction)

            match tech_type:
                case TechType.MISSED_TECH:
                    self.tech_state.tech.is_missed_tech = True
                    self.tech_state.tech.jab_reset = False

                case TechType.JAB_RESET:
                    self.tech_state.tech.jab_reset = True

                case TechType.TECH_LEFT | TechType.MISSED_TECH_ROLL_LEFT:
                    opnt_relative_position = opponent_frame.post.position.x - player_frame.post.position.x
                    if player_frame.post.facing_direction > 0:
                        self.tech_state.tech.towards_center = True
                    else:
                        self.tech_state.tech.towards_center = False
                    if opnt_relative_position > 0:
                        self.tech_state.tech.towards_opponent = True
                    else:
                        self.tech_state.tech.towards_opponent = False
                case TechType.TECH_RIGHT | TechType.MISSED_TECH_ROLL_RIGHT:
                    opnt_relative_position = opponent_frame.post.position.x - player_frame.post.position.x
                    if player_frame.post.facing_direction > 0:
                        self.tech_state.tech.towards_center = False
                    else:
                        self.tech_state.tech.towards_center = True
                    if opnt_relative_position > 0:
                        self.tech_state.tech.towards_opponent = False
                    else:
                        self.tech_state.tech.towards_opponent = True

                case _:  # Tech in place, getup attack
                    pass

            self.tech_state.tech.tech_type = tech_type.name
        return player.stats.techs

    def take_hit_compute(
        self,
        connect_code: str | None = None,
        player: Player | None = None,
        opponent: Player | None = None,
    ) -> TakeHits:
        if connect_code is None and player is None:
            raise ValueError("Compute functions require either a connect_code or player argument")

        if connect_code is not None:
            player = self.get_player(connect_code)
            opponent = self.get_opponent(connect_code)

        if self.replay_version < "2.0.0":
            warnings.warn(
                f"""No computation: take_hit_compute() requires at least replay version 2.0.0,
                          got replay version: {self.replay_version}""",
                RuntimeWarning,
            )
            return player.stats.take_hits
        if self.replay_version < "3.5.0":
            warnings.warn(
                f"""Partial computation: take_hit_compute() DI and knockback calculations
                require at least replay version 3.5.0, got replay version {self.replay_version}.""",
                RuntimeWarning,
            )

        for i, player_frame in enumerate(player.frames):
            prev_player_frame = player.frames[i - 1]
            opponent_frame = opponent.frames[i]

            # right now i don't care about shield SDI/ASDI but i may change this down the line
            # it requires slightly different logic
            in_hitlag = is_in_hitlag(player_frame.post.flags) and not is_shielding(prev_player_frame.post.state)
            was_in_hitlag = is_in_hitlag(prev_player_frame.post.flags) and not is_shielding(
                prev_player_frame.post.state
            )

            if not in_hitlag:
                if was_in_hitlag and self.take_hit_state is not None:
                    self.take_hit_state.end_pos = prev_player_frame.post.position
                    self.take_hit_state.last_hit_by = try_enum(Attack, opponent_frame.post.most_recent_hit)

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

                    self.take_hit_state.di_stick_pos = effective_stick

                    if self.replay_version >= "3.5.0":
                        if self.take_hit_state.kb_velocity.x != 0.0 and self.take_hit_state.kb_velocity.y != 0.0:
                            self.take_hit_state.final_kb_angle = get_post_di_angle(
                                effective_stick, self.take_hit_state.kb_velocity
                            )

                            di_efficacy = (
                                abs(self.take_hit_state.final_kb_angle - self.take_hit_state.kb_angle) / 18
                            ) * 100
                            # modulo magic to truncate to 2 decimal place
                            # see: https://stackoverflow.com/a/49183117
                            self.take_hit_state.di_efficacy = di_efficacy - di_efficacy % 1e-2
                        else:
                            self.take_hit_state.final_kb_angle = self.take_hit_state.kb_angle

                        self.take_hit_state.final_kb_velocity = get_post_di_velocity(
                            self.take_hit_state.final_kb_angle,
                            self.take_hit_state.kb_velocity,
                        )

                    cstick = get_joystick_region(player_frame.pre.cstick)
                    if cstick != JoystickRegion.DEAD_ZONE:
                        self.take_hit_state.asdi = cstick
                    else:
                        self.take_hit_state.asdi = get_joystick_region(player_frame.pre.joystick)

                    self.take_hit_state.find_valid_sdi()

                    player.stats.take_hits.append(self.take_hit_state)
                    self.take_hit_state = None
                continue

            if not was_in_hitlag and just_took_damage(player_frame.post.percent, prev_player_frame.post.percent):
                self.take_hit_state = TakeHitData()
                self.take_hit_state.frame_index = i
                self.take_hit_state.state_before_hit = player.frames[i - 1].post.state
                self.take_hit_state.start_pos = player_frame.post.position
                self.take_hit_state.percent = player_frame.post.percent
                self.take_hit_state.grounded = not player_frame.post.is_airborne
                if self.replay_version >= "3.5.0":
                    self.take_hit_state.kb_velocity = player_frame.post.knockback_speed
                    self.take_hit_state.kb_angle = degrees(get_angle(player_frame.post.knockback_speed))
                else:
                    self.take_hit_state.kb_velocity = None
                    self.take_hit_state.kb_angle = None

                if ActionRange.SQUAT_START <= prev_player_frame.post.state < ActionRange.SQUAT_END:
                    self.take_hit_state.crouch_cancel = True
                else:
                    self.take_hit_state.crouch_cancel = False
            # TODO this failed during all_stats(), DF had 1872 entries.
            # file:'Modern Replays\\FATK#202 (Yoshi) vs NUT#356 (Falco) on YS - 12-21-22 11.43pm .slp'
            # possibly fixed by changing <= ActionRange.AERIAL_ATTACK_END to <= ActionRange.SQUAT_END

            if self.take_hit_state is not None:
                self.take_hit_state.stick_regions_during_hitlag.append(get_joystick_region(player_frame.pre.joystick))
                self.take_hit_state.hitlag_frames += 1

        return player.stats.take_hits

    def l_cancel_compute(
        self,
        connect_code: str | None = None,
        player: Player | None = None,
    ) -> LCancels:
        if connect_code is None and player is None:
            raise ValueError("Compute functions require either a connect_code or player argument")

        if connect_code is not None:
            player = self.get_player(connect_code)

        if self.replay_version < "2.0.0":
            warnings.warn(
                f"""No computation: l_cancel_compute() requires at least replay version 2.0.0,
                          got replay version: {self.replay_version}""",
                RuntimeWarning,
            )
            return player.stats.l_cancels

        for i, player_frame in enumerate(player.frames):
            l_cancel = player_frame.post.l_cancel

            if l_cancel == LCancel.NOT_APPLICABLE:
                continue

            # Check for l/r press either 15 frames prior, or j + hitlag frames prior
            trigger_input_frame: int | None = None
            in_hitlag = False
            j = 0

            while j < 15 and not in_hitlag:
                if i - j >= 0:
                    if is_in_hitlag(player.frames[i - j].post.flags):
                        in_hitlag = True

                    if just_input_l_cancel(player.frames[i - j], player.frames[i - j - 1]):
                        trigger_input_frame = -j
                        break

                j += 1

            if trigger_input_frame is not None:
                for j in range(5):
                    if i + j < len(player.frames):
                        if just_input_l_cancel(player.frames[i + j], player.frames[i + j - 1]):
                            trigger_input_frame = j

            player.stats.l_cancels.append(
                LCancelData(
                    frame_index=i,
                    move=player.frames[i - 1].post.state,
                    l_cancel=True if l_cancel == 1 else False,
                    trigger_input_frame=trigger_input_frame,
                    position=get_ground(self.replay.start.stage, player_frame.post.last_ground_id),
                )
            )

        player.stats.l_cancels._percentage()
        return player.stats.l_cancels

    def recovery_compute(
        self,
        connect_code: str | None = None,
        player: Player | None = None,
        opponent: Player | None = None,
    ) -> TakeHits:
        if connect_code is None and player is None:
            raise ValueError("Compute functions require either a connect_code or player argument")

        if connect_code is not None:
            player = self.get_player(connect_code)
            opponent = self.get_opponent(connect_code)

        stage = self.replay.start.stage

        for i, player_frame in enumerate(player.frames):
            opponent_frame = opponent.frames[i]

            player_state = player_frame.post.state
            player_position = player_frame.post.position
            player_just_offstage = is_offstage(player_position, stage) and not is_offstage(
                player.frames[i - 1].post.position, stage
            )
            player_in_hitstun = is_in_hitstun(player_frame.post.flags)

            if self.recovery_state is None and player_just_offstage and player_in_hitstun:
                self.recovery_state = RecoveryData(frame_index=i, last_hit_by=opponent_frame.post.position)

            if self.recovery_state is None:
                continue

            # record furthest position outward/hitstun end/knockback end/distance from ledge?
            # check resources - double jump, find a way to track marth/luigi side B juice, walljump
            # record every move used (with character enum), special attention to resource useage
            # look for end (death, land on stage/platform, grab ledge)
            # attempt to discern SD's (never stops moving towards ledge,
            # special move direction towards blast zone + dist to ledge, etc.)
            # retroactively assign meaning to previous actions (i.e. most recent action was "recovery move")
            # maybe record opponent position?
            # outcome, "reason": Death, ledge, stage, hit offstage, hit onstage | ledge hog, SD, pineapple, too far,

            player_is_dead = is_dying(player_state)
            player_is_ledge = is_ledge_action(player_state)
            player_did_land = (
                not player_frame.post.is_airborne
                and get_ground(stage, player_frame.post.last_ground_id) != Yoshis.RANDALL
            )

    def shield_drop_compute(
        self,
        connect_code: str | None = None,
        player: Player | None = None,
        opponent: Player | None = None,
    ) -> TakeHits:
        if connect_code is None and player is None:
            raise ValueError("Compute functions require either a connect_code or player argument")

        if connect_code is not None:
            player = self.get_player(connect_code)
            opponent = self.get_opponent(connect_code)

        stage = self.replay.start.stage

        for i, player_frame in enumerate(player.frames):
            player_state = player_frame.post.state
            prev_player_frame = player.frames[i - 1]
            prev_player_state = prev_player_frame.post.state

            # can't use is_shielding() because you can't shielddrop during the guard release animation,
            # so it would false positive on drop shield -> first frame drop through platform
            player_was_shielding = (
                prev_player_state == ActionState.GUARD
                or prev_player_state == ActionState.GUARD_ON
                or prev_player_state == ActionState.GUARD_REFLECT
                or prev_player_state == ActionState.GUARD_DAMAGE
            )
            if player_state == ActionState.PASS and player_was_shielding:
                player.stats.shield_drops.append(
                    ShieldDropData(
                        frame_index=i,
                        position=get_ground(stage, player_frame.post.last_ground_id),
                    )
                )
                # TODO check for shieldstun and maybe followup option

        return player.stats.shield_drops

    # def track_

    # def ledge_action_compute():


# ---------------------------------------------------------------------------- #
#                                      eef                                     #
# ---------------------------------------------------------------------------- #


def _eef(file, connect_code):
    try:
        return StatsComputer(file)._compute(connect_code).to_polars()
    except:
        return None


def get_stats(directory, connect_code):
    ind = 1
    dfs = None
    files = []
    with os.scandir(directory) as dir:
        for entry in dir:
            files.append(os.path.join(directory, entry.name))
        with concurrent.futures.ProcessPoolExecutor() as executor_1:
            futures = {executor_1.submit(_eef, file, connect_code) for file in files}

            for df in concurrent.futures.as_completed(futures):
                if df.result() is not None:
                    if dfs is None:
                        dfs = df.result()
                    else:
                        dfs = pl.concat([dfs, df.result()], how="vertical")
                        print("concatting")

    dfs.write_parquet("wavedashdata_temp2.parquet")
    print("file written")

    return dfs
