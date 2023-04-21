from datetime import datetime, timezone
import os
import time
from pathlib import Path

import polars as pl

import slippistats as slp
from slippistats.stats.stat_types import *

replay = Path(R"E:\Slippi Replays\Netplay\Game_20230112T004355.slp")
directory = Path(R"E:\Slippi Replays\Netplay")
code = R"NUT#356"

# thing = slp.Game(replay)
# thing = slp.StatsComputer(replay).l_cancel_compute("NUT#356").to_polars()

# print(thing.schema)

# if __name__ == "__main__":
# thing = slp.get_stats(directory, code)
# try:
#     thing.l_cancels.to_polars().write_parquet("l_c_test_2.parquet")
# except:
#     pass


# dfs = None
# count = 1
# with os.scandir(directory) as dir:
#     for entry in dir:
#         print(f"{count}: {entry.name}")
#         count += 1
#         if ".slp" not in entry.name:
#             continue

#         try:
#             df = slp.StatsComputer(os.path.join(directory, entry.name)).stats_compute(code)
#         except (slp.IdentifierError, slp.PlayerCountError):
#             continue

# if dfs is None:
#     dfs = df
# else:
#     if df is not None:
#         dfs = pl.concat([dfs, df], how="vertical")
#         print("concatting")
# dfs.write_parquet("l_c_test_2.parquet")
# print("file written")
