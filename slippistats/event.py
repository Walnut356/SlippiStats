from __future__ import annotations

import struct
from enum import IntFlag
from typing import Optional, Sequence, Union

from .controller import Buttons, Triggers
from .enums.attack import Attack
from .enums.character import CSSCharacter, InGameCharacter
from .enums.item import Item, TurnipFace
from .enums.stage import Stage
from .enums.state import (
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

class MatchType(Enum):
    OFFLINE = -1
    RANKED = 0
    UNRANKED = 1
    DIRECT = 2
    OTHER = 3


#TODO make as many of these as possible dataclasses/recordclasses.
class Start(Base):
    """Information used to initialize the game such as the game mode, settings, characters & stage."""

    is_teams: bool  #: True if this was a teams game
    players: tuple[Optional[Start.Player]]  #: Players in this game by port (port 1 is at index 0; empty ports will contain None)
    random_seed: int  #: Random seed before the game start
    slippi_version: Start.SlippiVersion  #: Information about the Slippi recorder that generated this replay
    stage: Stage  #: Stage on which this game was played
    is_pal: Optional[bool]  #: `added(1.5.0)` True if this was a PAL version of Melee
    is_frozen_ps: Optional[bool]  #: `added(2.0.0)` True if frozen Pokemon Stadium was enabled
    match_id: Optional[str]  #: `added(3.14.0)` Mode (ranked/unranked) and time the match started
    match_type: bool
    game_number: Optional[int]  #: `added(3.14.0)` The game number for consecutive games
    tiebreak_number: Optional[int]

    def __init__(
            self,
            is_teams: bool,
            players: tuple[Optional[Start.Player]],
            random_seed: int,
            slippi: Start.SlippiVersion,
            stage: Stage,
            is_pal: Optional[bool] = None,
            is_frozen_ps: Optional[bool] = None,
            match_id: Optional[str] = None,
            game_number: Optional[int] = None,
            tiebreak_number: Optional[int] = None
        ):
        self.is_teams = is_teams
        self.players = players
        self.random_seed = random_seed
        self.slippi_version = slippi
        self.stage = stage
        self.is_pal = is_pal
        self.is_frozen_ps = is_frozen_ps
        self.match_id = match_id
        if match_id: #it's lazy, but it works
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
        players = []
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

            if type is not None:
                character = CSSCharacter(character)
                team = cls.Player.Team(team) if is_teams else None
                player = cls.Player(character=character, type=type, stocks=stocks, costume=costume, team=team)
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
                    players[i].tag = tag_bytes.decode('shift-jis').rstrip()
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
            match_id = str(match_id.decode('utf-8')).rstrip('\x00')
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
            tiebreak_number=tiebreak_number
            )

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return (
            self.is_teams == other.is_teams and self.players == other.players and self.random_seed == other.random_seed and
            self.slippi_version == other.slippi_version and self.stage is other.stage
            )

    class SlippiVersion(Base):
        """Information about the Slippi recorder that generated this replay."""
        #TODO flatten to Slippi_Version

        major: int
        minor: int
        revision: int

        def __init__(self, major: int, minor: int, revision: int=0, build=None):
            self.major = major
            self.minor = minor
            self.revision = revision
            # build was obsoleted in 2.0.0 and never held a nonzero value.

        @classmethod
        def _parse(cls, stream):
            # unpack returns a tuple, so we need to flatten the list. Additionally, we need to splat it to send to the constructor
            # I try not to use this too often because it's annoying to read if you don't already know what it does
            return cls(*[tup[0] for tup in [unpack_uint8(stream.read(1)) for i in range(4)]])

        def __repr__(self):
            return f'{self.major}.{self.minor}.{self.revision}'

        def __eq__(self, other: Start.SlippiVersion | str):
            if isinstance(other, self.__class__):
                return self.major == other.major and self.minor == other.minor and self.revision == other.revision

            if isinstance(other, str):
                major, minor, revision = [int(n) for n in other.split(".", 2)]
                return self.major == major and self.minor == minor and self.revision == revision

            raise NotImplementedError(
                "Incorrect type for comparison to event.Start.Slippi, accepted types are event.Start.Slippi, event.Start.Slippi.Version, and str"
                )

        def __ge__(self, other: Start.SlippiVersion | str):
            if isinstance(other, self.__class__):
                # Can't rely on short circuiting, example: 2.11.0 would evaluate as greater than 3.9.0, so we need a smarter check
                if self.major > other.major:
                    return True
                if self.major == other.major:
                    if self.minor > other.minor:
                        return True
                    if self.minor == other.minor:
                        if self.revision >= other.revision:
                            return True
                return False

            if isinstance(other, str):
                major, minor, revision = [int(n) for n in other.split(".", 2)]
                if self.major > major:
                    return True
                if self.major == major:
                    if self.minor > minor:
                        return True
                    if self.minor == minor:
                        if self.revision >= revision:
                            return True
                return False

            raise NotImplementedError(
                "Incorrect type for comparison to event.Start.Slippi, accepted types are event.Start.Slippi, event.Start.Slippi.Version, and str"
                )

        def __lt__(self, other: Start.SlippiVersion | Start.SlippiVersion | str):
            return not self.__ge__(other)


    class Player(Base):
        """Contains metadata about the player from the console's perspective including:
        character, starting stock count, costume, team, in-game tag, and UCF toggles"""
        character: CSSCharacter  #: Character selected
        type: Start.Player.Type  #: Player type (human/cpu)
        stocks: int  #: Starting stock count
        costume: int  #: Costume ID
        team: Optional[Start.Player.Team]  #: Team, if this was a teams game
        ucf: Optional[Start.Player.UCF]  #: UCF feature toggles
        tag: Optional[str]  #: Name tag

        def __init__(
                self,
                character: CSSCharacter,
                type: Start.Player.Type,
                stocks: int,
                costume: int,
                team: Optional[Start.Player.Team],
                ucf: Optional[Start.Player.UCF] = None,
                tag: Optional[str] = None
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
                self.character is other.character and self.type is other.type and self.stocks == other.stocks and
                self.costume == other.costume and self.team is other.team and self.ucf == other.ucf
                )

        class Type(IntEnum):
            """Human vs CPU"""
            HUMAN = 0
            CPU = 1

        class Team(IntEnum):
            """Doubles team colors"""
            RED = 0
            BLUE = 1
            GREEN = 2

        class UCF(Base):
            """UCF Dashback and shield drop, off, on, or arduino"""
            dash_back: Optional[Start.Player.UCF.DashBack]  #: UCF dashback status
            shield_drop: Optional[Start.Player.UCF.ShieldDrop]  #: UCF shield drop status

            def __init__(
                    self, dash_back: Optional[Start.Player.UCF.DashBack] = None, shield_drop: Optional[Start.Player.UCF.ShieldDrop] = None
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

    method: End.Method  #: `changed(2.0.0)` How the game ended
    lras_initiator: Optional[int]  #: `added(2.0.0)` Index of player that LRAS'd, if any
    # Player placements stored as a list. The index represents the port, the value of that element is their placement.
    player_placements: Optional[list[int]]  #: `added (3.13.0)` 0-indexed placement positions. -1 if player not in game

    def __init__(self, method: End.Method, lras_initiator: Optional[int] = None, player_placements: Optional[list[int]] = None):
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

    __slots__ = 'index', 'ports', 'items', 'start', 'end'

    index: int
    ports: Sequence[Optional[Frame.Port]]  #: Frame data for each port (port 1 is index 0; empty ports will contain None)
    items: Sequence[Frame.Item]  #: `added(3.0.0)` Active items (includes projectiles)
    start: Optional[Frame.Start]  #: `added(2.2.0)` Start-of-frame data
    end: Optional[Frame.End]  #: `added(2.2.0)` End-of-frame data

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

        __slots__ = 'leader', 'follower'

        leader: Frame.Port.Data  #: Frame data for the controlled character
        follower: Optional[Frame.Port.Data]  #: Frame data for the follower (Nana), if any

        def __init__(self):
            self.leader = self.Data()
            self.follower = None

        class Data(Base):
            """Frame data for a given character. Includes both pre-frame and post-frame data."""

            __slots__ = '_pre', '_post'



            def __init__(self):
                self._pre = None
                self._post = None

            #TODO i think these are used for live parsing? IDC about live parsing so I think i can just rip all this out
            #should make member access a tiny bit faster
            @property
            def pre(self) -> Optional[Frame.Port.Data.Pre]:
                """Pre-frame update data"""
                if self._pre and not isinstance(self._pre, self.Pre):
                    self._pre = self.Pre._parse(self._pre)
                return self._pre

            @property
            def post(self) -> Optional[Frame.Port.Data.Post]:
                """Post-frame update data"""
                if self._post and not isinstance(self._post, self.Post):
                    self._post = self.Post._parse(self._post)
                return self._post

            class Pre(Base):
                """Pre-frame update data, required to reconstruct a replay. Information is collected right before
                controller inputs are used to figure out the character's next action."""

                __slots__ = 'state', 'position', 'facing_direction', 'joystick', 'cstick', 'triggers', 'buttons',\
                'random_seed', 'raw_analog_x', 'percent'

                state: Union[ActionState, int]
                position: Position
                facing_direction: Direction
                joystick: Position
                cstick: Position
                triggers: Triggers
                buttons: Buttons
                random_seed: int
                raw_analog_x: Optional[int]
                percent: Optional[float]

                def __init__(
                        self,
                        state: Union[ActionState, int],
                        position: Position,
                        direction: Direction,
                        joystick: Position,
                        cstick: Position,
                        triggers: Triggers,
                        buttons: Buttons,
                        random_seed: int,
                        raw_analog_x: Optional[int] = None,
                        damage: Optional[float] = None
                    ):
                    self.state = state  #: :py:class:`slippi.id.ActionState` | int: Character's action state
                    self.position = position  #: :py:class:`Position`: Character's position
                    self.facing_direction = direction  #: :py:class:`Direction`: Direction the character is facing
                    self.joystick = joystick  #: :py:class:`Position`: Processed analog joystick position
                    self.cstick = cstick  #: :py:class:`Position`: Processed analog c-stick position
                    self.triggers = triggers  #: :py:class:`Triggers`: Trigger state
                    self.buttons = buttons  #: :py:class:`Buttons`: Button state
                    self.random_seed = random_seed  #: int: Random seed at this point
                    self.raw_analog_x = raw_analog_x  #: int | None: `added(1.2.0)` Raw x analog controller input (for UCF)
                    self.percent = damage  #: float | None: `added(1.4.0)` Current damage percent

                @classmethod
                def _parse(cls, stream):
                    (random_seed,) = unpack_uint32(stream.read(4))
                    (state,) = unpack_uint16(stream.read(2))
                    (position_x,) = unpack_float(stream.read(4))
                    (position_y,) = unpack_float(stream.read(4))
                    (direction,) = unpack_float(stream.read(4))
                    (joystick_x,) = unpack_float(stream.read(4))
                    (joystick_y,) = unpack_float(stream.read(4))
                    (cstick_x,) = unpack_float(stream.read(4))
                    (cstick_y,) = unpack_float(stream.read(4))
                    (trigger_logical,) = unpack_float(stream.read(4))
                    (buttons_logical,) = unpack_uint32(stream.read(4))
                    (buttons_physical,) = unpack_uint16(stream.read(2))
                    (trigger_physical_l,) = unpack_float(stream.read(4))
                    (trigger_physical_r,) = unpack_float(stream.read(4))

                    # v1.2.0
                    try:
                        (raw_analog_x,) = unpack_uint8(stream.read(1))
                    except struct.error:
                        raw_analog_x = None

                    # v1.4.0
                    try:
                        (damage,) = unpack_float(stream.read(4))
                    except struct.error:
                        damage = None

                    return cls(
                        state=try_enum(ActionState, state),
                        position=Position(position_x, position_y),
                        direction=Direction(direction),
                        joystick=Position(joystick_x, joystick_y),
                        cstick=Position(cstick_x, cstick_y),
                        triggers=Triggers(trigger_logical, trigger_physical_l, trigger_physical_r),
                        buttons=Buttons(buttons_logical, buttons_physical),
                        random_seed=random_seed,
                        raw_analog_x=raw_analog_x,
                        damage=damage
                        )

            class Post(Base):
                """Post-frame update data, for making decisions about game states (such as computing stats).
                Information is collected at the end of collision detection, which is the last consideration of the game engine."""

                __slots__ = (
                    'character', 'state', 'position', 'facing_direction', 'percent', 'shield_size', 'stocks_remaining', 'most_recent_hit',
                    'last_hit_by', 'combo_count', 'state_age', 'flags', 'misc_timer', 'is_airborne', 'last_ground_id',
                    'jumps_remaining', 'l_cancel', 'hurtbox_status', 'self_ground_speed', 'self_air_speed', 'knockback_speed',
                    'hitlag_remaining', 'animation_index'
                    )

                character: InGameCharacter  # In-game character (can only change for Zelda/Sheik).
                state: Union[ActionState, int]  # Character's action state
                position: Position  # Character's position
                facing_direction: Direction  # Direction the character is facing
                percent: float  # Current damage percent
                shield_size: float  # Current size of shield
                stocks_remaining: int  # Number of stocks remaining
                most_recent_hit: Union[Attack, int]  # Last attack that this character landed
                last_hit_by: Optional[int]  # Port of character that last hit this character
                combo_count: int  # Combo count as defined by the game
                state_age: Optional[float]  # Number of frames action state has been active. Can be fractional for certain actions
                flags: Optional[list[IntFlag]]  # State flags
                misc_timer: Optional[float]  # hitstun frames remaining
                is_airborne: Optional[bool]  # True if character is airborne
                last_ground_id: Optional[int]  # ID of ground character is standing on, if any
                jumps_remaining: Optional[int]  # Jumps remaining
                l_cancel: Optional[LCancel]  # L-cancel status, if any
                hurtbox_status: Optional[Hurtbox]
                # speeds are split into 5 values. A shared Y, a grounded and air X, and a knockback X and Y. Generic Y *DOES* matter
                # even when grounded. For example, watch velocity values when walking on the slanted edges of yoshi's
                self_ground_speed: Optional[Velocity]  # Self induced ground X speed and generic Y speed
                self_air_speed: Optional[Velocity]  # Self induced air X speed and generic Y speed
                knockback_speed: Optional[Velocity]  # Speed from knockback, adds with self-speeds for total velocity
                hitlag_remaining: Optional[float]  # 0 means "not in hitlag"
                animation_index: Optional[int]  # Indicates the animation the character is in, animation derived from state.

                def __init__(
                        self,
                        character: InGameCharacter,
                        state: Union[ActionState, int],
                        position: Position,
                        direction: Direction,
                        damage: float,
                        shield: float,
                        stocks: int,
                        most_recent_hit: Union[Attack, int],
                        last_hit_by: Optional[int],
                        combo_count: int,
                        state_age: Optional[float] = None,
                        flags: Optional[list[IntEnum]] = None,
                        misc_timer: Optional[float] = None,
                        airborne: Optional[bool] = None,
                        ground: Optional[int] = None,
                        jumps: Optional[int] = None,
                        l_cancel: Optional[LCancel] = None,
                        hurtbox_status: Optional[Hurtbox] = None,
                        self_ground_speed: Optional[Velocity] = None,
                        self_air_speed: Optional[Velocity] = None,
                        knockback_speed: Optional[Velocity] = None,
                        hitlag_remaining: Optional[float] = None,
                        animation_index: Optional[int] = None
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
                    self.last_ground_id = ground
                    self.jumps_remaining = jumps
                    self.l_cancel = l_cancel
                    self.hurtbox_status = hurtbox_status
                    self.self_ground_speed = self_ground_speed
                    self.self_air_speed = self_air_speed
                    self.knockback_speed = knockback_speed
                    self.hitlag_remaining = hitlag_remaining
                    self.animation_index = animation_index

                @classmethod
                def _parse(cls, stream):
                    (character,) = unpack_uint8(stream.read(1))
                    (state,) = unpack_uint16(stream.read(2))
                    (position_x,) = unpack_float(stream.read(4))
                    (position_y,) = unpack_float(stream.read(4))
                    (direction,) = unpack_float(stream.read(4))
                    (damage,) = unpack_float(stream.read(4))
                    (shield,) = unpack_float(stream.read(4))
                    (last_attack_landed,) = unpack_uint8(stream.read(1))
                    (combo_count,) = unpack_uint8(stream.read(1))
                    (last_hit_by,) = unpack_uint8(stream.read(1))
                    (stocks,) = unpack_uint8(stream.read(1))

                    # v0.2.0
                    try:
                        (state_age,) = unpack_float(stream.read(4))
                    except struct.error:
                        state_age = None

                    try:  # v2.0.0
                        # unpack returns a tuple, so we need to flatten the list.
                        # I try not to use this too often because it's annoying to read if you don't already know what it does
                        flags = [tup[0] for tup in [unpack_uint8(stream.read(1)) for i in range(5)]]

                        (misc_timer,) = unpack_float(stream.read(4))
                        (airborne,) = unpack_bool(stream.read(1))
                        (maybe_ground,) = unpack_uint16(stream.read(2))
                        (jumps,) = unpack_uint8(stream.read(1))
                        (l_cancel,) = unpack_uint8(stream.read(1))

                        flags = [Field1(flags[0]),
                                Field2(flags[1]),
                                Field3(flags[2]),
                                Field4(flags[3]),
                                Field5(flags[4])]
                        ground = maybe_ground
                        misc_timer = misc_timer
                        l_cancel = LCancel(l_cancel)
                    except struct.error:
                        (flags, misc_timer, airborne, ground, jumps, l_cancel) = [None] * 6

                    try:  # v2.1.0
                        (hurtbox_status,) = unpack_uint8(stream.read(1))
                    except struct.error:
                        hurtbox_status = None

                    try:  # v3.5.0
                        (self_air_x,) = unpack_float(stream.read(4))
                        (self_y,) = unpack_float(stream.read(4))
                        (kb_x,) = unpack_float(stream.read(4))
                        (kb_y,) = unpack_float(stream.read(4))
                        (self_ground_x,) = unpack_float(stream.read(4))

                        self_ground_speed = Velocity(self_ground_x, self_y)
                        self_air_speed = Velocity(self_air_x, self_y)
                        knockback_speed = Velocity(kb_x, kb_y)
                    except struct.error:
                        (self_ground_speed, self_air_speed, knockback_speed) = [None] * 3

                    try:  # v3.8.0
                        (hitlag_remaining,) = unpack_float(stream.read(4))
                    except struct.error:
                        hitlag_remaining = None

                    try:  # v3.11.0
                        (animation_index,) = unpack_uint32(stream.read(4))
                    except struct.error:
                        animation_index = None

                    return cls(
                        character=InGameCharacter(character),
                        state=try_enum(ActionState, state),
                        state_age=state_age,
                        position=Position(position_x, position_y),
                        direction=Direction(direction),
                        damage=damage,
                        shield=shield,
                        stocks=stocks,
                        most_recent_hit=try_enum(Attack, last_attack_landed),
                        last_hit_by=last_hit_by if last_hit_by < 4 else None,
                        combo_count=combo_count,
                        flags=flags,
                        misc_timer=misc_timer,
                        airborne=airborne,
                        ground=ground,
                        jumps=jumps,
                        l_cancel=l_cancel,
                        hurtbox_status=hurtbox_status,
                        self_ground_speed=self_ground_speed,
                        self_air_speed=self_air_speed,
                        knockback_speed=knockback_speed,
                        hitlag_remaining=hitlag_remaining,
                        animation_index=animation_index
                        )

    class Item(Base):
        """An active item (includes projectiles)."""

        __slots__ = 'type', 'state', 'direction', 'velocity', 'position', 'damage', 'timer', 'spawn_id'

        type: Item  #: Item type
        state: int  #: Item's action state
        direction: Optional[Direction]  #: Direction item is facing
        velocity: Velocity  #: Item's velocity
        position: Position  #: Item's position
        damage: int  #: Amount of damage item has taken
        timer: int  #: Frames remaining until item expires
        spawn_id: int  #: Unique ID per item spawned (0, 1, 2, ...)
        missile_type: Optional[int]
        turnip_type: Optional[TurnipFace]
        is_shot_launched: Optional[bool]
        charge_power: Optional[int]
        owner: Optional[int]

        def __init__(
                self, type: Item, state: int, direction: Optional[Direction], velocity: Velocity, position: Position, damage: int,
                timer: int, spawn_id: int, missile_type: Optional[int], turnip_type: Optional[TurnipFace], is_shot_launched: Optional[bool],
                charge_power: Optional[int], owner: Optional[int]
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
                turnip_type=try_enum(TurnipFace, turnip_type),
                is_shot_launched=is_shot_launched,
                charge_power=charge_power,
                owner=owner
                )

        def __eq__(self, other):
            if not isinstance(other, self.__class__):
                return NotImplemented
            return (
                self.type == other.type and self.state == other.state and self.direction == other.direction and
                self.velocity == other.velocity and self.position == other.position and self.damage == other.damage and
                self.timer == other.timer and self.spawn_id == other.spawn_id
                )

    class Start(Base):
        """Start-of-frame data."""

        __slots__ = ('random_seed',)

        random_seed: int  #: The random seed at the start of the frame

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

        __slots__ = 'id', 'type', 'data'

        def __init__(self, id, type, data):
            self.id = id
            self.type = type
            self.data = data

        class Id(Base):
            __slots__ = ('frame',)

            def __init__(self, stream):
                (self.frame,) = unpack_int32(stream.read(4))

        class PortId(Id):
            __slots__ = 'port', 'is_follower'

            def __init__(self, stream):
                (self.frame,) = unpack_int32(stream.read(4))
                (self.port,) = unpack_uint8(stream.read(1))
                (self.is_follower,) = unpack_bool(stream.read(1))

        class Type(Enum):
            START = 'start'
            END = 'end'
            PRE = 'pre'
            POST = 'post'
            ITEM = 'item'


class Position(Base):
    __slots__ = 'x', 'y'

    x: float
    y: float

    def __init__(self, x: float, y: float):
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
        return f'({self.x:.2f}, {self.y:.2f})'


class Velocity(Base):
    __slots__ = 'x', 'y'

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

    def __repr__(self):
        return f'({self.x:.2f}, {self.y:.2f})'
