from __future__ import annotations

import io
import struct
from collections.abc import Sequence
from enum import IntFlag

from .controller import Buttons, Triggers
from .enums.attack import Attack
from .enums.character import CSSCharacter, InGameCharacter, get_costume
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
    Port,
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


class Start(Base):
    """Information used to initialize the game such as the game mode, settings, characters & stage.

    Attributes:
        slippi_version : SlippiVersion
            Version of the recorder that generated the replay. Major releases:

            v0.1.0 Initial Release

            v1.0.0 Dolphin Slippi Release

            v2.0.0 Slippi Rollback Release

            v3.0.0 Slippi Ranked Pre-release

        players : tuple[Player | None]
            4-element container corresponding to in-game ports with metadata for each port. Empty ports contain None.
        random_seed : int
            Random seed upon initializing the game
        stage : Stage
            Which stage the game was played on
    `Minimum Replay Version: 1.5.0`:
        is_pal : bool
            True if recorded on the PAL version of Melee
    `Minimum Replay Version: 2.0.0`:
        is_frozen_ps : bool
            True if Pokemon Stadium transformations were disabled
    `Minimum Replay Version: 3.14.0`:
        match_id : str
            In format mode.[mode]-[ISO 8601 timestamp]. For slippi matchmaking, Match IDs correspond to one instance of
            queuing into another player. Each game before disconnecting will have the same Match ID, but a different
            `game_number`.
        match_type : MatchType
            Enum representing one of the slippi matchmaking modes: Direct, Unranked, Ranked, Offline, and Other
        game_number : int
            Which game number this replay is for the current `match_id`
        tiebreak_number : int
            If `MatchType.RANKED` and a tiebreak is necessary, acts as `game_number` for tiebreaks.
    """

    is_teams: bool
    players: tuple[Start.Player | None]
    """4-element container corresponding to in-game ports with metadata for each port. Empty ports contain None."""
    random_seed: int
    """Random seed upon initializing the game"""
    slippi_version: Start.SlippiVersion
    stage: Stage
    """Which stage the game was played on"""
    is_pal: bool | None
    is_frozen_ps: bool | None
    match_id: str | None
    """In format mode.[mode]-[ISO 8601 timestamp]. For slippi matchmaking, Match IDs correspond to one instance of
    queuing into another player. Each game before disconnecting will have the same Match ID, but a different
    `game_number`."""
    match_type: MatchType
    """Enum representing one of the slippi matchmaking modes: Direct, Unranked, Ranked, Offline, and Other"""
    game_number: int | None
    """Which game number this replay is for the current `match_id`"""
    tiebreak_number: int | None
    """If `MatchType.RANKED` and a tiebreak is necessary, acts as `game_number` for tiebreaks."""

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
        stage = Stage(*unpack_uint16(stream.read(2)))

        stream.read(80)  # skip game timer, item spawn bitfields, and damage ratio
        players: list[cls.Player | None] = []
        for i in range(4):
            character = CSSCharacter(*unpack_uint8(stream.read(1)))
            (type,) = unpack_uint8(stream.read(1))
            (stocks,) = unpack_uint8(stream.read(1))
            costume = get_costume(character, *unpack_uint8(stream.read(1)))

            stream.read(5)  # skip team shade, handicap
            team = cls.Player.Team(*unpack_uint8(stream.read(1)))
            stream.read(26)  # skip remainder of player-specific game info

            try:
                type = cls.Player.Type(type)
            except ValueError:
                type = None

            if type is not None and type != cls.Player.Type.EMPTY:
                player = cls.Player(
                    character=character,
                    type=type,
                    stocks=stocks,
                    costume=costume,
                    team=team if is_teams else None,
                )
            else:
                player = None

            players.append(player)

        stream.read(72)  # skip the rest of the game info block
        (random_seed,) = unpack_uint32(stream.read(4))

        try:  # v1.0.0
            for i in range(4):
                dash_back = cls.Player.UCF.DashBack(*unpack_uint32(stream.read(4)))
                shield_drop = cls.Player.UCF.ShieldDrop(*unpack_uint32(stream.read(4)))

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
            match_id = str(unpack_matchid(stream.read(50))[0].decode("utf-8")).rstrip("\x00")
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
        """Information about the Slippi recorder that generated this replay.

        Can be compared to tuples (0, 1, 0), strings '0.1.0', or other SlippiVersion objects SlippiVersion(0, 1, 0)
        """

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
        """Contains metadata about the player from the console's perspective.

        Attributes:
            character : CSSCharacter
                The character chosen on the character select screen
            type : Type
                Enumerated classification of the player. Can be Human, CPU, Demo, or Empty
            stocks : int
                How many stocks the player starts the game with
            costume : IntEnum
                Index of the selected costume
            team : Team
                Enumerated team color. If not a Teams game, this field corresponds to the player's shield color.
        `Minimum Replay Version: 1.0.0`:
            ucf : UCF
                Information on which UCF toggles were enabled, if any
            tag : str
                The in-game tag that hovers over the player, if any
        """

        character: CSSCharacter
        type: Type
        stocks: int
        costume: IntEnum
        team: Team | None
        ucf: UCF | None
        tag: str | None

        def __init__(
            self,
            character: CSSCharacter,
            type: Start.Player.Type,
            stocks: int,
            costume: IntEnum,
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
            """The game's classification of the type of player: Human, CPU, Demo, or Empty"""

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
            """UCF Dashback and shield drop. Can be off, on, or arduino"""

            dash_back: Start.Player.UCF.DashBack | None
            shield_drop: Start.Player.UCF.ShieldDrop | None

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
    """Information about the end of the game.

    Attributes:
        method : Method
            Enumeration of game end methods: Inconclusive, Time, Game, Conclusive, No Contest
    `Minimum Replay Version: 2.0.0`:
        lras_initiatior : int
            Index of the player that LRAS'd. None if not applicable
    `Minimum Replay Version: 3.13.0`:
        player_placements : list[int]
            List of placements, lower is better. List is in port order, 0 indexed. Placement is -1 if port is Type.Empty
    """

    method: Method
    lras_initiator: int | None
    player_placements: list[int] | None

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
            player_placements = [
                *unpack_uint8(stream.read(1)),  # p1 placement
                *unpack_uint8(stream.read(1)),
                *unpack_uint8(stream.read(1)),
                *unpack_uint8(stream.read(1)),  # p4 placement
            ]

        except struct.error:
            player_placements = None
        return cls(cls.Method(method), lras_initiator, player_placements)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self.method is other.method

    class Method(IntEnum):
        INCONCLUSIVE = 0
        TIME = 1
        GAME = 2
        CONCLUSIVE = 3
        NO_CONTEST = 7


class Frame(Base):
    """A single frame of the game. Includes data for all active bodies (characters, items, etc.)

    Attributes:
        index : int
            -123 indexed Frame counter
        ports : Sequence[Frame.Port | None]
            Data for each port on a single frame
    `Minimum Replay Version: 2.2.0`:
        start : Frame.Start
            Information given at the start of the frame to help keep netplay clients in sync
    `Minimum Replay Version: 3.0.0`:
        items : Sequence[Frame.Item | None]
            Data for up to 15 items on a single frame
        end : Frame.End
            Information given at the end of a frame to mark that there is no further information for that frame."""

    __slots__ = "index", "ports", "items", "start", "end"

    index: int
    ports: Sequence[Frame.Port | None]
    items: Sequence[Frame.Item | None]
    start: Frame.Start | None
    end: Frame.End | None

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
        """Frame data for a given port.

        Attributes:
            leader:
                Main active character
            follower:
                Secondary active character if applicable (ic's)
        """

        __slots__ = "leader", "follower"

        leader: Frame.Port.Data
        follower: Frame.Port.Data | None

        def __init__(self):
            self.leader = self.Data()
            self.follower = None

        class Data(Base):
            """Frame data for a given character

            Attributes:
                pre : Data.Pre
                    Data about the given player, used by the engine to update the player's state for the frame
                post : Data.Post
                    Data about the given player, after the game engine has updated for the frame
            """

            __slots__ = "_pre", "_post"

            def __init__(self):
                self._pre = None
                self._post = None

            # Makes pre/post frame write-only, also allows for lazy access. Pre and post frame are not parsed until
            # requested, which saves about half of the total parsing time
            @property
            def pre(self) -> Frame.Port.Data.Pre | None:
                """Pre-frame update data used by the game engine to update the player's state"""
                # could flatten these ifs, but it saves us a comparison the vast majority of the time we access it
                # since type(self._pre) is None is the same thing as not isinstance(self._pre, self.Pre)
                if not isinstance(self._pre, self.Pre):
                    if self._pre:
                        self._pre = self.Pre._parse(self._pre)
                return self._pre

            @property
            def post(self) -> Frame.Port.Data.Post | None:
                """Post-frame update data after the game engine has updated the player's state"""
                if not isinstance(self._post, self.Post):
                    if self._post:
                        self._post = self.Post._parse(self._post)
                return self._post

            class Pre(Base):
                """Pre-frame update data, required to reconstruct a replay. Information is collected right before
                controller inputs are used to figure out the character's next action.

                Attributes:
                    state : ActionState | int
                        Enumeration representing the characters current Action State
                    position : Position
                        X, Y coordinates of the player's in-engine position. Position does not necessarily corrispond to
                        the character model.
                    facing_direction : Direction
                        Enumeration with values LEFT and RIGHT. DOWN is used for stats, but also represents the facing
                        direction when using the Warp Star item
                    joystick : Position
                        X, Y coordinates of the player's joystick position
                    cstick : Position
                        X, Y coordinates of the player's cstick position
                    triggers : Triggers
                        Contains the physical (controller perspective) and logical (game engine perspective) trigger
                        values
                    buttons : Buttons
                        Contains the physical (controller perspective) and logical (game engine perspective)
                        button values. Also contains generalized stick/trigger values
                    random_seed : int
                        Random seed value used for the upcoming physics calculation
                `Minimum Replay Version: 1.2.0`:
                    raw_analog_x : float | None
                        Raw X axis analog controller input. Used by UCF dashback code
                `Minimum Replay Version: 1.4.0`:
                    percent : float | None
                        The character's current percent (Min 0.0, Max ~999)
                """

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
                """Enumeration representing the characters current Action State"""
                position: Position
                """X, Y coordinates of the player's in-engine position. Position does not necessarily corrispond to
                the character model."""
                facing_direction: Direction
                """Enumeration with values LEFT and RIGHT. DOWN is used for stats, but also represents the facing
                direction when using the Warp Star item"""
                joystick: Position
                """X, Y coordinates of the player's joystick position"""
                cstick: Position
                """X, Y coordinates of the player's cstick position"""
                triggers: Triggers
                """Contains the physical (controller perspective) and logical (game engine perspective) trigger
                values"""
                buttons: Buttons
                """Contains the physical (controller perspective) and logical (game engine perspective)
                button values. Also contains generalized stick/trigger values"""
                random_seed: int
                """Random seed value used for the upcoming physics calculation"""
                raw_analog_x: int | None
                """Raw X axis analog controller input. Used by UCF dashback code"""
                percent: float | None
                """The character's current percent (Min 0.0, Max ~999)"""

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

                Information is collected at the end of collision detection, which is the last consideration of the game
                engine.

                Attributes:
                    character : InGameCharacter
                        Which character is active on the current frame (should only change for zelda/shiek)
                    state : ActionState | int
                        Enumeration representing the characters current Action State
                    position : Position
                        X, Y coordinates of the player's in-engine position. Position does not necessarily corrispond to
                        the character model.
                    facing_direction : Direction
                        Enumeration with values LEFT and RIGHT. DOWN is used for stats, but also represents the facing
                        direction when using the Warp Star item
                    percent : float
                        The player's current percent (Min 0.0, Max ~999)
                    shield_size : float
                        The remaining health of the player's shield (Max 60.0)
                    stocks_remaining : int
                        The number of stocks remaining. Will be 0 for 1 frame if player loses all stocks in 1v1
                    most_recent_hit : Attack | int
                        The last attack that this character landed, directly corresponds to stale move queue
                    last_hit_by : int | None
                        0-indexed port of the character that last hit this character
                    combo_count : int
                        Current combo count as defined by the game
                `Minimum Replay Version: 0.2.0`:
                    state_age : float | None
                        Number of frames the current action state has been active. Can be fractional
                `Minimum Replay Version: 2.0.0`:
                    flags : list[IntFlag]
                        Sequence of 5 bitfields with values pertaining to the character's current state
                    misc_timer : float | None
                        Timer used by various states. If HITSTUN flag is active, this timer is the number of hitstun
                        frames remaining
                    is_airborne : bool | None
                        True if the character is in the air
                    last_ground_id : int | None
                        In-game ID of the last ground the character stood on
                    jumps_remaining : int | None
                        The number of jumps remaining. Grounded jumps count (e.g. most characters: 2 when grounded,
                        1 when airborne, 0 after double jumping)
                    l_cancel : LCancel | None
                        Enumeration representing current L cancel status. LCancel.SUCCESS or LCancel.FAILURE
                        for 1 frame upon landing during an aerial, otherwise LCancel.NOTAPPLICABLE
                `Minimum Replay Version: 2.1.0`:
                    hurtbox_status : Hurtbox | None
                        VULNERABLE, INVULNERABLE, or INTANGIBLE
                `Minimum Replay Version: 3.5.0`:
                    self_ground_speed : Velocity | None
                        Player-induced X,Y ground speed. Added to knockback speed to calculate next position. Used when
                        `is_airborne` is False. Y ground speed is relevant on slopes
                    self_air_speed : Velocity | None
                        Player-induced X,Y air speed. Added to knockback speed to calculate next position. Used when
                        `is_airborne` is True
                    knockback_speed : Velocity | None
                        X,Y knockback speed. Added to self speeds to calculate next position.
                    hitlag_remaining : float | None
                        Total number of hitlag frames remaining. Can have a fractional component. 0 = not in hitstun
                    animation_index : int | None
                        Indicates the animation the character is in, animation derived from state
                """

                __slots__ = (
                    "character",
                    "state",
                    "position",
                    "facing_direction",
                    "percent",
                    "shield_health",
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

                character: InGameCharacter
                """Which character is active on the current frame (should only change for zelda/shiek)"""
                state: ActionState | int
                """Enumeration representing the characters current Action State. Includes character specific action
                states"""
                position: Position
                """X, Y coordinates of the player's in-engine position. Position does not necessarily corrispond to
                the character model."""
                facing_direction: Direction
                """Enumeration with values LEFT and RIGHT. DOWN is used for stats, but also represents the facing
                direction when using the Warp Star item"""
                percent: float
                """The player's current percent (Min 0.0, Max ~999)"""
                shield_health: float
                """The remaining health of the player's shield (Max 60.0)"""
                stocks_remaining: int
                """The number of stocks remaining. Will be 0 for 1 frame if player loses all stocks in 1v1"""
                most_recent_hit: Attack | int
                """The last attack that this character landed, directly corresponds to stale move queue"""
                last_hit_by: int | None
                """0-indexed port of the character that last hit this character"""
                combo_count: int
                """Current combo count as defined by the game"""
                state_age: float | None
                """Number of frames the current action state has been active. Can be fractional"""
                flags: list[IntFlag] | None
                """Sequence of 5 bitfields with values pertaining to the character's current state"""
                misc_timer: float | None
                """Timer used by various states. If HITSTUN flag is active, this timer is the number of hitstun
                frames remaining"""
                is_airborne: bool | None
                """True if the character is in the air"""
                last_ground_id: int | None
                """In-game ID of the last ground the character stood on"""
                jumps_remaining: int | None
                """The number of jumps remaining. Grounded jumps count (e.g. most characters: 2 when grounded,
                1 when airborne, 0 after double jumping)"""
                l_cancel: LCancel | None
                """Enumeration representing current L cancel status. LCancel.SUCCESS or LCancel.FAILURE
                for 1 frame upon landing during an aerial, otherwise LCancel.NOTAPPLICABLE"""
                hurtbox_status: Hurtbox | None
                """VULNERABLE, INVULNERABLE, or INTANGIBLE"""
                self_ground_speed: Velocity | None
                """Player-induced X,Y ground speed. Added to knockback speed to calculate next position. Used when
                `is_airborne` is False. Y ground speed is relevant on slopes"""
                self_air_speed: Velocity | None
                """Player-induced X,Y air speed. Added to knockback speed to calculate next position. Used when
                `is_airborne` is True"""
                knockback_speed: Velocity | None
                """X,Y knockback speed. Added to self speeds to calculate next position."""
                hitlag_remaining: float | None
                """Total number of hitlag frames remaining. Can have a fractional component. 0 = not in hitstun"""
                animation_index: int | None
                """Indicates the animation the character is in, animation derived from state"""

                def __init__(
                    self,
                    character: InGameCharacter,
                    state: ActionState | int,
                    position: Position,
                    direction: Direction,
                    damage: float,
                    shield_health: float,
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
                    self.shield_health = shield_health
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
                ):
                    read = stream.read
                    character = try_enum(InGameCharacter, *unpack_uint8(read(1)))
                    state = get_character_state(*unpack_uint16(read(2)), character)
                    position = Position(*unpack_float(read(4)), *unpack_float(read(4)))
                    direction = Direction(*unpack_float(read(4)))
                    (damage,) = unpack_float(read(4))
                    (shield_health,) = unpack_float(read(4))
                    last_attack_landed = try_enum(Attack, *unpack_uint8(read(1)))
                    (combo_count,) = unpack_uint8(read(1))
                    (last_hit_by,) = unpack_uint8(read(1))
                    (stocks,) = unpack_uint8(read(1))

                    # There's a lot of return repetition, but this essentially prevents old replays from getting
                    # progressively slower over time. Post-frames are a hot path, so we want to keep them as fast as
                    # possible. Try is almost free, except is about 5x slower than an if (and ifs have a noticeable
                    # impact on parsing speed). By returning, we prevent old replays from excepting more than once.

                    # All struct errors should be due to stream.read running out of bytes, indicating an older replay
                    # with a shorter post-frame payload

                    # v0.2.0
                    try:
                        (state_age,) = unpack_float(read(4))
                    except struct.error:
                        return cls(
                            character=character,
                            state=state,
                            state_age=state_age,
                            position=position,
                            direction=direction,
                            damage=damage,
                            shield_health=shield_health,
                            stocks=stocks,
                            most_recent_hit=last_attack_landed,
                            last_hit_by=last_hit_by if last_hit_by < 4 else None,
                            combo_count=combo_count,
                        )

                    try:  # v2.0.0
                        flags = [
                            Field1(*unpack_uint8(read(1))),
                            Field2(*unpack_uint8(read(1))),
                            Field3(*unpack_uint8(read(1))),
                            Field4(*unpack_uint8(read(1))),
                            Field5(*unpack_uint8(read(1))),
                        ]

                        (misc_timer,) = unpack_float(read(4))
                        (airborne,) = unpack_bool(read(1))
                        (last_ground_id,) = unpack_uint16(read(2))
                        (jumps,) = unpack_uint8(read(1))
                        l_cancel = LCancel(*unpack_uint8(read(1)))

                    except struct.error:
                        return cls(
                            character=character,
                            state=state,
                            state_age=state_age,
                            position=position,
                            direction=direction,
                            damage=damage,
                            shield_health=shield_health,
                            stocks=stocks,
                            most_recent_hit=last_attack_landed,
                            last_hit_by=last_hit_by if last_hit_by < 4 else None,
                            combo_count=combo_count,
                        )

                    try:  # v2.1.0
                        (hurtbox_status,) = unpack_uint8(read(1))
                    except struct.error:
                        return cls(
                            character=character,
                            state=state,
                            state_age=state_age,
                            position=position,
                            direction=direction,
                            damage=damage,
                            shield_health=shield_health,
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
                        )

                    try:  # v3.5.0
                        self_air_speed = Velocity(*unpack_float(read(4)), *unpack_float(read(4)))
                        knockback_speed = Velocity(*unpack_float(read(4)), *unpack_float(read(4)))
                        self_ground_speed = Velocity(*unpack_float(read(4)), self_air_speed.y)

                    except struct.error:
                        return cls(
                            character=character,
                            state=state,
                            state_age=state_age,
                            position=position,
                            direction=direction,
                            damage=damage,
                            shield_health=shield_health,
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
                        )

                    try:  # v3.8.0
                        (hitlag_remaining,) = unpack_float(read(4))
                    except struct.error:
                        return cls(
                            character=character,
                            state=state,
                            state_age=state_age,
                            position=position,
                            direction=direction,
                            damage=damage,
                            shield_health=shield_health,
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
                        )

                    try:  # v3.11.0
                        (animation_index,) = unpack_uint32(read(4))
                    except struct.error:
                        return cls(
                            character=character,
                            state=state,
                            state_age=state_age,
                            position=position,
                            direction=direction,
                            damage=damage,
                            shield_health=shield_health,
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
                        )

                    return cls(
                        character=character,
                        state=state,
                        state_age=state_age,
                        position=position,
                        direction=direction,
                        damage=damage,
                        shield_health=shield_health,
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
        """An active item (includes projectiles).

        Attributes:
            type : Item
                What type of item this data is for (turnip, missile, pokeball, etc.)
            state : int
                Item's action state
            facing_direction : Direction
                    Enumeration with values LEFT and RIGHT. DOWN is used for stats, but also represents the facing
                    direction when using the Warp Star item
            velocity : Velocity
                Item's X,Y velocity
            position : Position
                Item's X,Y position
            damage_taken : int
                Amount of damage item has taken
            timer : int
                Frames remaining until item expires
            spawn_id : int
                Unique ID per item spawned (0, 1, 2, ...)
            missile_type : MissileType | None
                Used for Samus side B missiles. See MissileType Enumeration
            turnip_type: TurnipFace | None
                Used for Peach's down B turnips. See TurnipFace Enumeration
            is_shot_launched: bool | None
                Differentiates between charge shots that are on-screen but held, and charge shots have been launched
            charge_power: int | None
                Integer value for total charge shot power.
            owner: Port | int | None
                Item owner by port
        """

        __slots__ = (
            "type",
            "state",
            "facing_direction",
            "velocity",
            "position",
            "damage_taken",
            "timer",
            "spawn_id",
        )

        type: Item  # Item type
        state: int  # Item's action state
        facing_direction: Direction | None  # Direction item is facing
        velocity: Velocity  # Item's velocity
        position: Position  # Item's position
        damage_taken: int  # Amount of damage item has taken
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
            facing_direction: Direction | None,
            velocity: Velocity,
            position: Position,
            damage_taken: int,
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
            self.facing_direction = facing_direction
            self.velocity = velocity
            self.position = position
            self.damage_taken = damage_taken
            self.timer = timer
            self.spawn_id = spawn_id
            self.missile_type = missile_type
            self.turnip_type = turnip_type
            self.is_shot_launched = is_shot_launched
            self.charge_power = charge_power
            self.owner = owner

        @classmethod
        def _parse(cls, stream: io.BytesIO, unpack_float=unpack_float, unpack_uint8=unpack_uint8):
            type = try_enum(Item, *unpack_uint16(stream.read(2)))
            (state,) = unpack_uint8(stream.read(1))
            facing_direction = Direction(*unpack_float(stream.read(4)))
            velocity = Velocity(*unpack_float(stream.read(4)), *unpack_float(stream.read(4)))
            position = Position(*unpack_float(stream.read(4)), *unpack_float(stream.read(4)))
            (damage_taken,) = unpack_uint16(stream.read(2))
            (timer,) = unpack_float(stream.read(4))
            (spawn_id,) = unpack_uint32(stream.read(4))

            try:
                (missile_type,) = unpack_uint8(stream.read(1))
                (turnip_type,) = unpack_uint8(stream.read(1))
                (is_shot_launched,) = unpack_uint8(stream.read(1))
                (charge_power,) = unpack_uint8(stream.read(1))
                owner = Port(*unpack_int8(stream.read(1)))
                missile_type = try_enum(MissileType, missile_type) if type == Item.SAMUS_MISSILE else missile_type
                turnip_type = try_enum(TurnipFace, turnip_type) if type == Item.PEACH_TURNIP else turnip_type
            except struct.error:
                missile_type = None
                turnip_type = None
                is_shot_launched = None
                charge_power = None
                owner = None

            return cls(
                type=type,
                state=state,
                facing_direction=facing_direction,
                velocity=velocity,
                position=position,
                damage_taken=damage_taken,
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
                and self.facing_direction == other.facing_direction
                and self.velocity == other.velocity
                and self.position == other.position
                and self.damage_taken == other.damage_taken
                and self.timer == other.timer
                and self.spawn_id == other.spawn_id
            )

    class Start(Base):
        """Start-of-frame data.

        Attributes:
            random_seed : int
                random seed value at the beginning of the frame"""

        __slots__ = ("random_seed",)

        random_seed: int  # The random seed at the start of the frame

        def __init__(self, random_seed: int):
            self.random_seed = random_seed

        @classmethod
        def _parse(cls, stream: io.BytesIO):
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
        def _parse(cls, stream: io.BytesIO):
            return cls()

        def __eq__(self, other):
            if not isinstance(other, self.__class__):
                return NotImplemented
            return True

    class Event(Base):
        """Temporary wrapper used while parsing frame data."""

        __slots__ = "id", "type", "data"

        def __init__(self, id: Id | PortId, type: Type, data: io.BytesIO):
            self.id = id
            self.type = type
            self.data = data

        class Id(Base):
            __slots__ = ("frame",)

            def __init__(self, stream: io.BytesIO):
                (self.frame,) = unpack_int32(stream.read(4))

        class PortId(Id):
            __slots__ = "port", "is_follower"

            def __init__(self, stream: io.BytesIO):
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
    """Coordinate position for characters and analog stick values

    Attributes:
        x : float
            horizontal component
        y : float
            vertical component
    """

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
    """Velocity in the form of X and Y

    Attributes:
        x : float
            horizontal component
        y : float
            vertical component
    """

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
