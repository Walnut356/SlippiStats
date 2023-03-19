import os
import timeit
from pathlib import Path

import polars as pl

from slippistats import *

directory = r"Modern Replays"
code = r"NUT#356"

# data = StatsComputer(Path(r'Modern Replays/Game_20221227T194333.slp')).take_hit_compute("NUT#356")
# data = data.to_polars()

# print(data)
# data.write_parquet("take_hit_test.parquet")
if __name__ == '__main__':
    # thing = get_stats(directory, code)

    # print("done")

    wavedashes = StatsComputer(r'test\replays\dash.slp')
    wavedashes = wavedashes.dash_compute(player=wavedashes.players[0])
    wavedashes.to_polars().write_parquet("dash_replay.parquet")
