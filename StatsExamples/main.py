import os
import timeit
from pathlib import Path

import polars as pl

from slippistats import *

data = StatsComputer(Path(r'Modern Replays/Game_20221227T194333.slp')).wavedash_compute("NUT#356")
data = data.to_polars()

print(data)
data.write_parquet("wd_test_2.parquet")