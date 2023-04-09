from __future__ import annotations

import io
import struct
from collections.abc import Sequence
from enum import IntFlag

from .controller import Buttons, Triggers
from .enums.attack import Attack
from .enums.character import CSSCharacter, InGameCharacter
from .enums.item import Item, MissileType, TurnipFace
from .enums.stage import Stage
from .enums.state import (
    get_character_state,
    ActionState,
    Direction,
    Hurtbox,
    LCancel,
    Field1,
    Field2,
    Field3,
    Field4,
    Field5,
)
from .util import (
    Base,
    Enum,
    IntEnum,
    try_enum,
    unpack_bool,
    unpack_float,
    unpack_int8,
    unpack_int32,
    unpack_matchid,
    unpack_uint8,
    unpack_uint16,
    unpack_uint32,
)


# The first frame of the game is indexed -123, counting up to zero (which is when the word "GO" appears).
# But since players actually get control before frame zero (!!!), we need to record these frames.
FIRST_FRAME_INDEX = -123
PLAYER_CONTROL_INDEX = -39


class EventType(IntEnum):
    """Slippi events that can appear in a game's `raw` data."""

    EVENT_PAYLOADS = 0x35
    GAME_START = 0x36
    FRAME_PRE = 0x37
    FRAME_POST = 0x38
    GAME_END = 0x39
    FRAME_START = 0x3A
    ITEM = 0x3B
    FRAME_END = 0x3C
    GECKO_LIST = 0x3D
    MESSAGE_SPLITTER = 0x10


class MatchType(Enum):
    OFFLINE = -1
    RANKED = 0
    UNRANKED = 1
    DIRECT = 2
    OTHER = 3


# TODO make as many of these as possible dataclasses/recordclasses.
class Start(Base):
    """Information used to initialize the game such as the game mode, settings, characters & stage."""

    is_teams: bool  # True if this was a teams game
    players: tuple[Start.Player | None]  # Players in game, 0 indexed, empty ports will contain None
    random_seed: int  # Random seed before the game start
    slippi_version: Start.SlippiVersion  # Information about the Slippi recorder that generated this replay
    stage: Stage  # Stage on which this game was played
    is_pal: bool | None  # True if this was a PAL version of Melee
    is_frozen_ps: bool | None  # True if frozen Pokemon Stadium was enabled
    match_id: str | None  #  Mode (ranked/unranked) and time the match started
    match_type: MatchType
    game_number: int | None  # The game number for consecutive games
    tiebreak_number: int | None

    def __init__(
        self,
        is_teams: bool,
        players: tuple[Start.Player | None],
        random_seed: int,
        slippi: Start.SlippiVersion,
        stage: Stage,
        is_pal: bool | None = None,
        is_frozen_ps: bool | None = None,
        match_id: str | None = None,
        game_number: int | None = None,
        tiebreak_number: int | None = None,
    ):
        self.is_teams = is_teams
        self.players = players
        self.random_seed = random_seed
        self.slippi_version = slippi
        self.stage = stage
        self.is_pal = is_pal
        self.is_frozen_ps = is_frozen_ps
        self.match_id = match_id
        if match_id:  # it's lazy, but it works
            match match_id[5]:
                case "r":
                    self.match_type = MatchType.RANKED
                case "u":
                    self.match_type = MatchType.UNRANKED
                case "d":
                    self.match_type = MatchType.DIRECT
                case _:
                    self.match_type = MatchType.OTHER
        else:
            self.match_type = MatchType.OFFLINE
        self.game_number = game_number
        self.tiebreak_number = tiebreak_number

    @classmethod
    def _parse(cls, stream):
        slippi_version = cls.SlippiVersion._parse(stream)

        stream.read(8)  # skip game bitfields
        (is_teams,) = unpack_bool(stream.read(1))

        stream.read(5)  # skip item spawn behavior and self destruct score value
        (stage,) = unpack_uint16(stream.read(2))
        stage = Stage(stage)

        stream.read(80)  # skip game timer, item spawn bitfields, and damage ratio
        players: list[cls.Player | None] = []
        for i in range(4):
            (character,) = unpack_uint8(stream.read(1))
            (type,) = unpack_uint8(stream.read(1))
            (stocks,) = unpack_uint8(stream.read(1))
            (costume,) = unpack_uint8(stream.read(1))

            stream.read(5)  # skip team shade, handicap
            (team,) = unpack_uint8(stream.read(1))
            stream.read(26)  # skip remainder of player-specific game info

            try:
                type = cls.Player.Type(type)
            except ValueError:
                type = None

            if type is not None and type != cls.Player.Type.EMPTY:
                character = CSSCharacter(character)
                team = cls.Player.Team(team) if is_teams else None
                player = cls.Player(
                    character=character,
                    type=type,
                    stocks=stocks,
                    costume=costume,
                    team=team,
                )
            else:
                player = None

            players.append(player)

        stream.read(72)  # skip the rest of the game info block
        (random_seed,) = unpack_uint32(stream.read(4))

        try:  # v1.0.0
            for i in range(4):
                (dash_back,) = unpack_uint32(stream.read(4))
                (shield_drop,) = unpack_uint32(stream.read(4))
                dash_back = cls.Player.UCF.DashBack(dash_back)
                shield_drop = cls.Player.UCF.ShieldDrop(shield_drop)
                if players[i]:
                    players[i].ucf = cls.Player.UCF(dash_back, shield_drop)
        except struct.error:
            pass

        try:  # v1.3.0
            for i in range(4):
                tag_bytes = stream.read(16)
                if players[i]:
                    try:
                        null_pos = tag_bytes.index(0)
                        tag_bytes = tag_bytes[:null_pos]
                    except ValueError:
                        pass
                    players[i].tag = tag_bytes.decode("shift-jis").rstrip()
        except struct.error:
            pass

        # v1.5.0
        try:
            (is_pal,) = unpack_bool(stream.read(1))
        except struct.error:
            is_pal = None

        # v2.0.0
        try:
            (is_frozen_ps,) = unpack_bool(stream.read(1))
        except struct.error:
            is_frozen_ps = None

        # v3.14.0
        stream.read(283)  # skip major/minor scene and slippi info

        try:
            (match_id,) = unpack_matchid(stream.read(50))
            match_id = str(match_id.decode("utf-8")).rstrip("\x00")
        except struct.error:
            match_id = None
        except EOFError:
            match_id = None

        stream.read(1)
        try:
            (game_number,) = unpack_uint32(stream.read(4))
        except struct.error:
            game_number = None

        try:
            (tiebreak_number,) = unpack_uint32(stream.read(4))
        except struct.error:
            tiebreak_number = None

        return cls(
            is_teams=is_teams,
            players=tuple(players),
            random_seed=random_seed,
            slippi=slippi_version,
            stage=stage,
            is_pal=is_pal,
            is_frozen_ps=is_frozen_ps,
            match_id=match_id,
            game_number=game_number,
            tiebreak_number=tiebreak_number,
        )

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return (
            self.is_teams == other.is_teams
            and self.players == other.players
            and self.random_seed == other.random_seed
            and self.slippi_version == other.slippi_version
            and self.stage == other.stage
        )

    class SlippiVersion(Base):
        """Information about the Slippi recorder that generated this replay."""

        # TODO flatten to Slippi_Version

        major: int
        minor: int
        revision: int

        def __init__(self, major: int, minor: int, revision: int = 0, build=None):
            self.major = major
            self.minor = minor
            self.revision = revision
            # build was obsoleted in 2.0.0 and never held a nonzero value.

        @classmethod
        def _parse(cls, stream):
            # unpack returns a tuple, so we need to flatten the list.
            # Additionally, we need to splat it to send to the constructor
            # I try not to use this too often because it's annoying to read if you don't already know what it does
            return cls(*[tup[0] for tup in [unpack_uint8(stream.read(1)) for i in range(4)]])

        def __repr__(self):
            return f"{self.major}.{self.minor}.{self.revision}"

        def __eq__(self, other: Start.SlippiVersion | str):
            if isinstance(other, Sequence):
                if len(other) == 3:
                    major, minor, revision = other
                else:
                    raise ValueError(
                        f"""Incorrect Sequence {other} for SlippiVersion.
                                     Must have 3 elements (major, minor, revision)"""
                    )

                return self.major == major and self.minor == minor and self.revision == revision
            if isinstance(other, self.__class__):
                return self.major == other.major and self.minor == other.minor and self.revision == other.revision

            if isinstance(other, str):
                major, minor, revision = [int(n) for n in other.split(".", 2)]
                return self.major == major and self.minor == minor and self.revision == revision

            raise NotImplementedError(
                """Incorrect type for comparison to event.Start.Slippi,
                accepted types are event.Start.Slippi, event.Start.Slippi.Version, and str"""
            )

        def __ge__(self, other: Start.SlippiVersion | str | Sequence):
            if isinstance(other, Sequence):
                if len(other) == 3:
                    major, minor, revision = other
                else:
                    raise ValueError(
                        f"""Incorrect Sequence {other} for SlippiVersion.
                                     Must have 3 elements (major, minor, revision)"""
                    )

                return (
                    self.major > major
                    or (self.major == major and self.minor > minor)
                    or (self.minor == minor and self.revision >= revision)
                )

            if isinstance(other, self.__class__):
                return (
                    self.major > other.major
                    or (self.major == other.major and self.minor > other.minor)
                    or (self.minor == other.minor and self.revision >= other.revision)
                )

            if isinstance(other, str):
                return (
                    self.major > other.major
                    or (self.major == other.major and self.minor > other.minor)
                    or (self.minor == other.minor and self.revision >= other.revision)
                )

            raise NotImplementedError(
                """Incorrect type for comparison to event.Start.Slippi,
                accepted types are event.Start.Slippi, event.Start.Slippi.Version, and str"""
            )

        def __lt__(self, other: Start.SlippiVersion | Start.SlippiVersion | str):
            return not self.__ge__(other)

    class Player(Base):
        """Contains metadata about the player from the console's perspective including:
        character, starting stock count, costume, team, in-game tag, and UCF toggles"""

        character: CSSCharacter  # Character selected
        type: Start.Player.Type  # Player type (human/cpu)
        stocks: int  # Starting stock count
        costume: int  # Costume ID
        team: Start.Player.Team | None  # Team, if this was a teams game
        ucf: Start.Player.UCF | None  # UCF feature toggles
        tag: str | None  # Name tag

        def __init__(
            self,
            character: CSSCharacter,
            type: Start.Player.Type,
            stocks: int,
            costume: int,
            team: Start.Player.Team | None,
            ucf: Start.Player.UCF | None = None,
            tag: str | None = None,
        ):
            self.character = character
            self.type = type
            self.stocks = stocks
            self.costume = costume
            self.team = team
            self.ucf = ucf or self.UCF()
            self.tag = tag

        def __eq__(self, other):
            if not isinstance(other, self.__class__):
                return NotImplemented
            return (
                self.character is other.character
                and self.type is other.type
                and self.stocks == other.stocks
                and self.costume == other.costume
                and self.team is other.team
                and self.ucf == other.ucf
            )

        class Type(IntEnum):
            """Human vs CPU"""

            HUMAN = 0
            CPU = 1
            DEMO = 2
            EMPTY = 3

        class Team(IntEnum):
            """Doubles team colors"""

            RED = 0
            BLUE = 1
            GREEN = 2

        class UCF(Base):
            """UCF Dashback and shield drop, off, on, or arduino"""

            dash_back: Start.Player.UCF.DashBack | None  # UCF dashback status
            shield_drop: Start.Player.UCF.ShieldDrop | None  # UCF shield drop status

            def __init__(
                self,
                dash_back: Start.Player.UCF.DashBack | None = None,
                shield_drop: Start.Player.UCF.ShieldDrop | None = None,
            ):
                self.dash_back = dash_back or self.DashBack.OFF
                self.shield_drop = shield_drop or self.ShieldDrop.OFF

            def __eq__(self, other):
                if not isinstance(other, self.__class__):
                    return NotImplemented
                return self.dash_back == other.dash_back and self.shield_drop == other.shield_drop

            class DashBack(IntEnum):
                OFF = 0
                UCF = 1
                ARDUINO = 2

            class ShieldDrop(IntEnum):
                OFF = 0
                UCF = 1
                ARDUINO = 2


class End(Base):
    """Information about the end of the game."""

    method: End.Method  # How the game ended
    lras_initiator: int | None  # Index of player that LRAS'd, if any
    # Player placements stored as a list. The index represents the port, the value of that element is their placement.
    player_placements: list[int] | None  # 0-indexed placement positions. -1 if player not in game

    def __init__(
        self,
        method: End.Method,
        lras_initiator: int | None = None,
        player_placements: list[int] | None = None,
    ):
        self.method = method
        self.lras_initiator = lras_initiator
        self.player_placements = player_placements

    @classmethod
    def _parse(cls, stream):
        (method,) = unpack_uint8(stream.read(1))
        try:  # v2.0.0
            (lras,) = unpack_uint8(stream.read(1))
            lras_initiator = lras if lras < 4 else None
        except struct.error:
            lras_initiator = None

        try:  # v3.13.0
            (p1_placement,) = unpack_int8(stream.read(1))
            (p2_placement,) = unpack_int8(stream.read(1))
            (p3_placement,) = unpack_int8(stream.read(1))
            (p4_placement,) = unpack_int8(stream.read(1))
            player_placements = [p1_placement, p2_placement, p3_placement, p4_placement]
        except struct.error:
            player_placements = None
        return cls(cls.Method(method), lras_initiator, player_placements)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self.method is other.method

    class Method(IntEnum):
        INCONCLUSIVE = 0  # `obsoleted(2.0.0)`
        TIME = 1  # `added(2.0.0)`
        GAME = 2  # `added(2.0.0)`
        CONCLUSIVE = 3  # `obsoleted(2.0.0)`
        NO_CONTEST = 7  # `added(2.0.0)`


class Frame(Base):
    """A single frame of the game. Includes data for all active bodies (characters, items, etc.)"""

    __slots__ = "index", "ports", "items", "start", "end"

    index: int
    ports: Sequence[Frame.Port | None]  # Frame data for each port (0 indexed, including empty ports)
    items: Sequence[Frame.Item | None]  # Active items (includes projectiles)
    start: Frame.Start | None  # Start-of-frame data
    end: Frame.End | None  # End-of-frame data

    def __init__(self, index: int):
        self.index = index
        self.ports = [None, None, None, None]
        self.items = []
        self.start = None
        self.end = None

    def _finalize(self):
        self.ports = tuple(self.ports)
        self.items = tuple(self.items)

    class Port(Base):
        """Frame data for a given port. Can include two characters' frame data (ICs)."""

        __slots__ = "leader", "follower"

        leader: Frame.Port.Data  # Frame data for the controlled character
        follower: Frame.Port.Data | None  # Frame data for the follower (Nana), if any

        def __init__(self):
            self.leader = self.Data()
            self.follower = None

        class Data(Base):
            """Frame data for a given character. Includes both pre-frame and post-frame data."""

            __slots__ = "_pre", "_post"

            def __init__(self):
                self._pre = None
                self._post = None

            # Creates write-only, lazy access to
            @property
            def pre(self) -> Frame.Port.Data.Pre | None:
                """Pre-frame update data"""
                # could flatten these ifs, but it saves us a comparison the vast majority of the time we access it
                # since type(self._pre) is None is the same thing as not isinstance(self._pre, self.Pre)
                if not isinstance(self._pre, self.Pre):
                    if self._pre:
                        self._pre = self.Pre._parse(self._pre)
                return self._pre

            @property
            def post(self) -> Frame.Port.Data.Post | None:
                """Post-frame update data"""
                if not isinstance(self._post, self.Post):
                    if self._post:
                        self._post = self.Post._parse(self._post)
                return self._post

            class Pre(Base):
                """Pre-frame update data, required to reconstruct a replay. Information is collected right before
                controller inputs are used to figure out the character's next action."""

                __slots__ = (
                    "state",
                    "position",
                    "facing_direction",
                    "joystick",
                    "cstick",
                    "triggers",
                    "buttons",
                    "random_seed",
                    "raw_analog_x",
                    "percent",
                )

                state: ActionState | int
                position: Position
                facing_direction: Direction
                joystick: Position
                cstick: Position
                triggers: Triggers
                buttons: Buttons
                random_seed: int
                raw_analog_x: int | None
                percent: float | None

                def __init__(
                    self,
                    state: ActionState | int,
                    position: Position,
                    direction: Direction,
                    joystick: Position,
                    cstick: Position,
                    triggers: Triggers,
                    buttons: Buttons,
                    random_seed: int,
                    raw_analog_x: int | None = None,
                    damage: float | None = None,
                ):
                    self.state = state
                    self.position = position
                    self.facing_direction = direction
                    self.joystick = joystick
                    self.cstick = cstick
                    self.triggers = triggers
                    self.buttons = buttons
                    self.random_seed = random_seed
                    self.raw_analog_x = raw_analog_x
                    self.percent = damage

                @classmethod
                def _parse(
                    cls,
                    stream: io.BytesIO,
                    # it's dumb, but this promotes the functions to locals which are slightly faster to access
                    unpack_float=unpack_float,
                    unpack_uint32=unpack_uint32,
                    unpack_uint16=unpack_uint16,
                    unpack_uint8=unpack_uint8,
                ):
                    read = stream.read
                    (random_seed,) = unpack_uint32(read(4))
                    state = try_enum(ActionState, *unpack_uint16(read(2)))
                    position = Position(*unpack_float(read(4)), *unpack_float(read(4)))
                    # (position_x,) = unpack_float(read(4))
                    # (position_y,) = unpack_float(read(4))
                    direction = Direction(*unpack_float(read(4)))
                    joystick = Position(*unpack_float(read(4)), *unpack_float(read(4)))
                    # (joystick_x,) = unpack_float(read(4))
                    # (joystick_y,) = unpack_float(read(4))
                    cstick = Position(*unpack_float(read(4)), *unpack_float(read(4)))
                    # (cstick_x,) = unpack_float(read(4))
                    # (cstick_y,) = unpack_float(read(4))
                    (trigger_logical,) = unpack_float(read(4))
                    (buttons_logical,) = unpack_uint32(read(4))
                    (buttons_physical,) = unpack_uint16(read(2))
                    (trigger_physical_l,) = unpack_float(read(4))
                    (trigger_physical_r,) = unpack_float(read(4))

                    # v1.2.0
                    try:
                        (raw_analog_x,) = unpack_uint8(read(1))
                    except struct.error:
                        raw_analog_x = None

                    # v1.4.0
                    try:
                        (damage,) = unpack_float(read(4))
                    except struct.error:
                        damage = None

                    return cls(
                        state=state,
                        position=position,
                        direction=direction,
                        joystick=joystick,
                        cstick=cstick,
                        triggers=Triggers(trigger_logical, trigger_physical_l, trigger_physical_r),
                        buttons=Buttons(buttons_logical, buttons_physical),
                        random_seed=random_seed,
                        raw_analog_x=raw_analog_x,
                        damage=damage,
                    )

            class Post(Base):
                """Post-frame update data, for making decisions about game states (such as computing stats).
                Information is collected at the end of collision detection,
                which is the last consideration of the game engine.
                """

                __slots__ = (
                    "character",
                    "state",
                    "position",
                    "facing_direction",
                    "percent",
                    "shield_size",
                    "stocks_remaining",
                    "most_recent_hit",
                    "last_hit_by",
                    "combo_count",
                    "state_age",
                    "flags",
                    "misc_timer",
                    "is_airborne",
                    "last_ground_id",
                    "jumps_remaining",
                    "l_cancel",
                    "hurtbox_status",
                    "self_ground_speed",
                    "self_air_speed",
                    "knockback_speed",
                    "hitlag_remaining",
                    "animation_index",
                )

                character: InGameCharacter  # In-game character (can only change for Zelda/Sheik).
                state: ActionState | int  # Character's action state
                position: Position  # Character's position
                facing_direction: Direction  # Direction the character is facing
                percent: float  # Current damage percent
                shield_size: float  # Current size of shield
                stocks_remaining: int  # Number of stocks remaining
                most_recent_hit: Attack | int  # Last attack that this character landed
                last_hit_by: int | None  # Port of character that last hit this character
                combo_count: int  # Combo count as defined by the game
                state_age: float | None  # Number of frames action state has been active. Can be fractional
                flags: list[IntFlag] | None  # State flags
                misc_timer: float | None  # hitstun frames remaining
                is_airborne: bool | None  # True if character is airborne
                last_ground_id: int | None  # ID of ground character is standing on, if any
                jumps_remaining: int | None  # Jumps remaining
                l_cancel: LCancel | None  # L-cancel status, if any
                hurtbox_status: Hurtbox | None
                # speeds are split into 5 values. A shared Y, a grounded and air X, and a knockback X and Y.
                # Generic Y *DOES* matter, even when grounded.
                # For example, watch velocity values when walking on the slanted edges of yoshi's
                self_ground_speed: Velocity | None  # Self induced ground X speed and generic Y speed
                self_air_speed: Velocity | None  # Self induced air X speed and generic Y speed
                knockback_speed: Velocity | None  # Speed from knockback, adds with self-speeds for total velocity
                hitlag_remaining: float | None  # 0 means "not in hitlag"
                animation_index: int | None  # Indicates the animation the character is in, animation derived from state

                def __init__(
                    self,
                    character: InGameCharacter,
                    state: ActionState | int,
                    position: Position,
                    direction: Direction,
                    damage: float,
                    shield: float,
                    stocks: int,
                    most_recent_hit: Attack | int,
                    last_hit_by: int | None,
                    combo_count: int,
                    state_age: float | None = None,
                    flags: list[IntEnum] | None = None,
                    misc_timer: float | None = None,
                    airborne: bool | None = None,
                    last_ground_id: int | None = None,
                    jumps: int | None = None,
                    l_cancel: LCancel | None = None,
                    hurtbox_status: Hurtbox | None = None,
                    self_ground_speed: Velocity | None = None,
                    self_air_speed: Velocity | None = None,
                    knockback_speed: Velocity | None = None,
                    hitlag_remaining: float | None = None,
                    animation_index: int | None = None,
                ):
                    self.character = character
                    self.state = state
                    self.position = position
                    self.facing_direction = direction
                    self.percent = damage
                    self.shield_size = shield
                    self.stocks_remaining = stocks
                    self.most_recent_hit = most_recent_hit
                    self.last_hit_by = last_hit_by
                    self.combo_count = combo_count
                    self.state_age = state_age
                    self.flags = flags
                    self.misc_timer = misc_timer
                    self.is_airborne = airborne
                    self.last_ground_id = last_ground_id
                    self.jumps_remaining = jumps
                    self.l_cancel = l_cancel
                    self.hurtbox_status = hurtbox_status
                    self.self_ground_speed = self_ground_speed
                    self.self_air_speed = self_air_speed
                    self.knockback_speed = knockback_speed
                    self.hitlag_remaining = hitlag_remaining
                    self.animation_index = animation_index

                @classmethod
                def _parse(
                    cls,
                    stream: io.BytesIO,
                    unpack_uint8=unpack_uint8,
                    unpack_uint16=unpack_uint16,
                    unpack_float=unpack_float,
                    unpack_bool=unpack_bool,
                    unpack_uint32=unpack_uint32,
                ):
                    read = stream.read
                    character = try_enum(InGameCharacter, *unpack_uint8(read(1)))
                    state = get_character_state(*unpack_uint16(read(2)), character)
                    position = Position(*unpack_float(read(4)), *unpack_float(read(4)))
                    direction = Direction(*unpack_float(read(4)))
                    (damage,) = unpack_float(read(4))
                    (shield,) = unpack_float(read(4))
                    last_attack_landed = try_enum(Attack, *unpack_uint8(read(1)))
                    (combo_count,) = unpack_uint8(read(1))
                    (last_hit_by,) = unpack_uint8(read(1))
                    (stocks,) = unpack_uint8(read(1))
                    # v0.2.0
                    try:
                        (state_age,) = unpack_float(read(4))
                    except struct.error:
                        state_age = None

                    try:  # v2.0.0

                        flags = [
                            Field1(*unpack_uint8(read(1))),
                            Field2(*unpack_uint8(read(1))),
                            Field3(*unpack_uint8(read(1))),
                            Field4(*unpack_uint8(read(1))),
                            Field5(*unpack_uint8(read(1)))
                        ]

                        (misc_timer,) = unpack_float(read(4))
                        (airborne,) = unpack_bool(read(1))
                        (last_ground_id,) = unpack_uint16(read(2))
                        (jumps,) = unpack_uint8(read(1))
                        l_cancel = LCancel(*unpack_uint8(read(1)))

                    except struct.error:
                        (
                            flags,
                            misc_timer,
                            airborne,
                            last_ground_id,
                            jumps,
                            l_cancel,
                        ) = [None] * 6

                    try:  # v2.1.0
                        (hurtbox_status,) = unpack_uint8(read(1))
                    except struct.error:
                        hurtbox_status = None

                    try:  # v3.5.0
                        self_air_speed = Velocity(*unpack_float(read(4)), *unpack_float(read(4)))
                        knockback_speed = Velocity(*unpack_float(read(4)), *unpack_float(read(4)))
                        self_ground_speed = Velocity(*unpack_float(read(4)), self_air_speed.y)

                    except struct.error:
                        (self_ground_speed, self_air_speed, knockback_speed) = [None] * 3

                    try:  # v3.8.0
                        (hitlag_remaining,) = unpack_float(read(4))
                    except struct.error:
                        hitlag_remaining = None

                    try:  # v3.11.0
                        (animation_index,) = unpack_uint32(read(4))
                    except struct.error:
                        animation_index = None

                    return cls(
                        character=character,
                        state=state,
                        state_age=state_age,
                        position=position,
                        direction=direction,
                        damage=damage,
                        shield=shield,
                        stocks=stocks,
                        most_recent_hit=last_attack_landed,
                        last_hit_by=last_hit_by if last_hit_by < 4 else None,
                        combo_count=combo_count,
                        flags=flags,
                        misc_timer=misc_timer,
                        airborne=airborne,
                        last_ground_id=last_ground_id,
                        jumps=jumps,
                        l_cancel=l_cancel,
                        hurtbox_status=hurtbox_status,
                        self_ground_speed=self_ground_speed,
                        self_air_speed=self_air_speed,
                        knockback_speed=knockback_speed,
                        hitlag_remaining=hitlag_remaining,
                        animation_index=animation_index,
                    )

    class Item(Base):
        """An active item (includes projectiles)."""

        __slots__ = (
            "type",
            "state",
            "direction",
            "velocity",
            "position",
            "damage",
            "timer",
            "spawn_id",
        )

        type: Item  # Item type
        state: int  # Item's action state
        direction: Direction | None  # Direction item is facing
        velocity: Velocity  # Item's velocity
        position: Position  # Item's position
        damage: int  # Amount of damage item has taken
        timer: int  # Frames remaining until item expires
        spawn_id: int  # Unique ID per item spawned (0, 1, 2, ...)
        missile_type: MissileType | None
        turnip_type: TurnipFace | None
        is_shot_launched: bool | None
        charge_power: int | None
        owner: int | None

        def __init__(
            self,
            type: Item,
            state: int,
            direction: Direction | None,
            velocity: Velocity,
            position: Position,
            damage: int,
            timer: int,
            spawn_id: int,
            missile_type: int | None,
            turnip_type: TurnipFace | None,
            is_shot_launched: bool | None,
            charge_power: int | None,
            owner: int | None,
        ):
            self.type = type
            self.state = state
            self.direction = direction
            self.velocity = velocity
            self.position = position
            self.damage = damage
            self.timer = timer
            self.spawn_id = spawn_id
            self.missile_type = missile_type
            self.turnip_type = turnip_type
            self.is_shot_launched = is_shot_launched
            self.charge_power = charge_power
            self.owner = owner

        @classmethod
        def _parse(cls, stream):
            (type,) = unpack_uint16(stream.read(2))
            (state,) = unpack_uint8(stream.read(1))
            (direction,) = unpack_float(stream.read(4))
            (x_vel,) = unpack_float(stream.read(4))
            (y_vel,) = unpack_float(stream.read(4))
            (x_pos,) = unpack_float(stream.read(4))
            (y_pos,) = unpack_float(stream.read(4))
            (damage,) = unpack_uint16(stream.read(2))
            (timer,) = unpack_float(stream.read(4))
            (spawn_id,) = unpack_uint32(stream.read(4))

            try:
                (missile_type,) = unpack_uint8(stream.read(1))
                (turnip_type,) = unpack_uint8(stream.read(1))
                (is_shot_launched,) = unpack_uint8(stream.read(1))
                (charge_power,) = unpack_uint8(stream.read(1))
                (owner,) = unpack_int8(stream.read(1))
                missile_type = try_enum(MissileType, missile_type) if type == Item.SAMUS_MISSILE else missile_type
                turnip_type = try_enum(TurnipFace, turnip_type) if type == Item.PEACH_TURNIP else turnip_type
            except struct.error:
                missile_type = None
                turnip_type = None
                is_shot_launched = None
                charge_power = None
                owner = None

            return cls(
                type=try_enum(Item, type),
                state=state,
                direction=Direction(direction) if direction != 0 else None,
                velocity=Velocity(x_vel, y_vel),
                position=Position(x_pos, y_pos),
                damage=damage,
                timer=timer,
                spawn_id=spawn_id,
                missile_type=missile_type,
                turnip_type=turnip_type,
                is_shot_launched=is_shot_launched,
                charge_power=charge_power,
                owner=owner,
            )

        def __eq__(self, other):
            if not isinstance(other, self.__class__):
                return NotImplemented
            return (
                self.type == other.type
                and self.state == other.state
                and self.direction == other.direction
                and self.velocity == other.velocity
                and self.position == other.position
                and self.damage == other.damage
                and self.timer == other.timer
                and self.spawn_id == other.spawn_id
            )

    class Start(Base):
        """Start-of-frame data."""

        __slots__ = ("random_seed",)

        random_seed: int  # The random seed at the start of the frame

        def __init__(self, random_seed: int):
            self.random_seed = random_seed

        @classmethod
        def _parse(cls, stream):
            (random_seed,) = unpack_uint32(stream.read(4))
            # random_seed = random_seed ??? why was this here?
            return cls(random_seed)

        def __eq__(self, other):
            if not isinstance(other, self.__class__):
                return NotImplemented
            return self.random_seed == other.random_seed

    class End(Base):
        """End-of-frame data."""

        def __init__(self):
            pass

        @classmethod
        def _parse(cls, stream):
            return cls()

        def __eq__(self, other):
            if not isinstance(other, self.__class__):
                return NotImplemented
            return True

    class Event(Base):
        """Temporary wrapper used while parsing frame data."""

        __slots__ = "id", "type", "data"

        def __init__(self, id, type, data):
            self.id = id
            self.type = type
            self.data = data

        class Id(Base):
            __slots__ = ("frame",)

            def __init__(self, stream):
                (self.frame,) = unpack_int32(stream.read(4))

        class PortId(Id):
            __slots__ = "port", "is_follower"

            def __init__(self, stream):
                (self.frame,) = unpack_int32(stream.read(4))
                (self.port,) = unpack_uint8(stream.read(1))
                (self.is_follower,) = unpack_bool(stream.read(1))

        class Type(Enum):
            START = "start"
            END = "end"
            PRE = "pre"
            POST = "post"
            ITEM = "item"


class Position(Base):
    __slots__ = "x", "y"

    x: float
    y: float

    def __init__(self, x: float = 0.0, y: float = 0.0):
        self.x = x
        self.y = y

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self.x == other.x and self.y == other.y

    def __sub__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return (self.x - other.x, self.y - other.y)

    def __add__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return (self.x + other.x, self.y + other.y)

    def __iter__(self):
        for val in [self.x, self.y]:
            yield val

    def __repr__(self):
        return f"({self.x:.2f}, {self.y:.2f})"


class Velocity(Base):
    __slots__ = "x", "y"

    x: float
    y: float

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self.x == other.x and self.y == other.y

    def __add__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return Velocity(self.x + other.x, self.y + other.y)

    def __iter__(self):
        for val in [self.x, self.y]:
            yield val

    def __repr__(self):
        return f"({self.x:.2f}, {self.y:.2f})"
