from pathlib import Path
from dis import dis
import os
import struct
import random
from functools import lru_cache, cache
import slippistats as slp
import timeit, time
import polars as pl


file = Path(R"test/Bench Replays/mango_zain_netplay.slp")
dir = Path(R"test/Bench Replays")


def eef(replay):
    thing = slp.Game(replay)
    for frame in thing.frames:
        for player in frame.ports:
            if player is not None:
                dang = player.leader.pre
                dang = player.leader.post


def freef(replay):
    thing = slp.Game(replay)


eef(file)
# print(timeit.timeit(eef, number=50))
# print(timeit.timeit(freef, number=50))


with os.scandir(dir) as d:
    for entry in d:
        file = os.path.join(dir, entry.name)
        print(timeit.timeit("eef(file)", number=1, timer=time.process_time, globals=globals()))

# for i in range(100000):
#     freef(file)

# dis(slp.Frame.Port.Data.Post._parse)

# byte = []

# for i in range(100000):
#     byte.append(random.randbytes(4))

# unpack_byte = struct.Struct(">f").unpack

# lru_byte = lru_cache(struct.Struct(">f").unpack)


# cache_byte = cache(struct.Struct(">f").unpack)


# def reg():
#     for num in byte:
#         struct.unpack(">f", num)


# def store_global():
#     for num in byte:
#         unpack_byte(num)


# def store_local(unpack_byte=unpack_byte):
#     for num in byte:
#         unpack_byte(num)


# def cache_lru(lru_byte=lru_byte):
#     for num in byte:
#         lru_byte(num)


# def cache_normal(cache_byte=cache_byte):
#     for num in byte:
#         cache_byte(num)


# print("reg: ", timeit.timeit(reg, globals=globals(), number=1))
# print("store_global: ", timeit.timeit(store_global, globals=globals(), number=1))
# print("store_local: ", timeit.timeit(store_local, globals=globals(), number=1))
# print("cache_lru: ", timeit.timeit(store_local, globals=globals(), number=1))
# print("cache_normal: ", timeit.timeit(store_local, globals=globals(), number=1))

# pass
# thing = {}

# print(timeit.timeit("thing['eef'] = 100", globals=globals()))
