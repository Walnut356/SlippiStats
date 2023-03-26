from pathlib import Path
import struct
from slippistats import Game
import timeit
import slippi

avg_replay = Path(r'Modern Replays/Game_20221227T194333.slp')
long_replay = Path(r"Modern Replays/Game_20221227T210010.slp")


def eef():
    thing = Game(avg_replay)


def freef():
    thing = slippi.Game(avg_replay)


# print(timeit.timeit(eef, number=50))
# print(timeit.timeit(freef, number=50))

for i in range(100000):
    eef()
#     freef()