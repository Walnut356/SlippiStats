from __future__ import annotations
from enum import IntFlag

from typing import Optional, Sequence, Tuple, Union, List

from .enums import (ActionState,
                    Stage,
                    CSSCharacter,
                    InGameCharacter,
                    Item,
                    TurnipFace,
                    Attack)

from .util import *

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


class Start(Base):
    """Information used to initialize the game such as the game mode, settings, characters & stage."""

    is_teams: bool #: True if this was a teams game
    players: Tuple[Optional[Start.Player]] #: Players in this game by port (port 1 is at index 0; empty ports will contain None)
    random_seed: int #: Random seed before the game start
    slippi: Start.Slippi #: Information about the Slippi recorder that generated this replay
    stage: Stage #: Stage on which this game was played
    is_pal: Optional[bool] #: `added(1.5.0)` True if this was a PAL version of Melee
    is_frozen_ps: Optional[bool] #: `added(2.0.0)` True if frozen Pokemon Stadium was enabled
    match_id: Optional[str] #: `added(3.14.0)` Mode (ranked/unranked) and time the match started
    is_ranked: bool
    game_number: Optional[int] #: `added(3.14.0)` The game number for consecutive games
    tiebreak_number: Optional[int]

    def __init__(self, is_teams: bool, players: Tuple[Optional[Start.Player]], random_seed: int, slippi: Start.Slippi, stage: Stage,
                 is_pal: Optional[bool] = None, is_frozen_ps: Optional[bool] = None, match_id: Optional[str] = None,
                 game_number: Optional[int] = None, tiebreak_number: Optional[int] = None):
        self.is_teams = is_teams
        self.players = players
        self.random_seed = random_seed
        self.slippi = slippi
        self.stage = stage
        self.is_pal = is_pal
        self.is_frozen_ps = is_frozen_ps
        self.match_id = match_id
        if match_id:
            self.is_ranked = match_id[5] == "r" #it's lazy, but it seems like a waste to import regex for this
        else:
            self.is_ranked = False
        self.game_number = game_number
        self.tiebreak_number = tiebreak_number

    @classmethod
    def _parse(cls, stream):
        slippi_ = cls.Slippi._parse(stream)

        stream.read(8)
        (is_teams,) = unpack('?', stream)

        stream.read(5)
        (stage,) = unpack('H', stream)
        stage = Stage(stage)

        stream.read(80)
        players = []
        for i in PORTS:
            (character, type, stocks, costume) = unpack('BBBB', stream)

            stream.read(5)
            (team,) = unpack('B', stream)
            stream.read(26)

            try: type = cls.Player.Type(type)
            except ValueError: type = None

            if type is not None:
                character = CSSCharacter(character)
                team = cls.Player.Team(team) if is_teams else None
                player = cls.Player(character=character, type=type, stocks=stocks, costume=costume, team=team)
            else:
                player = None

            players.append(player)

        stream.read(72)
        (random_seed,) = unpack('L', stream)

        try: # v1.0.0
            for i in PORTS:
                (dash_back, shield_drop) = unpack('LL', stream)
                dash_back = cls.Player.UCF.DashBack(dash_back)
                shield_drop = cls.Player.UCF.ShieldDrop(shield_drop)
                if players[i]:
                    players[i].ucf = cls.Player.UCF(dash_back, shield_drop)
        except EOFError: pass

        try: # v1.3.0
            for i in PORTS:
                tag_bytes = stream.read(16)
                if players[i]:
                    try:
                        null_pos = tag_bytes.index(0)
                        tag_bytes = tag_bytes[:null_pos]
                    except ValueError: pass
                    players[i].tag = tag_bytes.decode('shift-jis').rstrip()
        except EOFError: pass

        # v1.5.0
        try: (is_pal,) = unpack('?', stream)
        except EOFError: is_pal = None

        # v2.0.0
        try: (is_frozen_ps,) = unpack('?', stream)
        except EOFError: is_frozen_ps = None

        # v3.14.0
        stream.read(283)

        try:
            (match_id,) = unpack('50s', stream)
            match_id = str(match_id.decode('utf-8')).rstrip('\x00')
        except EOFError: match_id = None

        stream.read(1)
        try: (game_number,) = unpack('I', stream)
        except EOFError: game_number = None

        try: (tiebreak_number,) = unpack('I', stream)
        except EOFError: tiebreak_number = None

        return cls(
            is_teams=is_teams,
            players=tuple(players),
            random_seed=random_seed,
            slippi=slippi_,
            stage=stage,
            is_pal=is_pal,
            is_frozen_ps=is_frozen_ps,
            match_id=match_id,
            game_number=game_number,
            tiebreak_number=tiebreak_number)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return (self.is_teams == other.is_teams and
                self.players == other.players and
                self.random_seed == other.random_seed and
                self.slippi == other.slippi and
                self.stage is other.stage)


    class Slippi(Base):
        """Information about the Slippi recorder that generated this replay."""

        version: Start.Slippi.Version #: Slippi version number

        def __init__(self, version: Start.Slippi.Version):
            self.version = version

        @classmethod
        def _parse(cls, stream):
            return cls(cls.Version(*unpack('BBBB', stream)))

        def __eq__(self, other):
            if isinstance(other, self.__class__):
                return self.version == other.version

            if isinstance(other, str) or isinstance(other, Start.Slippi.Version):
                return self.version == other
    
            raise NotImplementedError("Incorrect type for comparison to event.Start.Slippi, accepted types are event.Start.Slippi, event.Start.Slippi.Version, and str")
        
        def __ge__(self, other: Start.Slippi | Start.Slippi.Version | str):
            if isinstance(other, self.__class__):
                return self.version >= other.version

            if isinstance(other, str) or isinstance(other, Start.Slippi.Version):
                return self.version >= other
    
            raise NotImplementedError("Incorrect type for comparison to event.Start.Slippi, accepted types are event.Start.Slippi, event.Start.Slippi.Version, and str")
        
        def __lt__(self, other: Start.Slippi | Start.Slippi.Version | str):
            return not self.__ge__(other)


        class Version(Base):

            major: int
            minor: int
            revision: int

            def __init__(self, major: int, minor: int, revision: int, build = None):
                self.major = major
                self.minor = minor
                self.revision = revision
                # build was obsoleted in 2.0.0, and never held a nonzero value

            def __repr__(self):
                return '%d.%d.%d' % (self.major, self.minor, self.revision)

            def __eq__(self, other: Start.Slippi.Version | str ):
                if isinstance(other, self.__class__):
                    return self.major == other.major and self.minor == other.minor and self.revision == other.revision

                if isinstance(other, str):
                    major, minor, revision = [int(n) for n in other.split(".", 2)]
                    return self.major == major and self.minor == minor and self.revision == revision

                raise NotImplementedError("Incorrect type for comparison to event.Start.Slippi, accepted types are event.Start.Slippi, event.Start.Slippi.Version, and str")
            
            def __ge__(self, other: Start.Slippi.Version | str ):
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
                
                raise NotImplementedError("Incorrect type for comparison to event.Start.Slippi, accepted types are event.Start.Slippi, event.Start.Slippi.Version, and str")


    class Player(Base):
        """Contains metadata about the player from the console's perspective including:
        character, starting stock count, costume, team, in-game tag, and UCF toggles"""
        character: CSSCharacter #: Character selected
        type: Start.Player.Type #: Player type (human/cpu)
        stocks: int #: Starting stock count
        costume: int #: Costume ID
        team: Optional[Start.Player.Team] #: Team, if this was a teams game
        ucf: Start.Player.UCF #: UCF feature toggles
        tag: Optional[str] #: Name tag

        def __init__(self, character: CSSCharacter, type: Start.Player.Type, stocks: int, costume: int,
                     team: Optional[Start.Player.Team], ucf: Start.Player.UCF = None, tag: Optional[str] = None):
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
            return (self.character is other.character and
                    self.type is other.type and
                    self.stocks == other.stocks and
                    self.costume == other.costume and
                    self.team is other.team and
                    self.ucf == other.ucf)


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
            dash_back: Start.Player.UCF.DashBack #: UCF dashback status
            shield_drop: Start.Player.UCF.ShieldDrop #: UCF shield drop status

            def __init__(self, dash_back: Start.Player.UCF.DashBack = None,
                         shield_drop: Start.Player.UCF.ShieldDrop = None):
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

    method: End.Method #: `changed(2.0.0)` How the game ended
    lras_initiator: Optional[int] #: `added(2.0.0)` Index of player that LRAS'd, if any
    # Player placements stored as a list. The index represents the port, the value of that element is their placement.
    player_placements: Optional[List[int]] #: `added (3.13.0)` 0-indexed placement positions. -1 if player not in game

    def __init__(self, method: End.Method, lras_initiator: Optional[int] = None, player_placements: Optional[List[int]] = None):
        self.method = method
        self.lras_initiator = lras_initiator
        self.player_placements = player_placements

    @classmethod
    def _parse(cls, stream):
        (method,) = unpack('B', stream)
        try: # v2.0.0
            (lras,) = unpack('B', stream)
            lras_initiator = lras if lras < len(PORTS) else None
        except EOFError:
            lras_initiator = None

        try: # v3.13.0
            (p1_placement, p2_placement, p3_placement, p4_placement) = unpack('bbbb', stream)
            player_placements = [p1_placement, p2_placement, p3_placement, p4_placement]
        except EOFError:
            player_placements = None
        return cls(cls.Method(method), lras_initiator, player_placements)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self.method is other.method


    class Method(IntEnum):
        INCONCLUSIVE = 0 # `obsoleted(2.0.0)`
        TIME = 1 # `added(2.0.0)`
        GAME = 2 # `added(2.0.0)`
        CONCLUSIVE = 3 # `obsoleted(2.0.0)`
        NO_CONTEST = 7 # `added(2.0.0)`


class Frame(Base):
    """A single frame of the game. Includes data for all active bodies (characters, items, etc.)"""

    __slots__ = 'index', 'ports', 'items', 'start', 'end'

    index: int
    ports: Sequence[Optional[Frame.Port]] #: Frame data for each port (port 1 is index 0; empty ports will contain None)
    items: Sequence[Frame.Item] #: `added(3.0.0)` Active items (includes projectiles)
    start: Optional[Frame.Start] #: `added(2.2.0)` Start-of-frame data
    end: Optional[Frame.End] #: `added(2.2.0)` End-of-frame data

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

        leader: Frame.Port.Data #: Frame data for the controlled character
        follower: Optional[Frame.Port.Data] #: Frame data for the follower (Nana), if any

        def __init__(self):
            self.leader = self.Data()
            self.follower = None


        class Data(Base):
            """Frame data for a given character. Includes both pre-frame and post-frame data."""

            __slots__ = '_pre', '_post'

            def __init__(self):
                self._pre = None
                self._post = None

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

                def __init__(self, state: Union[ActionState, int], position: Position, direction: Direction,
                             joystick: Position, cstick: Position, triggers: Triggers, buttons: Buttons,
                             random_seed: int, raw_analog_x: Optional[int] = None, damage: Optional[float] = None):
                    self.state = state #: :py:class:`slippi.id.ActionState` | int: Character's action state
                    self.position = position #: :py:class:`Position`: Character's position
                    self.facing_direction = direction #: :py:class:`Direction`: Direction the character is facing
                    self.joystick = joystick #: :py:class:`Position`: Processed analog joystick position
                    self.cstick = cstick #: :py:class:`Position`: Processed analog c-stick position
                    self.triggers = triggers #: :py:class:`Triggers`: Trigger state
                    self.buttons = buttons #: :py:class:`Buttons`: Button state
                    self.random_seed = random_seed #: int: Random seed at this point
                    self.raw_analog_x = raw_analog_x #: int | None: `added(1.2.0)` Raw x analog controller input (for UCF)
                    self.percent = damage #: float | None: `added(1.4.0)` Current damage percent

                @classmethod
                def _parse(cls, stream):
                    (random_seed, state, position_x, position_y, direction, joystick_x, joystick_y, cstick_x,
                     cstick_y, trigger_logical, buttons_logical, buttons_physical, trigger_physical_l,
                     trigger_physical_r) = unpack('LHffffffffLHff', stream)

                    # v1.2.0
                    try: (raw_analog_x,) = unpack('B', stream)
                    except EOFError: raw_analog_x = None

                    # v1.4.0
                    try: (damage,) = unpack('f', stream)
                    except EOFError: damage = None

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
                        damage=damage)


            class Post(Base):
                """Post-frame update data, for making decisions about game states (such as computing stats).
                Information is collected at the end of collision detection, which is the last consideration of the game engine."""

                __slots__ = ('character', 'state', 'position', 'facing_direction', 'percent', 'shield_size', 'stocks_remaining',
                'most_recent_hit', 'last_hit_by', 'combo_count', 'state_age', 'flags', 'maybe_hitstun_remaining','is_airborne',
                'last_ground_id', 'jumps_remaining', 'l_cancel', 'hurtbox_status', 'self_ground_speed', 'self_air_speed',
                'knockback_speed', 'hitlag_remaining', 'animation_index')

                character: InGameCharacter # In-game character (can only change for Zelda/Sheik).
                state: Union[ActionState, int] # Character's action state
                position: Position # Character's position
                facing_direction: Direction # Direction the character is facing
                percent: float # Current damage percent
                shield_size: float # Current size of shield
                stocks_remaining: int # Number of stocks remaining
                most_recent_hit: Union[Attack, int] # Last attack that this character landed
                last_hit_by: Optional[int] # Port of character that last hit this character
                combo_count: int # Combo count as defined by the game
                state_age: Optional[float] # Number of frames action state has been active. Can have a fractional component for certain actions
                flags: Optional[StateFlags] # State flags
                maybe_hitstun_remaining: Optional[float] # hitstun boolean
                is_airborne: Optional[bool] # True if character is airborne
                last_ground_id: Optional[int] # ID of ground character is standing on, if any
                jumps_remaining: Optional[int] # Jumps remaining
                l_cancel: Optional[LCancel] # L-cancel status, if any
                hurtbox_status: Optional[Hurtbox]
                # speeds are split into 5 values. A shared Y, a grounded and air X, and a knockback X and Y. Generic Y *DOES* matter
                # even when grounded. For example, watch velocity values when walking on the slanted edges of yoshi's
                self_ground_speed: Optional[Velocity] # Self induced ground X speed and generic Y speed
                self_air_speed: Optional[Velocity] # Self induced air X speed and generic Y speed
                knockback_speed: Optional[Velocity] # Speed from knockback, adds with self-speeds for total velocity
                hitlag_remaining: Optional[float] # 0 means "not in hitlag"
                animation_index: Optional[int] # Indicates the animation the character is in, animation derived from state.
                # TODO enum animation indexes
                
                
                def __init__(self, character: InGameCharacter, state: Union[ActionState, int],
                             position: Position, direction: Direction, damage: float, shield: float, stocks: int,
                             most_recent_hit: Union[Attack, int], last_hit_by: Optional[int], combo_count: int,
                             state_age: Optional[float] = None, flags: Optional[StateFlags] = None, hit_stun: Optional[float] = None,
                             airborne: Optional[bool] = None, ground: Optional[int] = None, jumps: Optional[int] = None,
                             l_cancel: Optional[LCancel] = None, hurtbox_status: Optional[Hurtbox] = None,
                             self_ground_speed: Optional[Velocity] = None, self_air_speed: Optional[Velocity] = None,
                             knockback_speed: Optional[Velocity] = None, hitlag_remaining: Optional[float] = None,
                             animation_index: Optional[int]= None):
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
                    self.maybe_hitstun_remaining = hit_stun
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
                    (character, state, position_x, position_y, direction, damage, shield, last_attack_landed,
                     combo_count, last_hit_by, stocks) = unpack('BHfffffBBBB', stream)

                    # v0.2.0
                    try: (state_age,) = unpack('f', stream)
                    except EOFError: state_age = None
                    
                    try: # v2.0.0
                        flags = unpack('5B', stream)
                        (misc_as, airborne, maybe_ground, jumps, l_cancel) = unpack('f?HBB', stream)
                        log.info('%s', flags)
                        flags = StateFlags(flags[0] +
                                           flags[1] * 2**8 +
                                           flags[2] * 2**16 +
                                           flags[3] * 2**24 +
                                           flags[4] * 2**32)
                        ground = maybe_ground
                        hit_stun = misc_as if flags.HIT_STUN else None
                        l_cancel = LCancel(l_cancel) if l_cancel else None
                    except EOFError:
                        (flags, hit_stun, airborne, ground, jumps, l_cancel) = [None] * 6

                    try: # v2.1.0
                        (hurtbox_status,) = unpack('B', stream)
                    except EOFError:
                        hurtbox_status = None

                    try: # v3.5.0
                        (self_air_x, self_y, kb_x, kb_y, self_ground_x) = unpack('fffff', stream)
                        self_ground_speed = Velocity(self_ground_x, self_y)
                        self_air_speed = Velocity(self_air_x, self_y)
                        knockback_speed = Velocity(kb_x, kb_y)
                    except EOFError:
                        (self_ground_speed, self_air_speed, knockback_speed) = [None] * 3

                    try: # v3.8.0
                        (hitlag_remaining,) = unpack('f', stream)
                    except EOFError:
                        hitlag_remaining = None

                    try: # v3.11.0
                        (animation_index,) = unpack('I', stream)
                    except EOFError:
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
                        hit_stun=hit_stun,
                        airborne=airborne,
                        ground=ground,
                        jumps=jumps,
                        l_cancel=l_cancel,
                        hurtbox_status=hurtbox_status,
                        self_ground_speed=self_ground_speed,
                        self_air_speed=self_air_speed,
                        knockback_speed=knockback_speed,
                        hitlag_remaining=hitlag_remaining,
                        animation_index=animation_index)


    class Item(Base):
        """An active item (includes projectiles)."""

        __slots__ = 'type', 'state', 'direction', 'velocity', 'position', 'damage', 'timer', 'spawn_id'

        type: Item #: Item type
        state: int #: Item's action state
        direction: Direction #: Direction item is facing
        velocity: Velocity #: Item's velocity
        position: Position #: Item's position
        damage: int #: Amount of damage item has taken
        timer: int #: Frames remaining until item expires
        spawn_id: int #: Unique ID per item spawned (0, 1, 2, ...)
        missile_type: int
        turnip_type: TurnipFace
        is_shot_launched: bool
        charge_power: int
        owner: int


        def __init__(self, type: Item, state: int, direction: Direction, velocity: Velocity, position: Position,
                     damage: int, timer: int, spawn_id: int, missile_type: int, turnip_type: TurnipFace, is_shot_launched: bool,
                     charge_power: int, owner: int):
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
            (type, state, direction, x_vel, y_vel, x_pos, y_pos, damage, timer, spawn_id) = unpack('HB5fHfI', stream)

            try:
                (missile_type, turnip_type, is_shot_launched, charge_power, owner) = unpack('4Bb', stream)
            except EOFError:
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
                owner=owner)

        def __eq__(self, other):
            if not isinstance(other, self.__class__):
                return NotImplemented
            return (self.type == other.type and
                    self.state == other.state and
                    self.direction == other.direction and
                    self.velocity == other.velocity and
                    self.position == other.position and
                    self.damage == other.damage and
                    self.timer == other.timer and
                    self.spawn_id == other.spawn_id)


    class Start(Base):
        """Start-of-frame data."""

        __slots__ = 'random_seed'

        random_seed: int #: The random seed at the start of the frame

        def __init__(self, random_seed: int):
            self.random_seed = random_seed

        @classmethod
        def _parse(cls, stream):
            (random_seed,) = unpack('I', stream)
            random_seed = random_seed
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
            __slots__ = 'frame'

            def __init__(self, stream):
                (self.frame,) = unpack('i', stream)


        class PortId(Id):
            __slots__ = 'port', 'is_follower'

            def __init__(self, stream):
                (self.frame, self.port, self.is_follower) = unpack('iB?', stream)


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
        return '(%.2f, %.2f)' % (self.x, self.y)


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
        return '(%.2f, %.2f)' % (self.x, self.y)

# TODO move all the enums to .id

class Direction(IntEnum):
    LEFT = -1
    DOWN = 0 # not used by slippi replay data, but useful for stats enumerations
    RIGHT = 1

class Triggers(Base):
    __slots__ = 'logical', 'physical'

    logical: float #: Processed analog trigger position
    physical: Triggers.Physical #: Physical analog trigger positions (useful for APM)

    def __init__(self, logical: float, physical_x: float, physical_y: float):
        self.logical = logical
        self.physical = self.Physical(physical_x, physical_y)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return other.logical == self.logical and other.physical == self.physical


    class Physical(Base):
        __slots__ = 'l', 'r'

        l: float
        r: float

        def __init__(self, l: float, r: float):
            self.l = l
            self.r = r

        def __eq__(self, other):
            if not isinstance(other, self.__class__):
                return NotImplemented
            # Should we add an epsilon to these comparisons? When are people going to be comparing trigger states for equality, other than in our tests?
            return other.l == self.l and other.r == self.r


class Buttons(Base):
    __slots__ = 'logical', 'physical'

    logical: Buttons.Logical #: Processed button-state bitmask
    physical: Buttons.Physical #: Physical button-state bitmask

    def __init__(self, logical, physical):
        self.logical = self.Logical(logical)
        self.physical = self.Physical(physical)

    def __eq__(self, other):
        if not isinstance(other, Buttons):
            return NotImplemented
        return other.logical is self.logical and other.physical is self.physical


    class Logical(IntFlag):
        TRIGGER_ANALOG = 2**31
        CSTICK_RIGHT = 2**23
        CSTICK_LEFT = 2**22
        CSTICK_DOWN = 2**21
        CSTICK_UP = 2**20
        JOYSTICK_RIGHT = 2**19
        JOYSTICK_LEFT = 2**18
        JOYSTICK_DOWN = 2**17
        JOYSTICK_UP = 2**16
        START = 2**12
        Y = 2**11
        X = 2**10
        B = 2**9
        A = 2**8
        L = 2**6
        R = 2**5
        Z = 2**4
        DPAD_UP = 2**3
        DPAD_DOWN = 2**2
        DPAD_RIGHT = 2**1
        DPAD_LEFT = 2**0
        NONE = 0


    class Physical(IntFlag):
        START = 2**12
        Y = 2**11
        X = 2**10
        B = 2**9
        A = 2**8
        L = 2**6
        R = 2**5
        Z = 2**4
        DPAD_UP = 2**3
        DPAD_DOWN = 2**2
        DPAD_RIGHT = 2**1
        DPAD_LEFT = 2**0
        NONE = 0

        def pressed(self):
            """Returns a list of all buttons being pressed."""
            pressed = []
            for b in self.__class__:
                if self & b:
                    pressed.append(b)
            return pressed


class LCancel(IntEnum):
    NOT_APPLICABLE = 0
    SUCCESS = 1
    FAILURE = 2


class StateFlags(IntFlag):
    REFLECT = 2**4
    UNTOUCHABLE = 2**10
    FAST_FALL = 2**11
    HIT_LAG = 2**13
    SHIELD = 2**23
    HIT_STUN = 2**25
    SHIELD_TOUCH = 2**26
    POWER_SHIELD = 2**29
    FOLLOWER = 2**35
    SLEEP = 2**36
    DEAD = 2**38
    OFF_SCREEN = 2**39

class Hurtbox(IntEnum):
    VULNERABLE = 0
    INVULNERABLE = 1
    INTANGIBLE = 2
