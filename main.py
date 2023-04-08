from datetime import datetime, timezone
import os
import time
from pathlib import Path

import polars as pl

import slippistats as slp
from slippistats.stats.stat_types import *

replay = Path(R"Modern Replays\Game_20221227T194333.slp")

directory = Path(R"E:\Slippi Replays\Netplay")
code = R"NUT#356"


thing = slp.StatsComputer(replay).tech_compute("NUT#356").to_polars()

print(thing)


# if __name__ == "__main__":

# target_name = R"StatsExamples\Output\wavedash_test.parquet"

# start = time.time()
# thing = slp.get_stats(directory, code, target_name)
# print(time.time() - start)
# print("Done")

# dfs = None
# count = 0
# with os.scandir(directory) as dir:
#     for entry in dir:
#         print(entry.name)
#         if ".slp" not in entry.name:
#             continue
#         count += 1
#         print(count)
#         try:
#             df = slp.StatsComputer(os.path.join(directory, entry.name)).wavedash_compute(code).to_polars()
#         except (slp.IdentifierError, slp.PlayerCountError):
#             continue

#         if dfs is None:
#             dfs = df
#         else:
#             if df is not None:
#                 dfs = pl.concat([dfs, df], how="vertical")
#                 print("concatting")
# dfs.write_parquet("wavedash_test.parquet")
# print("file written")
