import os
import timeit
from pathlib import Path

import polars as pl

from slippistats import *

data = StatsComputer(Path(r'Modern Replays/Game_20221227T194333.slp')).take_hit_compute("NUT#356")
data = data.to_polars()

print(data)
data.write_parquet("take_hit_test.parquet")
