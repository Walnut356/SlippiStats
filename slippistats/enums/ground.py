from functools import lru_cache

from ..util import IntEnum, try_enum

from .stage import Stage


class Yoshis(IntEnum):
    RANDALL = 0
    LEFT_PLATFORM = 1
    LEFT_SLANT = 2
    MAIN_STAGE = 3
    TOP_PLATFORM = 4
    RIGHT_PLATFORM = 5
    RIGHT_SLANT = 6


class Battlefield(IntEnum):
    LEFT_EDGE = 0
    MAIN_STAGE = 1
    LEFT_PLATFORM = 2
    TOP_PLATFORM = 3
    RIGHT_PLATFORM = 4
    RIGHT_EDGE = 5


class Dreamland(IntEnum):
    LEFT_PLATFORM = 0
    RIGHT_PLATFORM = 1
    TOP_PLATFORM = 2
    LEFT_EDGE = 3
    MAIN_STAGE = 4
    RIGHT_EDGE = 5


class PokemonStadium(IntEnum):
    MAIN_STAGE = 34
    LEFT_PLATFORM = 35
    RIGHT_PLATFORM = 36
    LEFT_EDGE_OUTTER = 51
    LEFT_EDGE_INNER = 52
    RIGHT_EDGE_INNER = 53
    RIGHT_EDGE_OUTTER = 54


class FountainOfDreams(IntEnum):
    LEFT_PLATFORM = 0
    RIGHT_PLATFORM = 1
    TOP_PLATFOMR = 2
    LEFT_EDGE_OUTTER = 3
    LEFT_EDGE_INNER = 4
    MAIN_STAGE = 5
    RIGHT_EDGE_INNER = 6
    RIGHT_EDGE_OUTTER = 7


class FinalDestination(IntEnum):
    LEFT_EDGE = 0
    MAIN_STAGE = 1
    RIGHT_EDGE = 2

@lru_cache(maxsize=4)
def get_ground(stage: Stage, ground_id: int) -> IntEnum:
    if stage is None or ground_id is None:
        return ground_id

    match stage:
        case Stage.YOSHIS_STORY:
            if ground_id in {2, 6}:
                ground = Yoshis.MAIN_STAGE
            else:
                ground = try_enum(Yoshis, ground_id)
            return ground

        case Stage.BATTLEFIELD:
            if ground_id in {0, 5}:
                ground = Battlefield.MAIN_STAGE
            else:
                ground = try_enum(Battlefield, ground_id)
            return ground

        case Stage.DREAM_LAND_N64:
            if ground_id in {3, 5}:
                ground = Dreamland.MAIN_STAGE
            else:
                ground = try_enum(Dreamland, ground_id)
            return ground

        case Stage.POKEMON_STADIUM:
            if ground_id in {51, 52, 53, 54}:
                ground = PokemonStadium.MAIN_STAGE
            else:
                ground = try_enum(PokemonStadium, ground_id)
            return ground

        case Stage.FOUNTAIN_OF_DREAMS:
            if ground_id in {3, 4, 6, 7}:
                ground = FountainOfDreams(ground_id)
            else:
                ground = try_enum(FountainOfDreams, ground_id)
            return ground

        case Stage.FINAL_DESTINATION:
            return FinalDestination.MAIN_STAGE
