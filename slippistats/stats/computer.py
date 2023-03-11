from os import PathLike
from typing import Any, Optional

from ..event import Frame, Start
from ..game import Game
from ..metadata import Metadata


class ComputerBase():

    rules: Optional[Start]
    players: list[Metadata.Player]
    placements: Optional[list[int]]
    did_win: Optional[bool]
    all_frames: list[Frame]
    metadata: Optional[Metadata]
    queue: list[dict]
    replay_path: PathLike | str

    #TODO store whole game object instead of just pieces of it
    #TODO adopt peppi "port frames" model, aggregate all player data (e.g. connect code, in-game info, placement, etc.)

    def prime_replay(self, replay: PathLike | Game | str, retain_data=False) -> None:
        """Parses a replay and loads the relevant data into the combo computer. Call combo_compute(connect_code) to extract combos
        from parsed replay"""
        if isinstance(replay, PathLike) or isinstance(replay, str):
            parsed_replay = Game(replay)
            self.replay_path = replay
        elif isinstance(replay, Game):
            parsed_replay = replay
            self.replay_path = ""
        else:
            raise TypeError("prime_replay accepts only PathLikes, strings, and Game objects.")

        self.rules = parsed_replay.start
        self.players = [player for player in parsed_replay.metadata.players if player is not None]
        self.all_frames = parsed_replay.frames
        self.metadata = parsed_replay.metadata
        self.placements = parsed_replay.end.player_placements
        self.did_win = None

        if not retain_data:
            self.reset_data()

    #FIXME the entry/return on this is dumb and I need to restructure it so it's useable anywhere outside of the stats calc
    def get_player_ports(self, connect_code=None) -> Any:  #difficult to express proper type hint
        player_port = -1
        opponent_port = -1
        if connect_code:
            for i, player in enumerate(self.players):
                if player.connect_code == connect_code.upper():
                    player_port = i
                else:
                    opponent_port = i
            if player_port == opponent_port:
                return [[], None]
            # TODO raise exception? log warning?
            # currently returns nothing so program will continue and stats calc will do nothing
            return [[player_port], opponent_port]

        # If there's no connect code, extract the port values of both *active* ports
        player_ports = [i for i, x in enumerate(self.rules.players) if x is not None]
        # And if there's more than 2 active ports, we return an empty list which should skip processing.
        # TODO make this an exception, but one that doesn't kill the program? Or just some way to track which replays don't get processed
        if len(player_ports) > 2:
            return []
        return player_ports

    def port_frame(self, port: int, frame: Frame) -> Frame.Port.Data:
        return frame.ports[port].leader

    def port_frame_by_index(self, port: int, index: int) -> Frame.Port.Data:
        return self.all_frames[index].ports[port].leader

    def reset_data(self):
        return

    def is_winner(self, identifier: int | str) -> bool:
        if isinstance(identifier, str):
            identifier = self.get_player_ports(identifier)[0][0]
        return True if self.placements[identifier] == 0 else False
