from ..util import *


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
