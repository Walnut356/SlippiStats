import os
import timeit
from pathlib import Path

import polars as pl

from slippistats import *

data = StatsComputer(Path(r'Modern Replays/Game_20221227T194333.slp')).dash_compute("NUT#356")
data = data.to_polars()

print(data)
data.write_parquet("dash_test.parquet")