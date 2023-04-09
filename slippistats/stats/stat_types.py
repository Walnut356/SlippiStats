from abc import ABC
from collections import UserList
from dataclasses import dataclass, field
from math import degrees, dist

import polars as pl
from tzlocal import get_localzone_name

from slippistats.util import IntEnum, try_enum

from ..enums.attack import Attack
from ..enums.state import ActionState
from ..event import Position, Velocity
from .common import JoystickRegion, TechType, get_angle


# TODO abstract base class:
class Stat(ABC):
    pass


# TODO add stocks_remaining

# --------------------------------- Wavedash --------------------------------- #


@dataclass
class WavedashData(Stat):
    frame_index: int
    stocks_remaining: int | None
    angle: float | None  # in degrees
    direction: str | None
    r_frame: int  # which airborne frame was the airdodge input on?
    airdodge_frames: int
    waveland: bool

    def __init__(
        self,
        frame_index: int,
        stocks_remaining: int = None,
        r_frame: int = 0,
        stick: Position | None = None,
        airdodge_frames: int = 0,
    ):
        self.frame_index = frame_index
        self.stocks_remaining = stocks_remaining
        if stick:
            # atan2 converts coordinates to degrees without losing information
            self.angle = degrees(get_angle(stick))
            # then we need to normalize the values to degrees-below-horizontal and assign a direction
            if self.angle < 270 and self.angle > 180:
                self.angle -= 180
                self.direction = "LEFT"
            if self.angle > 270 and self.angle < 360:
                self.angle -= 270
                self.direction = "RIGHT"
            if self.angle == 180:
                self.angle = 0
                self.direction = "LEFT"
            if self.angle == 0:
                self.direction = "RIGHT"
            if self.angle == 270:
                self.angle = 90
                self.direction = "DOWN"

        else:
            self.angle = None
            self.direction = None
        self.r_frame = r_frame
        self.airdodge_frames = airdodge_frames
        self.waveland = True

    def total_startup(self) -> int:
        return self.r_frame + self.airdodge_frames


# ----------------------------------- Dash ----------------------------------- #


@dataclass
class DashData(Stat):
    frame_index: int = -1
    stocks_remaining: int | None = None
    start_pos: float = 0.0
    end_pos: float = 0.0
    direction: str | None = None
    is_dashdance: bool = False

    def distance(self) -> float:
        return abs(self.end_pos - self.start_pos)


# ----------------------------------- Tech ----------------------------------- #


@dataclass
class TechData(Stat):
    frame_index: int = -1
    stocks_remaining: int | None = None
    tech_type: TechType | None = None
    was_punished: bool = False
    direction: str = None
    position: Position = field(default_factory=Position)
    ground_id: IntEnum | None = None
    is_on_platform: bool = False
    is_missed_tech: bool = False
    towards_center: bool | None = None
    towards_opponent: bool | None = None
    jab_reset: bool | None = None
    last_hit_by: str = field(default_factory=str)


@dataclass
class TechState:
    tech: TechData
    last_state: ActionState | int | None

    def __init__(self):
        self.tech = TechData()
        self.last_state = -1


# --------------------------------- Take hit --------------------------------- #


@dataclass
class TakeHitData(Stat):
    frame_index: int
    last_hit_by: Attack | None
    state_before_hit: IntEnum | None
    grounded: bool | None
    crouch_cancel: bool | None
    hitlag_frames: int | None
    stick_regions_during_hitlag: list[JoystickRegion]
    sdi_inputs: list[JoystickRegion]
    asdi: JoystickRegion | None
    di_stick_pos: Position | None
    percent: float | None
    kb_velocity: Velocity | None
    kb_angle: float | None
    final_kb_velocity: Velocity | None
    final_kb_angle: float | None
    start_pos: Position | None
    end_pos: Position | None
    di_efficacy: float | None

    def __init__(self):
        self.frame_index = -1
        self.grounded = None
        self.percent = None
        self.last_hit_by = None
        self.state_before_hit = None
        self.crouch_cancel = None
        self.hitlag_frames = 0
        self.stick_regions_during_hitlag = []
        self.sdi_inputs = []
        self.asdi = None
        self.start_pos = None
        self.end_pos = None
        self.kb_angle = None
        self.di_stick_pos = None
        self.di_efficacy = None
        self.final_kb_angle = None
        self.kb_velocity = None
        self.final_kb_velocity = None

    def find_valid_sdi(self):
        for i, stick_region in enumerate(self.stick_regions_during_hitlag):
            # Obviously the first stick position and any deadzone input cannot be SDI inputs so we skip those
            if i == 0 or stick_region == JoystickRegion.DEAD_ZONE:
                continue

            prev_stick_region = self.stick_regions_during_hitlag[i - 1]

            # If we haven't changed regions, it can't be an SDI input
            if stick_region == prev_stick_region:
                continue

            # Any time we leave the deadzone though, the input counts
            if prev_stick_region == JoystickRegion.DEAD_ZONE:
                self.sdi_inputs.append(stick_region)
                continue

            # Joystick region cardinals are stored as odd numbers, diagonals are even
            # Cardinal -> Any region will result in a second SDI input
            if prev_stick_region % 2 == 0:
                self.sdi_inputs.append(stick_region)
                continue

            # Diagonal -> cardinal will NOT result in a second SDI input
            # unless the cardinal borders the opposite quadrant
            if prev_stick_region % 2 == 1:
                if stick_region % 2 == 1:
                    self.sdi_inputs.append(stick_region)
                # HACK there's probably less stupid way to do this
                # I checked and for any valid diagonal->cadinal (DR->L, UL->D, etc.)
                # the absolute value of the difference between the 2 is always 3 or 5 so this literally works
                # It should almost never happen though since you'd need to move 3 zones away inbetween frames
                elif 3 <= abs(stick_region - prev_stick_region) < 7:
                    self.sdi_inputs.append(stick_region)
                continue

    def change_in_position(self) -> tuple:
        return self.start_pos - self.end_pos

    def distance(self) -> float:
        return dist(self.end_pos, self.start_pos)


# --------------------------------- L cancel --------------------------------- #


@dataclass
class LCancelData(Stat):
    frame_index: int
    l_cancel: bool
    move: Attack
    position: IntEnum
    trigger_input_frame: int
    during_hitlag: bool

    def __init__(self, frame_index, l_cancel, move, position, trigger_input_frame, during_hitlag):
        self.frame_index = frame_index
        self.l_cancel = l_cancel
        self.trigger_input_frame = trigger_input_frame
        self.during_hitlag = during_hitlag
        match move:
            case ActionState.ATTACK_AIR_N:
                self.move = Attack.NAIR
            case ActionState.ATTACK_AIR_F:
                self.move = Attack.FAIR
            case ActionState.ATTACK_AIR_B:
                self.move = Attack.BAIR
            case ActionState.ATTACK_AIR_HI:
                self.move = Attack.UAIR
            case ActionState.ATTACK_AIR_LW:
                self.move = Attack.DAIR
            case _:
                self.move = "UNKNOWN"
        self.position = position


# ------------------------------- Recovery Data ------------------------------ #


@dataclass
class RecoveryData(Stat):
    frame_index: int


# ------------------------------- Shield Drop Data ------------------------------ #


@dataclass
class ShieldDropData(Stat):
    frame_index: int
    position: IntEnum | int


# --------------------------------- Wrappers --------------------------------- #

# TODO ABC, protocol, mixin? for append, to_polars, etc.


class StatList(ABC, UserList):
    data_header: dict
    data: list[Stat]

    def append(self, item):
        pass

    def to_polars(self) -> pl.DataFrame:
        pass


class Wavedashes(UserList):
    """Iterable wrapper for lists of Wavedash data"""

    data_header: dict
    data: list[WavedashData]

    def __init__(self, data_header):
        self.data_header = data_header
        self.data = []
        self.schema = {
            "date_time": pl.Datetime(time_zone=get_localzone_name()),
            "slippi_version": pl.Utf8,
            "match_id": pl.Utf8,
            "match_type": pl.Utf8,
            "game_number": pl.Int64,
            "stage": pl.Utf8,
            "duration": pl.Duration(time_unit="ms"),
            "result": pl.Utf8,
            "port": pl.Utf8,
            "connect_code": pl.Utf8,
            "character": pl.Utf8,
            "opnt_character": pl.Utf8,
            "frame_index": pl.Int64,
            "angle": pl.Float64,
            "direction": pl.Utf8,
            "r_frame": pl.Int64,
            "airdodge_frames": pl.Int64,
            "waveland": pl.Boolean,
        }

    def append(self, item):
        if isinstance(item, WavedashData):
            UserList.append(self, item)
        else:
            raise TypeError(f"Incorrect stat type: {type(item)}, expected WavedashData")

    def to_polars(self) -> pl.DataFrame:
        if len(self.data) > 0:
            return pl.DataFrame(
                [self.data_header | vars(stat) for stat in self.data if stat is not None],
                schema=self.schema,
            )
        else:
            return pl.DataFrame([], schema=self.schema)


class Dashes(UserList):
    """Iterable wrapper for lists of Dash data"""

    data_header: dict
    data: list[DashData]

    def __init__(self, data_header):
        self.data_header = data_header
        self.data = []
        self.schema = {
            "date_time": pl.Datetime(time_zone=get_localzone_name()),
            "slippi_version": pl.Utf8,
            "match_id": pl.Utf8,
            "match_type": pl.Utf8,
            "game_number": pl.Int64,
            "stage": pl.Utf8,
            "duration": pl.Duration(time_unit="us"),
            "result": pl.Utf8,
            "port": pl.Utf8,
            "connect_code": pl.Utf8,
            "character": pl.Utf8,
            "opnt_character": pl.Utf8,
            "frame_index": pl.Int64,
            "stocks_remaining": pl.Int64,
            "start_pos": pl.Float64,
            "end_pos": pl.Float64,
            "direction": pl.Utf8,
            "is_dashdance": pl.Boolean,
        }

    def append(self, item):
        if isinstance(item, DashData):
            UserList.append(self, item)
        else:
            raise TypeError(f"Incorrect stat type: {type(item)}, expected DashData")

    def to_polars(self) -> pl.DataFrame:
        # if len(self.data) > 0:
        return pl.DataFrame([self.data_header | vars(stat) for stat in self.data if stat is not None])

    # else:
    #     return pl.DataFrame([], schema=self.schema)


class Techs(UserList):
    """Iterable wrapper for lists of Tech data"""

    data_header: dict
    data: list[TechData]

    def __init__(self, data_header):
        self.data_header = data_header
        self.data = []
        self.schema = {
            "frame_index": pl.Int64,
            "stocks_remaining": pl.Int64,
            "tech_type": pl.Utf8,
            "was_punished": pl.Boolean,
            "direction": pl.Boolean,
            "position": pl.List(pl.Float64),
            "ground_id": pl.Int64,
            "is_on_platform": pl.Boolean,
            "is_missed_tech": pl.Boolean,
            "towards_center": pl.Boolean,
            "towards_opponent": pl.Boolean,
            "jab_reset": pl.Boolean,
            "last_hit_by": pl.Utf8,
        }

    def append(self, item):
        if isinstance(item, TechData):
            UserList.append(self, item)
        else:
            raise TypeError(f"Incorrect stat type: {type(item)}, expected TechData")

    def to_polars(self) -> pl.DataFrame:
        if len(self.data) == 0:
            pass
            # df = pl.DataFrame([], self.schema)
        else:
            rows = []

            # polars doesn't like the formats of some of our numbers, so we have to manually conver them to lists
            for stat in self.data:
                stat_dict = vars(stat).copy()
                stat_dict["position"] = list(stat.position)
                rows.append(stat_dict)

            df = pl.DataFrame(rows)
            return df


class TakeHits(UserList):
    """Iterable wrapper rapper for lists of Take Hit data"""

    data_header: dict
    data: list[TakeHitData]
    schema: dict

    def __init__(self, data_header):
        self.data_header = data_header
        self.data = []
        self.schema = {
            "date_time": pl.Datetime(time_zone=get_localzone_name()),
            "slippi_version": pl.Utf8,
            "match_id": pl.Utf8,
            "match_type": pl.Utf8,
            "game_number": pl.Int64,
            "stage": pl.Utf8,
            "duration": pl.Duration(time_unit="ms"),
            "result": pl.Utf8,
            "port": pl.Utf8,
            "connect_code": pl.Utf8,
            "character": pl.Utf8,
            "opnt_character": pl.Utf8,
            "frame_index": pl.Int64,
            "grounded": pl.Boolean,
            "percent": pl.Float64,
            "last_hit_by": pl.Utf8,
            "state_before_hit": pl.Utf8,
            "crouch_cancel": pl.Boolean,
            "hitlag_frames": pl.Int64,
            "stick_regions_during_hitlag": pl.List(pl.Utf8),
            "sdi_inputs": pl.List(pl.Utf8),
            "asdi": pl.Utf8,
            "start_pos": pl.List(pl.Float64),
            "end_pos": pl.List(pl.Float64),
            "kb_angle": pl.Float64,
            "di_stick_pos": pl.List(pl.Float64),
            "di_efficacy": pl.Float64,
            "final_kb_angle": pl.Float64,
            "kb_velocity": pl.List(pl.Float64),
            "final_kb_velocity": pl.List(pl.Float64),
        }

    def append(self, item):
        if isinstance(item, TakeHitData):
            UserList.append(self, item)
        else:
            raise TypeError(f"Incorrect stat type: {type(item)}, expected TakeHitData")

    def to_polars(self) -> pl.DataFrame:
        if len(self.data) == 0:
            df = pl.DataFrame([], self.schema)
        else:
            rows = []

            # polars doesn't like the formats of some of our numbers, so we have to manually conver them to lists
            for stat in self.data:
                stat_dict = vars(stat).copy()
                try:
                    lhb = try_enum(Attack, stat.last_hit_by).name
                except AttributeError:
                    lhb = None
                try:
                    sbh = stat.state_before_hit.name
                except AttributeError:
                    sbh = str(stat.state_before_hit)

                stat_dict["last_hit_by"] = lhb or "UNKNOWN"
                stat_dict["state_before_hit"] = sbh or "UNKNOWN"
                stat_dict["sdi_inputs"] = [region.name for region in stat.sdi_inputs] or None
                stat_dict["asdi"] = stat.asdi.name
                stat_dict["stick_regions_during_hitlag"] = [region.name for region in stat.stick_regions_during_hitlag]
                stat_dict["kb_velocity"] = list(stat.kb_velocity)
                stat_dict["final_kb_velocity"] = list(stat.final_kb_velocity)
                stat_dict["start_pos"] = list(stat.start_pos)
                stat_dict["end_pos"] = list(stat.end_pos)
                if stat.di_stick_pos is not None:
                    stat_dict["di_stick_pos"] = list(stat.di_stick_pos)
                else:
                    stat_dict["di_stick_pos"] = None
                rows.append(self.data_header | stat_dict)

            df = pl.DataFrame(rows, schema=self.schema)
        return df


class LCancels(UserList):
    """Iterable wrapper for lists of l-cancel data"""

    data_header: dict
    percent: float | None
    data: list[LCancelData]

    def __init__(self, data_header):
        self.percent = None
        self.data = []
        self.data_header = data_header

    def append(self, item):
        if isinstance(item, LCancelData):
            UserList.append(self, item)
        else:
            raise ValueError(f"Incorrect stat type: {type(item)}, expected LCancelData")

    def _percentage(self):
        success = 0
        for item in self.data:
            if item.l_cancel:
                success += 1
        if len(self.data) > 0:
            self.percent = (success / len(self.data)) * 100

    def to_polars(self):
        data = []

        # polars doesn't like the formats of some of our numbers, so we have to manually conver them to lists
        for stat in self.data:
            # we have to make a copy so we don't bork the data with our changes
            stat_dict = vars(stat).copy()
            try:
                stat_dict["position"] = stat.position.name
            except AttributeError:
                stat_dict["position"] = "UNKNOWN"
            stat_dict["move"] = stat.move.name

            data.append(self.data_header | stat_dict)

        return pl.DataFrame(data)


class ShieldDrops(UserList):
    """Iterable wrapper for lists of Dash data"""

    data_header: dict
    data: list[ShieldDropData]

    def __init__(self, data_header):
        self.data_header = data_header
        self.data = []

    def append(self, item):
        if isinstance(item, ShieldDropData):
            UserList.append(self, item)
        else:
            raise ValueError(f"Incorrect stat type: {type(item)}, expected ShieldDropData")

    def to_polars(self):
        data = []
        for stat in self.data:
            stat_dict = stat.__dict__.copy()
            try:
                stat_dict["position"] = stat.position.name
            except AttributeError:
                stat_dict["position"] = "UNKNOWN"
            data.append(self.data_header | stat_dict)

        return pl.DataFrame(data)


@dataclass
class Data:
    wavedashes: Wavedashes
    dashes: Dashes
    techs: Techs
    take_hits: TakeHits
    l_cancels: LCancels

    shield_drops: ShieldDrops

    def __init__(self, data_header):
        self.wavedashes = Wavedashes(data_header)
        self.dashes = Dashes(data_header)
        self.techs = Techs(data_header)
        self.take_hits = TakeHits(data_header)
        self.l_cancels = LCancels(data_header)

        self.shield_drops = ShieldDrops(data_header)
