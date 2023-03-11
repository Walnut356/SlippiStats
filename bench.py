from pathlib import Path
import struct
from slippistats import *
import timeit

file = Path(r'Modern Replays/Game_20221227T194333.slp')


def eef():
    file = Path(r'Modern Replays/Game_20221227T194333.slp')
    Game(file)


# eef()
print(timeit.timeit(eef, number=1))