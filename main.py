import os
import time
from pathlib import Path

import polars as pl
import pandas as pd

from slippistats import *

directory = Path(r"Modern Replays")
code = r"NUT#356"

peach_file = Path(r"Modern Replays/Game_20221227T210010.slp")

data = StatsComputer(Path(r'Modern Replays/Game_20221227T194333.slp')).take_hit_compute("NUT#356")
data = data.to_polars()
data.to_pandas().to_excel("take_hit_data.xlsx")

# print(data)
# data.write_parquet("shield_drop_test.parquet")
