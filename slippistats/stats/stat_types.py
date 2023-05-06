from abc import ABC, abstractmethod
from collections import UserList
from dataclasses import dataclass, field
from math import degrees, dist
from pathlib import Path

import polars as pl
from tzlocal import get_localzone_name
from ..enums.stage import GroundID

from slippistats.util import IntEnum, try_enum

from ..enums.attack import Attack
from ..enums.state import ActionState, Direction
from ..event import Position, Velocity
from .common import JoystickRegion, TechType, get_angle


# TODO abstract base class:
class Stat(ABC):
    pass


# --------------------------------- Wavedash --------------------------------- #


@dataclass()
class WavedashData(Stat):
    """Contains all data for a single Wavedash Event.

    Attributes:
        frame_index : int
            The frame the event began on (0-indexed)
        stocks_remaining : int
            Stocks remaining at the start of the event
        angle : float
            Wavedash angle in degrees below horizontal
        direction : Direction
            Direction of the wavedash, can be 'LEFT', 'RIGHT', or 'DOWN'
        trigger_frame : int
            Number of frames between the last kneebend frame and the trigger press. Upper bound of 5
        stick : Position
            X,Y coordinate position where the event occurred
        airdodge_frames : int
            Number of airdodge frames between the trigger press and landing. Upper bound of 5

    Methods:
        total_startup() -> int
            Returns the total number of frames between the last kneebend frame and the first land_fall_special frame
    """

    frame_index: int
    """The frame the event began on (0-indexed)"""
    stocks_remaining: int | None
    angle: float | None
    """Wavedash angle in degrees below horizontal"""
    direction: Direction | None
    """Direction of the wavedash, can be LEFT, RIGHT, or DOWN"""
    trigger_frame: int
    """If the event is not a waveland, the number of frames between the last jumpsquat frame and the trigger press"""
    # TODO
    airdodge_frames: int
    """The number of frames the character was in airdodge between the trigger press and landing"""
    waveland: bool
    """True if there were no jumpsquat frames within a few frames of the trigger input"""

    def __init__(
        self,
        frame_index: int,
        stocks_remaining: int = None,
        trigger_frame: int = 0,
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
                self.direction = Direction.LEFT
            elif self.angle > 270 and self.angle < 360:
                self.angle -= 270
                self.direction = Direction.RIGHT
            elif self.angle == 180:
                self.angle = 0
                self.direction = Direction.LEFT
            elif self.angle == 0:
                self.direction = Direction.RIGHT
            elif self.angle == 270:
                self.angle = 90
                self.direction = Direction.DOWN
            elif self.angle > 0 and self.angle < 90:
                self.angle *= -1
                self.direction = Direction.RIGHT
            elif self.angle > 90 and self.angle < 180:
                self.angle *= -1
                self.direction = Direction.LEFT
            elif self.angle == 90:
                self.angle *= -1
                self.direction = Direction.DOWN
            else:
                self.angle = None
                self.direction = None
                raise ValueError(
                    f"""unexpected wavedash angle. Frame = {frame_index},
                    Stickpos = {stick}, angle = {degrees(get_angle(stick))}"""
                )
        else:
            self.angle = None
            self.direction = None
        self.trigger_frame = trigger_frame
        self.airdodge_frames = airdodge_frames
        self.waveland = True

    def total_startup(self) -> int:
        """Returns the total number of frames between the last kneebend frame and the first land_fall_special frame"""
        return self.trigger_frame + self.airdodge_frames


# ----------------------------------- Dash ----------------------------------- #


@dataclass()
class DashData(Stat):
    """Contains all data for a single Dash Event.

    Attributes:
        frame_index : int
            The frame the event began on (0-indexed)
        stocks_remaining : int
            Stocks remaining at the start of the event
        start_position : float
            X coordinate on the first frame of the event
        end_position : float
            X coordinate on the last frame of the event
        direction : Direction
            Direction of the dash, can be LEFT or RIGHT
        is_dashdancing : bool
            True if this was part of a dashdance (includes the first dash)
    """

    frame_index: int = -1
    """The frame the event began on (0-indexed)"""
    stocks_remaining: int | None = None
    start_pos: float = 0.0
    end_pos: float = 0.0
    direction: Direction | None = None
    is_dashdance: bool = False
    """Tue if this dash was part of a dashdance (includes the first dash)"""

    def distance(self) -> float:
        return abs(self.end_pos - self.start_pos)


# ----------------------------------- Tech ----------------------------------- #


@dataclass()
class TechData(Stat):
    """Contains all data for a single Tech Event.

    Attributes:
        frame_index : int
            The frame the event began on (0-indexed)
        stocks_remaining : int
            Stocks remaining at the start of the event
        tech_type : TechType
            IntEnum of the tech type and tech direction
        was_punished : bool
            True if player was hit at any point during the Tech animation
        position : Position
            X,Y coordinates on the first frame of the Tech Event
        ground_id : GroundID
            Player's last_ground_id on the first frame of the Tech Event
        is_on_platform : bool
            True if player is on any ground other than the main stage (includes Randall)
        is_missed_tech : bool
            True if player enters any missed tech animation during the Tech Event
        towards_center : bool
            True if player tech rolled towards Position(0,0)
        towards_opponent : bool
            True if player initiated a roll that travelled in the direction of the opponent at the time of the input
        jab_reset : bool
            True if the player entered either of the down_damage action states during the Tech Event
        last_hit_by : Attack
            IntEnum of the attack that the player was most recently hit by
    """

    frame_index: int = -1
    """The frame the event began on (0-indexed)"""
    stocks_remaining: int | None = None
    tech_type: TechType | None = None
    was_punished: bool = False
    """True if player was hit at any point during the Tech animation"""
    position: Position = field(default_factory=Position)
    """X,Y coordinates on the first frame of the Tech Event"""
    ground_id: GroundID | None = None
    is_on_platform: bool = False
    is_missed_tech: bool = False
    towards_center: bool | None = None
    """True if player tech rolled towards Position(0,0)"""
    towards_opponent: bool | None = None
    """True if player initiated a roll that travelled in the direction of the opponent at the time of the input"""
    jab_reset: bool | None = None
    """True if the player entered either of the down_damage action states during the Tech Event"""
    last_hit_by: Attack | None = None
    """IntEnum of the attack that the player was most recently hit by"""


# --------------------------------- Take hit --------------------------------- #


@dataclass()
class TakeHitData(Stat):
    """
    Contains all data for a single Take Hit Event.

    Attributes:
        frame_index : int
            The frame the event began on (0-indexed)
        last_hit_by : Attack
            Likely the attack that caused the take hit event, but there are some exceptions
        state_before_hit : ActionState
            Character's state the frame before the Take Hit Event
        grounded : bool
            True if the character was grounded upon entering hitlag
        crouch_cancel : bool
            True if the character was in action state SQUAT or SQUAT_WAIT the frame before the hit
        hitlag_frames : int
            The total number of hitstun frames
        stick_regions_during_hitlag : list[JoystickRegion]
            A list of the character's general stick position on each frame of hitlag
        sdi_inputs : list[JoystickRegion]
            A list of all valid SDI inputs that occurred during hitlag
        asdi : JoystickRegion
            Character's general stick position on the last frame of hitlag, used for ASDI calculation. If the c-stick is
            region is not DEAD_ZONE, the c-stick position is used. Otherwise, the joystick position is used.
        di_stick_pos : Position
            The coordinate position of the joystick on the last frame of hitlag, which is used for DI calculations
        percent : float
            The character's percent after the damage from the hit is applied
        kb_velocity : Velocity
            X,Y knockback velocity of the character upon entering hitlag, before DI is applied
        kb_angle : float
            Angle of knockback, in degrees, before DI is applied
        final_kb_velocity : Velocity
            X,Y knockback velocity of the character upon exiting hitlag, after DI is applied
        final_kb_angle : float
            Angle of knockback, in degrees, after DI is applied
        start_pos : Position
            Character's position upon entering hitlag, before any SDI or ASDI inputs.
        end_pos : Position
            Character's position upon exiting hitlag, after any SDI or ASDI inputs.
        di_efficacy : float
            Percentage. 0% = No change in KB angle, 100% = Maximum possible change in KB angle.

    Methods:
        distance() -> float:
            Returns the math.dist() between start_pos and end_pos
        change_in_position() -> Position:
            Returns a Position value representing the change in X and change in Y from start_pos to end_pos
    """

    frame_index: int = -1
    """The frame the event began on (0-indexed)"""
    stocks_remaining: int | None = None
    last_hit_by: Attack | None = None
    """Likely the attack that caused the take hit event, but there are some exceptions"""
    state_before_hit: ActionState | None = None
    """Character's state the frame before the Take Hit Event"""
    grounded: bool | None = None
    """True if the character was grounded upon entering hitlag"""
    crouch_cancel: bool | None = None
    """True if the character was in action state SQUAT or SQUAT_WAIT the frame before the hit"""
    hitlag_frames: int | None = 0
    """The total number of hitlag frames"""
    stick_regions_during_hitlag: list[JoystickRegion] = field(default_factory=list)
    """A list of the character's general stick position on each frame of hitlag"""
    sdi_inputs: list[JoystickRegion] = field(default_factory=list)
    """A list of all valid SDI inputs that occurred during hitlag"""
    asdi: JoystickRegion | None = None
    """Character's general stick position on the last frame of hitlag, used for ASDI calculation. If the c-stick is
        region is not DEAD_ZONE, the c-stick position is used. Otherwise, the joystick position is used."""
    di_stick_pos: Position | None = None
    """The coordinate position of the joystick on the last frame of hitlag, which is used for DI calculations"""
    percent: float | None = None
    """The character's percent after the damage from the hit is applied"""
    kb_velocity: Velocity | None = None
    """X,Y knockback velocity of the character upon entering hitlag, before DI is applied"""
    kb_angle: float | None = None
    """Angle of knockback, in degrees, before DI is applied"""
    final_kb_velocity: Velocity | None = None
    """X,Y knockback velocity of the character upon exiting hitlag, after DI is applied"""
    final_kb_angle: float | None = None
    """Angle of knockback, in degrees, after DI is applied"""
    start_pos: Position | None = None
    """Character's position upon entering hitlag, before any SDI or ASDI inputs."""
    end_pos: Position | None = None
    """Character's position upon exiting hitlag, after any SDI or ASDI inputs."""
    di_efficacy: float | None = None
    """Percentage. 0% = No change in KB angle, 100% = Maximum possible change in KB angle."""

    def _find_valid_sdi(self):
        """Populates self.sdi_inputs after all stick regions have been added. Automatically called by StatsComputer."""
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
            # unless the cardinal is not one of the composite values of the diagonal (i.e. UP_RIGHT -> UP means no SDI
            # UP_RIGHT -> DOWN or UP_RIGHT -> LEFT will register an SDI input)

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

    def change_in_position(self) -> Position:
        """Returns the difference in X pos and difference in Y pos of start_pos and end_pos.

        For distance, see .distance()
        """
        return self.end_pos - self.start_pos

    def distance(self) -> float:
        """Returns the calculated distance between the start and end position"""
        return dist(self.end_pos, self.start_pos)


# --------------------------------- L cancel --------------------------------- #


@dataclass()
class LCancelData(Stat):
    """
    Contains all data for a single L-Cancel Event.

    Attributes:
        frame_index : int
            The first frame of the event
        stocks_remaining : int
            Stocks remaining at the start of the event
        l_cancel : bool
            True if successful l-cancel
        move : Attack
            IntEnum representing which move was l-canceled
        position : GroundID
            IntEnum representing which platform/ground the player landed on
        trigger_input_frame : int
            Relative timing of the L/R/Z press. Negative values occur before landing, positive values occur after
            landing
        during_hitlag : bool
            True if the l-cancel input occurred during hitlag (thus extending the timing window)
        fastfall : bool
            True if character was fastfalling prior to landing
    """

    frame_index: int
    stocks_remaining: int
    l_cancel: bool
    move: Attack
    position: IntEnum
    trigger_input_frame: int
    during_hitlag: bool
    fastfall: bool


# ------------------------------- Shield Drop Data ------------------------------ #


@dataclass()
class ShieldDropData(Stat):
    frame_index: int
    position: IntEnum | int
    oo_shieldstun_frame: int


# ------------------------------- Recovery Data ------------------------------ #


# @dataclass
# class RecoveryData(Stat):
#     frame_index: int


# --------------------------------- Wrappers --------------------------------- #

# TODO ABC, protocol, mixin? for append, to_polars, etc.


class StatList(ABC, UserList):
    data: list[Stat]
    _data_header: dict
    _schema: dict

    @abstractmethod
    def append(self, item):
        pass

    def to_polars(self) -> pl.DataFrame:
        """Returns a Polars DataFrame representing the contents of the container.

        DataFrame creation is semantically equivalent to:
        ```
        if len(self.data) == 0:
            return pl.DataFrame([], schema=self._schema)
        else:
            return pl.DataFrame(
                [self._data_header | vars(stat) for stat in self.data if stat is not None], schema=self._schema
            )
        ```

        Some minor alterations are made per container-type to cast elements to Polars data types correctly.
        """
        if len(self.data) == 0:
            return pl.DataFrame([], schema=self._schema)
        else:
            return pl.DataFrame(
                [self._data_header | vars(stat) for stat in self.data if stat is not None], schema=self._schema
            )

    def write_excel(self, target: str | Path, utc_time: bool = False) -> None:
        """Writes excel file with target path.

        Excel cannot accept timezone-aware dataframes.

        If utc_time is False,
        the document will contain naive time local to the machine that parsed the replay.

        If utc_time is True,
        the document will contain naive UTC time.
        """

        df = self.to_polars()
        if utc_time:
            df = df.with_columns(pl.col("date_time").dt.convert_time_zone("UTC"))
        df.with_columns(pl.col("date_time").dt.replace_time_zone(None)).to_excel(target)


class Wavedashes(StatList):
    """Iterable wrapper, treat as list[WavedashData].

    Attributes:
        data : list[WavedashData]
            Contains the stats generated by StatsComputer.wavedash_compute()
        data_header : dict
            Contains metadat about the match, for use in constructing DataFrames
        schema : dict
            Complete schema dict, for use in constructing Polars DataFrames
    """

    data: list[WavedashData]

    def __init__(self, data_header):
        self._data_header = data_header
        self.data = []
        self._schema = {
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
            "costume": pl.Utf8,
            "opnt_character": pl.Utf8,
            "frame_index": pl.Int64,
            "stocks_remaining": pl.Int64,
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
        if len(self.data) == 0:
            return pl.DataFrame([], schema=self._schema)
        else:
            rows = []
            for stat in self.data:
                stat_dict = vars(stat).copy()
                stat_dict["direction"] = stat.direction.name

                rows.append(self._data_header | stat_dict)

            return pl.DataFrame(rows, schema=self._schema)


class Dashes(StatList):
    """Iterable wrapper, treat as list[DashData].

    Attributes:
        data : list[DashData]
            Contains the stats generated by StatsComputer.dash_compute()
        data_header : dict
            Contains metadat about the match, for use in constructing DataFrames
        schema : dict
            Complete schema dict, for use in constructing Polars DataFrames
    """

    data: list[DashData]

    def __init__(self, data_header):
        self._data_header = data_header
        self.data = []
        self._schema = {
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
            "costume": pl.Utf8,
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
        if len(self.data) == 0:
            return pl.DataFrame([], schema=self._schema)
        else:
            rows = []
            for stat in self.data:
                stat_dict = vars(stat).copy()
                stat_dict["direction"] = stat.direction.name

                rows.append(self._data_header | stat_dict)

            return pl.DataFrame(rows, schema=self._schema)


class Techs(StatList):
    """Iterable wrapper, treat as list[TechData].

    Attributes:
        data : list[TechData]
            Contains the stats generated by StatsComputer.tech_compute()
        data_header : dict
            Contains metadat about the match, for use in constructing DataFrames
        schema : dict
            Complete schema dict, for use in constructing Polars DataFrames
    """

    data: list[TechData]

    def __init__(self, data_header):
        self._data_header = data_header
        self.data = []
        self._schema = {
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
            "costume": pl.Utf8,
            "opnt_character": pl.Utf8,
            "frame_index": pl.Int64,
            "stocks_remaining": pl.Int64,
            "tech_type": pl.Utf8,
            "was_punished": pl.Boolean,
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
            return pl.DataFrame([], self._schema)
        else:
            rows = []

            for stat in self.data:
                try:
                    name = stat.last_hit_by.name
                except AttributeError:
                    name = None
                try:
                    ground_id = stat.ground_id.name
                except AttributeError:
                    ground_id = None
                stat_dict = vars(stat).copy()
                stat_dict["position"] = list(stat.position)
                stat_dict["tech_type"] = stat.tech_type.name
                stat_dict["ground_id"] = ground_id
                stat_dict["last_hit_by"] = name
                rows.append(self._data_header | stat_dict)

            return pl.DataFrame(rows, schema=self._schema)


class TakeHits(StatList):
    """Iterable wrapper, treat as list[TakeHitData].

    Attributes:
        data : list[TechData]
            Contains the stats generated by StatsComputer.tech_compute()
        data_header : dict
            Contains metadat about the match, for use in constructing DataFrames
        schema : dict
            Complete schema dict, for use in constructing Polars DataFrames
    """

    data: list[TakeHitData]

    def __init__(self, data_header):
        self._data_header = data_header
        self.data = []
        self._schema = {
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
            "costume": pl.Utf8,
            "opnt_character": pl.Utf8,
            "frame_index": pl.Int64,
            "stocks_remaining": pl.Int64,
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
            return pl.DataFrame([], self._schema)
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
                rows.append(self._data_header | stat_dict)

            df = pl.DataFrame(rows, schema=self._schema)
            return df


class LCancels(StatList):
    """Iterable wrapper for lists of l-cancel data"""

    data_header: dict
    percentage: float | None
    data: list[LCancelData]

    def __init__(self, data_header):
        self.percentage = None
        self.data = []
        self._data_header = data_header
        self._schema = {
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
            "costume": pl.Utf8,
            "opnt_character": pl.Utf8,
            "frame_index": pl.Int64,
            "stocks_remaining": pl.Int64,
            "l_cancel": pl.Boolean,
            "trigger_input_frame": pl.Int64,
            "during_hitlag": pl.Boolean,
            "move": pl.Utf8,
            "position": pl.Utf8,
            "fastfall": pl.Boolean,
        }

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
            self.percentage = (success / len(self.data)) * 100

    def to_polars(self):
        if len(self.data) == 0:
            return pl.DataFrame([], self._schema)
        else:
            rows = []
            # polars doesn't like the formats of some of our numbers, so we have to manually conver them to lists
            for stat in self.data:
                # we have to make a copy so we don't bork the data with our changes
                stat_dict = vars(stat).copy()
                try:
                    stat_dict["position"] = stat.position.name
                except AttributeError:
                    stat_dict["position"] = "UNKNOWN"
                stat_dict["move"] = stat.move.name

                rows.append(self._data_header | stat_dict)

            return pl.DataFrame(rows, schema=self._schema)


class ShieldDrops(StatList):
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
        rows = []
        for stat in self.data:
            stat_dict = stat.__dict__.copy()
            try:
                stat_dict["position"] = stat.position.name
            except AttributeError:
                stat_dict["position"] = "UNKNOWN"
            rows.append(self.data_header | stat_dict)

        return pl.DataFrame(rows)


class Data:
    """Iterable container of Stat Type containers. Stat Type containers are effectively list[StatType]

    Containers:
        wavedashes

        dashes

        techs

        take_hits

        l_cancels
    """

    wavedashes: Wavedashes
    dashes: Dashes
    techs: Techs
    take_hits: TakeHits
    l_cancels: LCancels
    shield_drops: ShieldDrops

    def __init__(self, data_header=None):
        self.wavedashes = Wavedashes(data_header)
        self.dashes = Dashes(data_header)
        self.techs = Techs(data_header)
        self.take_hits = TakeHits(data_header)
        self.l_cancels = LCancels(data_header)
        self.shield_drops = ShieldDrops(data_header)

    def __iter__(self):
        for item in (self.wavedashes, self.dashes, self.techs, self.take_hits, self.l_cancels):
            yield item
