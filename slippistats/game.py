from __future__ import annotations

import os
from dataclasses import dataclass
from logging import debug
from typing import BinaryIO, Optional, TYPE_CHECKING

from .enums import InGameCharacter, CSSCharacter
from .event import FIRST_FRAME_INDEX, End, Frame, Start
from .metadata import Metadata
from .parse import parse
from .util import Base, Ports


class Game(Base):
    """Replay data from a game of Super Smash Brothers Melee."""

    start: Optional[Start]  #: Information about the start of the game
    frames: tuple[Frame]  #: Every frame of the game, indexed by frame number
    end: Optional[End]  #: Information about the end of the game
    metadata: Optional[Metadata]  #: Miscellaneous data not directly provided by Melee
    metadata_raw: Optional[dict]  #: Raw JSON metadata, for debugging and forward-compatibility

    def __init__(self, source: BinaryIO | str | os.PathLike, skip_frames: bool = False):
        """Parse a Slippi replay.

        :param input: replay file object or path"""
        self.start = None
        self.frames = []
        self.end = None
        self.metadata = None
        self.metadata_raw = None
        self.players = []

        parse(
            source, {
                Start: lambda x: setattr(self, 'start', x),
                Frame: self._add_frame,
                End: lambda x: setattr(self, 'end', x),
                Metadata: lambda x: setattr(self, 'metadata', x),
                dict: lambda x: setattr(self, 'metadata_raw', x)
                }, skip_frames
            )

        self.frames = tuple(self.frames)


    def _add_frame(self, frame: Frame):
        idx = frame.index - FIRST_FRAME_INDEX
        count = len(self.frames)
        if idx == count:
            self.frames.append(frame)
        elif idx < count:  # rollback
            debug(f"rollback: {count-1} -> {idx}")
            self.frames[idx] = frame
        else:
            raise ValueError(f'missing frames: {count-1} -> {idx}')

    def _attr_repr(self, attr):
        self_attr = getattr(self, attr)
        if isinstance(self_attr, list):
            return f'{attr}=[...]({len(self_attr)})' % (attr, len(self_attr))
        elif attr == 'metadata_raw':
            return None
        else:
            return super()._attr_repr(attr)

    
