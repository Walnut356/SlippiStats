from pathlib import Path
from dis import dis
import os
import struct
import random
from functools import lru_cache, cache
import slippistats as slp
import timeit, time
import polars as pl
import concurrent.futures


file = Path(R"test/Bench Replays/mango_zain_netplay.slp")
dir = Path(R"test/Bench Replays")


def eef(replay):
    thing = slp.Game(replay)


def freef(replay):
    thing = slp.Game(replay)


eef(file)
# print(timeit.timeit(eef, number=50))
# print(timeit.timeit(freef, number=50))


with os.scandir(dir) as d:
    for entry in d:
        file = os.path.join(dir, entry.name)
        print(timeit.timeit("eef(file)", number=1, timer=time.process_time, globals=globals()))
