from ..util import IntEnum


class CSSCharacter(IntEnum):
    CAPTAIN_FALCON = 0
    DONKEY_KONG = 1
    FOX = 2
    GAME_AND_WATCH = 3
    KIRBY = 4
    BOWSER = 5
    LINK = 6
    LUIGI = 7
    MARIO = 8
    MARTH = 9
    MEWTWO = 10
    NESS = 11
    PEACH = 12
    PIKACHU = 13
    ICE_CLIMBERS = 14
    JIGGLYPUFF = 15
    SAMUS = 16
    YOSHI = 17
    ZELDA = 18
    SHEIK = 19
    FALCO = 20
    YOUNG_LINK = 21
    DR_MARIO = 22
    ROY = 23
    PICHU = 24
    GANONDORF = 25
    MASTER_HAND = 26
    WIREFRAME_MALE = 27
    WIREFRAME_FEMALE = 28
    GIGA_BOWSER = 29
    CRAZY_HAND = 30
    SANDBAG = 31
    POPO = 32

    @classmethod
    def from_internal_id(cls, internal_id):
        char = InGameCharacter(internal_id)
        if char is InGameCharacter.NANA or char is InGameCharacter.POPO:
            return cls.ICE_CLIMBERS
        else:
            return cls[char.name]


class InGameCharacter(IntEnum):
    MARIO = 0
    FOX = 1
    CAPTAIN_FALCON = 2
    DONKEY_KONG = 3
    KIRBY = 4
    BOWSER = 5
    LINK = 6
    SHEIK = 7
    NESS = 8
    PEACH = 9
    POPO = 10
    NANA = 11
    PIKACHU = 12
    SAMUS = 13
    YOSHI = 14
    JIGGLYPUFF = 15
    MEWTWO = 16
    LUIGI = 17
    MARTH = 18
    ZELDA = 19
    YOUNG_LINK = 20
    DR_MARIO = 21
    FALCO = 22
    PICHU = 23
    GAME_AND_WATCH = 24
    GANONDORF = 25
    ROY = 26
    MASTER_HAND = 27
    CRAZY_HAND = 28
    WIREFRAME_MALE = 29
    WIREFRAME_FEMALE = 30
    GIGA_BOWSER = 31
    SANDBAG = 32


# ---------------------------------------------------------------------------- #
#                              Character Costumes                              #
# ---------------------------------------------------------------------------- #


class CaptainFalcon(IntEnum):
    INDIGO = 0
    BLACK = 1
    RED = 2
    WHITE = 3
    GREEN = 4
    BLUE = 5


class DonkeyKong(IntEnum):
    BROWN = 0
    BLACK = 1
    RED = 2
    BLUE = 3
    GREEN = 4


class Fox(IntEnum):
    WHITE = 0
    RED = 1
    BLUE = 2
    GREEN = 3


class GameAndWatch(IntEnum):
    BLACK = 0
    RED = 1
    BLUE = 2
    GREEN = 3


class Kirby(IntEnum):
    PINK = 0
    YELLOW = 1
    BLUE = 2
    RED = 3
    GREEN = 4
    WHITE = 5


class Bowser(IntEnum):
    GREEN = 0
    RED = 1
    BLUE = 2
    BLACK = 3


class Link(IntEnum):
    GREEN = 0
    RED = 1
    BLUE = 2
    BLACK = 3
    WHITE = 4


class Luigi(IntEnum):
    GREEN = 0
    WHITE = 1
    BLUE = 2
    RED = 3
    """Pink"""


class Mario(IntEnum):
    RED = 0
    YELLOW = 1
    BLACK = 2
    BLUE = 3
    GREEN = 4


class Marth(IntEnum):
    BLUE = 0
    RED = 1
    GREEN = 2
    BLACK = 3
    WHITE = 4


class Mewtwo(IntEnum):
    PURPLE = 0
    """White"""
    RED = 1
    BLUE = 2
    GREEN = 3


class Ness(IntEnum):
    RED = 0
    YELLOW = 1
    BLUE = 2
    """Purple"""
    GREEN = 3


class Peach(IntEnum):
    RED = 0
    YELLOW = 1
    """Daisy"""
    WHITE = 2
    BLUE = 3
    GREEN = 4


class Pikachu(IntEnum):
    YELLOW = 0
    RED = 1
    """Trucker hat"""
    BLUE = 2
    """Party hat"""
    GREEN = 3
    """Cowboy hat"""


class IceClimbers(IntEnum):
    BLUE = 0
    GREEN = 1
    ORANGE = 2
    RED = 3


class Jigglypuff(IntEnum):
    PINK = 0
    RED = 1
    """Flower"""
    BLUE = 2
    """Bow"""
    GREEN = 3
    """Headband"""
    YELLOW = 4
    """Crown"""


class Samus(IntEnum):
    RED = 0
    """Orange"""
    PINK = 1
    BLACK = 2
    GREEN = 3
    BLUE = 4
    """Purple"""


class Yoshi(IntEnum):
    GREEN = 0
    RED = 1
    BLUE = 2
    YELLOW = 3
    PINK = 4
    CYAN = 5


class Zelda(IntEnum):
    PINK = 0
    RED = 1
    BLUE = 2
    GREEN = 3
    WHITE = 4


class Sheik(IntEnum):
    NAVY = 0
    RED = 1
    BLUE = 2
    GREEN = 3
    WHITE = 4


class Falco(IntEnum):
    TAN = 0
    RED = 1
    BLUE = 2
    GREEN = 3


class YoungLink(IntEnum):
    GREEN = 0
    RED = 1
    BLUE = 2
    WHITE = 3
    BLACK = 4


class DrMario(IntEnum):
    WHITE = 0
    RED = 1
    BLUE = 2
    GREEN = 3
    BLACK = 4


class Roy(IntEnum):
    PURPLE = 0
    RED = 1
    BLUE = 2
    GREEN = 3
    YELLOW = 4


class Pichu(IntEnum):
    YELLOW = 0
    RED = 1
    BLUE = 2
    GREEN = 3


class Ganondorf(IntEnum):
    BROWN = 0
    RED = 1
    BLUE = 2
    GREEN = 3
    PURPLE = 4


CHARACTER_COSTUME_MAP = {
    CSSCharacter.CAPTAIN_FALCON: CaptainFalcon,
    CSSCharacter.DONKEY_KONG: DonkeyKong,
    CSSCharacter.FOX: Fox,
    CSSCharacter.GAME_AND_WATCH: GameAndWatch,
    CSSCharacter.KIRBY: Kirby,
    CSSCharacter.BOWSER: Bowser,
    CSSCharacter.LINK: Link,
    CSSCharacter.LUIGI: Luigi,
    CSSCharacter.MARIO: Mario,
    CSSCharacter.MARTH: Marth,
    CSSCharacter.MEWTWO: Mewtwo,
    CSSCharacter.NESS: Ness,
    CSSCharacter.PEACH: Peach,
    CSSCharacter.PIKACHU: Pikachu,
    CSSCharacter.ICE_CLIMBERS: IceClimbers,
    CSSCharacter.JIGGLYPUFF: Jigglypuff,
    CSSCharacter.SAMUS: Samus,
    CSSCharacter.YOSHI: Yoshi,
    CSSCharacter.ZELDA: Zelda,
    CSSCharacter.SHEIK: Sheik,
    CSSCharacter.FALCO: Falco,
    CSSCharacter.YOUNG_LINK: YoungLink,
    CSSCharacter.DR_MARIO: DrMario,
    CSSCharacter.ROY: Roy,
    CSSCharacter.PICHU: Pichu,
    CSSCharacter.GANONDORF: Ganondorf,
    26: lambda x: None
}


def get_costume(character: CSSCharacter, costume: int) -> IntEnum:
    return CHARACTER_COSTUME_MAP[character](costume)
