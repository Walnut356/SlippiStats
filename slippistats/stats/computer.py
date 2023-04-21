import datetime
from dataclasses import dataclass
from itertools import permutations
from os import PathLike

from ..enums.character import CSSCharacter
from ..event import Frame, Start
from ..game import Game
from ..util import Base, Port
from .stat_types import Data


class IdentifierError(Exception):
    """Connect code or port identifier does not match any players in the available Game object."""

    pass


class PlayerCountError(Exception):
    """The Game object's player count is not 2"""

    pass


class PlayerTypeError(Exception):
    """One or both players is not Player.Type.HUMAN"""

    pass


@dataclass
class Player(Base):
    """Aggregates info from event.Start.Player and metadata.Player. Also contains all frames for the player's port.

    Stats and Combo output is stored here.
    """

    character: CSSCharacter
    port: Port
    connect_code: str | None
    display_name: str | None
    costume: int
    did_win: bool
    frames: list[Frame.Port.Data]
    stats: Data
    combos: list
    nana_frames: list[Frame.Port.Data] | None = None

    def __init__(
        self,
        characters: tuple[CSSCharacter],
        port: Port,
        costume: int,
        frames: list[Frame.Port.Data],
        stats_header: dict,
        nana_frames: list[Frame.Port.Data] | None = None,
        connect_code: str | None = None,
        display_name: str | None = None,
        did_win: bool | None = None,
    ):
        self.character = characters[0]
        self.port = port
        self.connect_code = connect_code
        self.display_name = display_name
        self.costume = costume
        self.did_win = did_win
        self.frames = frames
        self.nana_frames = nana_frames

        data_header = {
            "result": "win" if self.did_win else "loss",
            "port": self.port.name,
            "connect_code": self.connect_code,
            "character": self.character.name,
            "costume": self.costume.name,
            "opnt_character": characters[1].name,
        }
        data_header = stats_header | data_header

        self.stats = Data(data_header)
        self.combos = []


# TODO abstract base class?
class ComputerBase:
    """Base for Computer classes, used for processing parsed replays.

    Currently only accepts replays with 2 human players

    Attributes:
        replay : Game
            The current parsed replay object
        replay_version : Start.SlippiVersion
            The parsed replay's version number. Can be compared to tuples and strings - e.g. (0, 1, 0), "0.1.0"
        replay_path : Pathlike | str
            Filepath used to parse the current replay if one was provided. Required for dolphin queue export
        players : list[Player]
            Contains metadata and all frames for each player in the game. Generated stats and combos are stored here
        queue : list[dict]
            formatted list of events used to create Clippi/Dolphin compatible json queues for playback

    Methods:
        prime_replay -> None
            Takes a Game object or a file path, parses the replay if necessary, and populates the correct information
            in the Computer object.
        get_player -> Player
            Takes an identifier (string connect code or physical port number), returns a
            Player object matching that identifier. Raises IdentifierError if the identifier is not found.
        get_opponent -> Player
            Takes an identifier (string connect code or physical port number), returns a Player object that does not
            match that identifier, if that identifier matches one player in the game.
    """

    replay: Game | None
    replay_version: Start.SlippiVersion | None
    queue: list[dict]
    replay_path: PathLike | str
    players: list[Player]

    def prime_replay(self, replay: PathLike | Game | str):
        """Parses a replay and loads the relevant data into the Computer. Also accepts pre-parsed Game objects."""
        if isinstance(replay, (PathLike, str)):
            parsed_replay = Game(replay)
            self.replay_path = replay
        elif isinstance(replay, Game):
            parsed_replay = replay
            self.replay_path = ""
        else:
            raise TypeError("prime_replay accepts only PathLikes, strings, and Game objects.")

        self.replay = parsed_replay
        self.replay_version = self.replay.start.slippi_version

        stats_header = {
            "date_time": self.replay.metadata.date,
            "slippi_version": str(self.replay_version),
            "match_id": self.replay.start.match_id,
            "match_type": self.replay.start.match_type.name,
            "game_number": self.replay.start.game_number,
            "stage": self.replay.start.stage.name,
            "duration": datetime.timedelta(seconds=((self.replay.metadata.duration) / 60)),
        }

        # HACK ugly garbage to pass opponent character correctly
        # characters will appear in order, ports will populate in order.
        # Using this we can just use a simple permutation to guarantee
        # object 1 in the list is the current player's character and object 2 is the opponent's character.
        # this only works for 2 players, but double stats is a pretty rare usecase so it's fine for now.
        characters = list(
            permutations([player.character for player in self.replay.start.players if player is not None])
        )
        if len(characters) != 2:
            raise PlayerCountError(f"Got {len(characters)} human players in {self.replay_path}, expected 2")

        # handling for bugged replays without a game end event
        _game_end = False
        if self.replay.end:
            _game_end = True
        for port in Port:
            if _game_end:
                if self.replay.end.player_placements is not None:
                    did_win = True if self.replay.end.player_placements[port] == 0 else False
                elif self.replay.end.lras_initiator is not None and self.replay.end.lras_initiator != -1:
                    did_win = True if port != self.replay.end.lras_initiator else False
                else:
                    # TODO this is going to need better logic eventually to account for timeouts, old replay LRAS's, etc
                    if self.replay.frames[-1].ports[port].leader.post.stocks_remaining > 0:
                        did_win = True
                    else:
                        did_win = False
            else:
                did_win = False
            if self.replay.start.players[port] is not None:
                self.players.append(
                    Player(
                        characters=characters.pop(0),
                        port=port,
                        connect_code=self.replay.metadata.players[port].connect_code,
                        display_name=self.replay.metadata.players[port].display_name,
                        costume=self.replay.start.players[port].costume,
                        did_win=did_win,
                        frames=tuple([frame.ports[port].leader for frame in self.replay.frames]),
                        nana_frames=(
                            tuple([frame.ports[port].follower for frame in self.replay.frames])
                            if self.replay.start.players[port].character == CSSCharacter.ICE_CLIMBERS
                            else None
                        ),
                        stats_header=stats_header,
                    )
                )

        if len(self.players) != 2:
            raise ValueError("Game must have exactly 2 players for stats generation")

        return self

    def reset_data(self):
        return

    def get_player(self, identifier: str | int | Port) -> Player:
        """
        Takes an identifier, returns a player object matching the identifier. Raises an error if the identifier is not
        present in the game.

        Args:
            identifier : str | int | Ports
                str format "CODE#123". Port/int corresponds to physical ports p1-p4.
        Returns:
            Player
        Raises:
            IdentifierError
                Raised when identifier does not match any players in the currently primed replay
        """
        match identifier.upper():
            case str():
                for player in self.players:
                    if player.connect_code == identifier:
                        return player
                else:
                    # TODO probably rip this out and just replace it with a log warning when done debugging
                    raise IdentifierError(f"No player matching given connect code {identifier}")
            case int() | Port():
                for player in self.players:
                    if player.port == identifier:
                        return player
                else:
                    raise IdentifierError(f"No player matching given port number {identifier}")
            case _:
                raise IdentifierError(
                    f"""Invalid identifier type for identifier: {identifier}.
                    Got: {type(identifier)} Expected: str | int | Ports"""
                )

    def get_opponent(self, identifier: str | int | Port) -> Player:
        """
        Takes an identifier, returns the player object that does not match the identifier. Raises an error if the
        identifier is not present in the game.

        Args:
            identifier : str | int | Ports
                str format "CODE#123". Port/int corresponds to physical ports p1-p4.
        Returns:
            Player
        Raises:
            IdentifierError
                Raised when identifier does not match any players in the currently primed replay
        """
        opponent = None
        valid_id = False

        match identifier:
            case str():
                for player in self.players:
                    if player.connect_code == identifier:
                        valid_id = True
                    else:
                        opponent = player
            case int() | Port():
                for player in self.players:
                    if player.port == identifier:
                        valid_id = True
                    else:
                        opponent = player
            case _:
                raise IdentifierError(
                    f"""Invalid identifier type for identifier: {identifier}.
                    Got: {type(identifier)} Expected: str | int | Ports"""
                )

        if valid_id:
            return opponent
        else:
            raise IdentifierError(
                f"""Cannot find opponent for identifier {identifier}.
                                  {identifier} is not present in game"""
            )
