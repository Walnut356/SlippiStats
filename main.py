import os
import time
from pathlib import Path

import polars as pl

from slippistats import *

directory = Path(r"Modern Replays")
code = r"NUT#356"

peach_file = Path(r"Modern Replays/Game_20221227T210010.slp")

# data = StatsComputer(Path(r'Modern Replays/Game_20221227T194333.slp')).take_hit_compute("NUT#356")
# data = data.to_polars()

# print(data)
# data.write_parquet("take_hit_test.parquet")
if __name__ == '__main__':
    thing = StatsComputer(peach_file)
    eef = thing.players[1].frames
    posts = []
    posts1 = []
    posts2 = []
    for frame in eef:
        posts.append(frame.post)
        posts1.append(frame.post.flags)
        posts2.append(frame.post.state)

    for i, post in enumerate(posts):
        if post.state in (341, 348):
            print(i)

    print("done")
