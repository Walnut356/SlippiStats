from pathlib import Path
import os
import struct
import slippistats as slp
import timeit
import polars as pl


dir = Path(R"test/Bench Replays")

file = Path(R"E:\Slippi Replays\Netplay\Game_20230113T010619.slp")

thing = slp.StatsComputer(file)

data = thing.take_hit_compute("NUT#356")

print("Done")

data = data.to_polars()

print("Done")


# file = Path(R'test\Bench Replays\mango_zain_netplay.slp')


# def eef(replay):
#     thing = Game(replay)


# def freef():
#     thing = Game(replay)

# print(timeit.timeit(eef, number=50))
# print(timeit.timeit(freef, number=50))
# thing = Game(file)

# with os.scandir(dir) as d:
#     for entry in d:
#         file = os.path.join(dir, entry.name)
#         print(*timeit.repeat("eef(file)", number=1, globals=globals(), repeat=5))

# for i in range(100000):
#     freef()
