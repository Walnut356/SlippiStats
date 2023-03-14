from itertools import permutations
from os import PathLike
from typing import Optional
from dataclasses import dataclass
import datetime

from ..enums import CSSCharacter
from ..event import Frame
from ..game import Game
from ..util import Ports, Base
from .stat_types import Data


@dataclass
class Player(Base):
    """Aggregate class for event.Start.Player and metadata.Player.
    Also contains stats info"""
    character: CSSCharacter
    port: Ports
    connect_code: Optional[str]
    display_name: Optional[str]
    costume: int
    did_win: bool
    frames: list[Frame.Port.Data]
    stats: Data
    nana_frames: Optional[list[Frame.Port.Data]] = None

    def __init__(self, characters, port, connect_code, display_name, costume, did_win, frames, nana_frames, stats_header):
        self.character = characters[0]
        self.port = port
        self.connect_code = connect_code
        self.display_name = display_name
        self.costume = costume
        self.did_win = did_win
        self.frames = frames
        self.nana_frames = nana_frames

        data_header = {
            "result" : "win" if self.did_win else "loss",
            "port" : self.port.name,
            "connect_code" : self.connect_code,
            "chara" : self.character.name,
            "opnt_chara" : characters[1].name,
        }
        data_header = stats_header | data_header

        self.stats = Data(data_header)



#TODO abstract base class?
class ComputerBase():

    replay: Optional[Game]
    queue: list[dict]
    replay_path: PathLike | str
    players: list[Player]

    def prime_replay(self, replay: PathLike | Game | str):
        """Parses a replay and loads the relevant data into the combo computer. Call combo_compute(connect_code) to extract combos
        from parsed replay"""
        if isinstance(replay, (PathLike, str)):
            parsed_replay = Game(replay)
            self.replay_path = replay
        elif isinstance(replay, Game):
            parsed_replay = replay
            self.replay_path = ""
        else:
            raise TypeError("prime_replay accepts only PathLikes, strings, and Game objects.")

        self.replay = parsed_replay

        stats_header = {
            "match_id" : self.replay.start.match_id,
            "date_time" : self.replay.metadata.date.replace(tzinfo=None),
            "match_type" : self.replay.start.match_type.name,
            "game_number" : self.replay.start.game_number,
            "duration" : datetime.timedelta(seconds=((self.replay.metadata.duration)/60)),
            }

        # HACK ugly garbage to pass opponent character correctly
        # characters will appear in order, ports will populate in order. Using this we can just use a simple permutation to guarantee
        # object 1 in the list is the current player's character and object 2 is the opponent's character.
        # this only works for 2 players, but double stats is a pretty rare usecase so it's fine for now.
        characters = list(permutations([player.character for player in self.replay.start.players if player is not None]))

        for port in Ports:

            if self.replay.start.players[port] is not None:
                self.players.append(
                    Player(
                        characters=characters.pop(0),
                        port=port,
                        connect_code=self.replay.metadata.players[port].connect_code,
                        display_name=self.replay.metadata.players[port].display_name,
                        costume=self.replay.start.players[port].costume,
                        did_win=True if self.replay.end.player_placements[port] == 0 else False,
                        frames=tuple([frame.ports[port].leader for frame in self.replay.frames]),
                        nana_frames= (tuple([frame.ports[port].follower for frame in self.replay.frames])
                            if self.replay.start.players[port].character == CSSCharacter.ICE_CLIMBERS else None),
                        stats_header=stats_header
                            )
                        )

        if len(self.players) != 2:
            raise ValueError("Game must have exactly 2 players for stats generation")

        return self

    #FIXME the entry/return on this is dumb and I need to restructure it so it's useable anywhere outside of the stats calc
    # def get_player_ports(self, connect_code=None) -> Any:  #difficult to express proper type hint
    #     player_port = -1
    #     opponent_port = -1
    #     if connect_code:
    #         for i, player in enumerate(self.players):
    #             if player.connect_code == connect_code.upper():
    #                 player_port = i
    #             else:
    #                 opponent_port = i
    #         if player_port == opponent_port:
    #             return [[], None]
    #         # TODO raise exception? log warning?
    #         # currently returns nothing so program will continue and stats calc will do nothing
    #         return [[player_port], opponent_port]

    #     # If there's no connect code, extract the port values of both *active* ports
    #     player_ports = [i for i, x in enumerate(self.replay.start.players) if x is not None]
    #     # And if there's more than 2 active ports, we return an empty list which should skip processing.
    #     # TODO make this an exception, but one that doesn't kill the program? Or just some way to track which replays don't get processed
    #     if len(player_ports) > 2:
    #         return []
    #     return player_ports

    # def port_frame(self, port: int, frame: Frame) -> Frame.Port.Data:
    #     return frame.ports[port].leader

    # def port_frame_by_index(self, port: int, index: int) -> Frame.Port.Data:
    #     return self.replay.frames[index].ports[port].leader

    def reset_data(self):
        return

    def get_player(self, identifier: str | int | Ports) -> Player:
        match identifier:
            case str():
                for player in self.players:
                    if player.connect_code == identifier:
                        return player
                else:
                    #TODO probably rip this out and just replace it with a log warning when done debugging
                    raise ValueError(f"No player matching given connect code {identifier}")
            case int() | Ports():
                return self.players[identifier]
            case _:
                raise ValueError(f"Invalid identifier type: {identifier} {type(identifier)}. get_player() accepts str, int, or Port")

    def get_opponent(self, identifier: str | int | Ports) -> Player:
        match identifier:
            case str():
                for player in self.players:
                    if player.connect_code != identifier:
                        return player
                else:
                    #TODO probably rip this out and just replace it with a log warning when done debugging
                    raise ValueError(f"No player matching given connect code {identifier}")
            case int() | Ports():
                return self.players[identifier - 1]
            case _:
                raise ValueError(f"Invalid identifier type: {identifier} {type(identifier)}. get_player() accepts str, int, or Port")