from pathlib import Path
import os
import struct
from slippistats import Game
import timeit


dir = Path(R"test/Bench Replays")

# file = Path(R'test\Bench Replays\mango_zain_netplay.slp')


def eef(replay):
    thing = Game(replay)


# def freef():
#     thing = Game(replay)

# print(timeit.timeit(eef, number=50))
# print(timeit.timeit(freef, number=50))
# thing = Game(file)

with os.scandir(dir) as d:
    for entry in d:
        file = os.path.join(dir, entry.name)
        print(entry.name)
        print(timeit.timeit("eef(file)", number=1, globals=globals()))

# for i in range(100000):
#     freef()
