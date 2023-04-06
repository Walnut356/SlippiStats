from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import tzlocal

from .event import FIRST_FRAME_INDEX
from .enums.character import InGameCharacter
from .util import Base, Enum


class Metadata(Base):
    """Miscellaneous data not directly provided by Melee."""

    date: datetime  #: Game start date & time
    duration: int  #: Duration of game, in frames
    platform: Metadata.Platform  #: Platform the game was played on (console/dolphin)
    players: tuple[
        Metadata.Player | None
    ]  #: Player metadata by port (port 1 is at index 0; empty ports will contain None)
    console_name: str | None  #: Name of the console the game was played on, if any

    def __init__(
        self,
        date: datetime,
        duration: int,
        platform: Metadata.Platform,
        players: tuple[Metadata.Player | None],
        console_name: str | None = None,
    ):
        self.date = date
        self.duration = duration
        self.platform = platform
        self.players = players
        self.console_name = console_name

    @classmethod
    def _parse(cls, json):
        raw_date = json["startAt"].rstrip("\x00")  # workaround for Nintendont/Slippi<1.5 bug
        # timezone & fractional seconds aren't always provided, so parse the date manually
        # (strptime lacks support for optional components)
        raw_date = [
            int(g or "0")
            for g in re.search(
                r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?(?:Z|\+(\d{2})(\d{2}))?$", raw_date
            ).groups()
        ]
        # MatchID already contains UTC time, so timezone will be the timezone of the device that parsed the replay.
        date = datetime(*raw_date[:7], timezone(timedelta(hours=raw_date[7], minutes=raw_date[8]))).astimezone(
            tzlocal.get_localzone()
        )
        # Duration is stored as the final frame index + the "pre-Go" frames.
        try:
            duration = 1 + json["lastFrame"] - FIRST_FRAME_INDEX
        except KeyError:
            duration = None

        platform = cls.Platform(json["playedOn"])

        console_name = json.get("consoleNick", None)

        players = [None, None, None, None]

        try:
            for port, player in json["players"].items():
                players[int(port)] = cls.Player._parse(player)
        except KeyError:
            pass

        return cls(
            date=date,
            duration=duration,
            platform=platform,
            players=tuple(players),
            console_name=console_name,
        )

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return (
            self.date == other.date
            and self.duration == other.duration
            and self.platform == other.platform
            and self.players == other.players
            and self.console_name == other.console_name
        )

    class Player(Base):
        """Contains metadata from the perspective of slippi,
        including character usage, netplay info, connect code, and display name"""

        characters: dict[InGameCharacter, int]  #: Character(s) used, with usage duration in frames (for Zelda/Sheik)
        connect_code: str | None
        display_name: str | None

        def __init__(self, characters: dict[InGameCharacter, int], netplay: Metadata.Player.Netplay | None = None):
            self.characters = characters
            if netplay:
                self.connect_code = netplay.code
                self.display_name = netplay.name
            else:
                self.connect_code = None
                self.display_name = None

        @classmethod
        def _parse(cls, json):
            characters = {}
            for char_id, duration in json["characters"].items():
                characters[InGameCharacter(int(char_id))] = duration
            try:
                netplay = cls.Netplay(code=json["names"]["code"], name=json["names"]["netplay"])
            except KeyError:
                netplay = None
            return cls(characters, netplay)

        def __eq__(self, other):
            if not isinstance(other, self.__class__):
                return NotImplemented
            return self.characters == other.characters and self.connect_code == other.connect_code

        class Netplay(Base):
            """Contains netplay name and netplay display name"""

            code: str  #: Netplay code (e.g. "ABCD#123")
            name: str  #: Netplay nickname

            def __init__(self, code: str, name: str):
                self.code = code
                self.name = name

            def __eq__(self, other):
                if not isinstance(other, self.__class__):
                    return NotImplemented
                return self.code == other.code and self.name == other.name

    class Platform(Enum):
        CONSOLE = "console"
        DOLPHIN = "dolphin"
        NETWORK = "network"
        NINTENDONT = "nintendont"
