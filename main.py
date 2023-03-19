import os
import time
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

    thing = StatsComputer(Path(r'Modern Replays/Game_20221227T194333.slp'))
    thing = thing.l_cancel_compute("NUT#356")
    print("done")