from dataclasses import dataclass
from math import degrees, dist
from typing import Optional
from abc import ABC
from collections import UserList

import polars as pl

from slippistats.util import try_enum

from .common import (get_angle, TechType, JoystickRegion)
from ..enums import (ActionState, Attack)
from ..event import Position, Velocity


#TODO abstract base class:
class Stat(ABC):
    pass

#TODO add stocks_remaining

# --------------------------------- Wavedash --------------------------------- #


@dataclass
class WavedashData(Stat):
    frame_index: int
    angle: Optional[float]  # in degrees
    direction: Optional[str]
    r_frame: int  # which airborne frame was the airdodge input on?
    airdodge_frames: int
    waveland: bool

    def __init__(self, frame_index: int, r_input_frame: int = 0, stick: Optional[Position] = None, airdodge_frames: int = 0):
        self.frame_index = frame_index
        if stick:
            # atan2 converts coordinates to degrees without losing information (with tan quadrent 1 and 3 are both positive)
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
        self.r_frame = r_input_frame
        self.airdodge_frames = airdodge_frames
        self.waveland = True

    def total_startup(self) -> int:
        return self.r_frame + self.airdodge_frames


# ----------------------------------- Dash ----------------------------------- #


@dataclass
class DashData(Stat):
    frame_index: int
    start_pos: float
    end_pos: float
    direction: str
    is_dashdance: bool

    def __init__(self, frame_index:int =-1, direction:str ="NONE", is_dashdance:bool =False, start_pos:float =0, end_pos:float =0):
        self.frame_index = frame_index
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.direction = direction
        self.is_dashdance = is_dashdance

    def distance(self) -> float:
        return abs(self.end_pos - self.start_pos)



# ----------------------------------- Tech ----------------------------------- #


@dataclass
class TechData(Stat):
    frame_index: int
    tech_type: Optional[TechType]
    was_punished: bool
    direction: str
    position: Position
    is_on_platform: bool
    is_missed_tech:bool
    towards_center: Optional[bool]
    towards_opponent: Optional[bool]
    jab_reset: Optional[bool]
    last_hit_by: str

    def __init__(self):
        self.frame_index = -1
        self.tech_type = None
        self.is_missed_tech = False
        self.was_punished = False
        self.jab_reset = None
        self.towards_center = None
        self.towards_opponent = None



@dataclass
class TechState():
    tech: TechData
    last_state: Optional[ActionState | int]

    def __init__(self):
        self.tech = TechData()
        self.last_state = -1


# --------------------------------- Take hit --------------------------------- #


@dataclass
class TakeHitData(Stat):
    frame_index: int
    last_hit_by: Optional[Attack]
    grounded: Optional[bool]
    crouch_cancel: Optional[bool]
    hitlag_frames: Optional[int]
    stick_regions_during_hitlag: list[JoystickRegion]
    sdi_inputs: list[JoystickRegion]
    asdi: Optional[JoystickRegion]
    di_stick_pos: Optional[float]
    percent: Optional[float]
    kb_velocity: Optional[Velocity]
    kb_angle: Optional[float]
    final_kb_velocity: Optional[Velocity]
    final_kb_angle: Optional[float]
    start_pos: Optional[Position]
    end_pos: Optional[Position]
    di_efficacy: Optional[float]

    def __init__(self):
        self.frame_index = -1
        self.grounded = None
        self.percent = None
        self.last_hit_by = None
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

            # Diagonal -> cardinal will NOT result in a second SDI input unless the cardinal borders the opposite quadrant
            if prev_stick_region % 2 == 1:
                if stick_region % 2 == 1:
                    self.sdi_inputs.append(stick_region)
                # HACK there's probably less stupid way to do this, but I checked and for any valid diagonal->cadinal (DR->L, UL->D, etc.)
                # the absolute value of the difference between the 2 (order doesn't matter) is always 3 or 5 so this literally works
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
    frame_index=int
    l_cancel: bool
    move: Attack
    slideoff: bool
    trigger_input_frame: int

    def __init__(self, frame_index, l_cancel, move, slideoff, trigger_input_frame):
        self.frame_index = frame_index
        self.l_cancel = l_cancel
        self.trigger_input_frame = trigger_input_frame
        match move:
            case ActionState.ATTACK_AIR_N:
                self.move = Attack.NAIR.name
            case ActionState.ATTACK_AIR_F:
                self.move = Attack.FAIR.name
            case ActionState.ATTACK_AIR_B:
                self.move = Attack.BAIR.name
            case ActionState.ATTACK_AIR_HI:
                self.move = Attack.UAIR.name
            case ActionState.ATTACK_AIR_LW:
                self.move = Attack.DAIR.name
            case _:
                self.move = "UNKNOWN"
        self.slideoff = slideoff



# --------------------------------- Wrappers --------------------------------- #


class Wavedashes(UserList):
    """Iterable wrapper for lists of Wavedash data"""
    data_header: dict
    data: list

    def __init__(self, data_header):
        self.data_header = data_header
        self.data = []

    def to_polars(self) -> pl.DataFrame:
        return pl.DataFrame([self.data_header | wavedash.__dict__ for wavedash in self])


class Dashes(UserList):
    """Iterable wrapper for lists of Dash data"""
    data_header: dict
    data: list

    def __init__(self, data_header):
        self.data_header = data_header
        self.data = []

    def to_polars(self):
        return pl.DataFrame([self.data_header | dash.__dict__ for dash in self])


class Techs(UserList):
    """Iterable wrapper for lists of Tech data"""
    data_header: dict
    data: list

    def __init__(self, data_header):
        self.data_header = data_header
        self.data = []

    def to_polars(self):
        return pl.DataFrame([self.data_header | tech.__dict__ for tech in self])


class TakeHits(UserList):
    """Iterable wrapper rapper for lists of Take Hit data"""
    data_header: dict
    data: list

    def __init__(self, data_header):
        self.data_header = data_header
        self.data = []

    def to_polars(self):

        data = []

        # polars doesn't like the formats of some of our numbers, so we have to manually conver them to lists
        for take_hit in self:
            th_dict = take_hit.__dict__.copy()
            try:
                lhb = try_enum(Attack, take_hit.last_hit_by).name
            except:
                lhb = None
            th_dict["last_hit_by"] = lhb or "UNKNOWN"
            th_dict["sdi_inputs"] = [region.name for region in take_hit.sdi_inputs]
            th_dict["asdi"] = take_hit.asdi.name
            th_dict["stick_regions_during_hitlag"] = [region.name for region in take_hit.stick_regions_during_hitlag]
            th_dict["kb_velocity"] = [take_hit.kb_velocity.x, take_hit.kb_velocity.y]
            th_dict["final_kb_velocity"] = [take_hit.final_kb_velocity.x, take_hit.final_kb_velocity.y]
            th_dict["start_pos"] = [take_hit.start_pos.x, take_hit.start_pos.y]
            th_dict["end_pos"] = [take_hit.end_pos.x, take_hit.end_pos.y]
            if take_hit.di_stick_pos is not None:
                th_dict["di_stick_pos"] = [take_hit.di_stick_pos.x, take_hit.di_stick_pos.y]
            else:
                th_dict["di_stick_pos"] = None
            data.append(self.data_header | th_dict)
        return pl.DataFrame(data)

class LCancels(UserList):
    """Iterable wrapper for lists of l-cancel data"""
    data_header: dict
    successful: int
    failed: int
    data: list

    def __init__(self, data_header):
        self.data_header = data_header
        self.data = []

    def percentage(self):
        return (self.successful / (self.successful + self.failed)) * 100

    def to_polars(self):
        return pl.DataFrame([self.data_header | l_cancel.__dict__ for l_cancel in self])


@dataclass
class Data():
    wavedashes: Wavedashes
    dashes: Dashes
    techs: Techs
    take_hits: TakeHits
    l_cancels: Optional[LCancelData] = None

    def __init__(self, data_header):
        self.wavedashes = Wavedashes(data_header)
        self.dashes = Dashes(data_header)
        self.techs = Techs(data_header)
        self.take_hits = TakeHits(data_header)
        self.l_cancels = LCancels(data_header)