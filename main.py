import os
import time
from pathlib import Path

import polars as pl
import pandas as pd

import slippistats as slp


# thing = pl.read_parquet("take_hit_temp.parquet")

# thing = thing.filter(pl.col("opnt_chara") == "FOX")

# counts = thing.select([pl.col("*"), pl.col("last_hit_by").count().over("last_hit_by").alias("times_hit")])

# counts = counts.groupby(["last_hit_by", "times_hit"]).agg(pl.col("di_efficacy").mean())


# counts.write_parquet("fox_moves_3.parquet")

if __name__ == "__main__":
    # dfs = None
    # count = 0
    # directory = Path(R"E:\Slippi Replays\Netplay")
    # code = R"NUT#356"

    # peach_file = Path(R"Modern Replays/Game_20221227T210010.slp")
    # start = time.time()
    # thing = slp.get_stats(directory, code)
    # print(time.time() - start)
    # print("Done")

    thing = pl.read_parquet("take_hit_test_2.parquet")
    thing.to_pandas().to_excel("take_hit_test.xlsx")

# with os.scandir(directory) as dir:
#     for entry in dir:
#         print(entry.name)
#         if ".slp" not in entry.name:
#             continue
#         count += 1
#         print(count)
#         try:
#             df = slp.StatsComputer(os.path.join(directory, entry.name)).take_hit_compute(code).to_polars()
#         except slp.IdentifierError:
#             continue

#         if dfs is None:
#             dfs = df
#         else:
#             if df is not None:
#                 dfs = pl.concat([dfs, df], how="vertical")
#                 print("concatting")
# dfs.write_parquet("take_hit_test_2.parquet")
# print("file written")


# data = slp.StatsComputer(Path(r'Modern Replays/Game_20221227T194333.slp')).take_hit_compute("NUT#356")
# data = data.to_polars()
# data.to_pandas().to_excel("take_hit_data.xlsx")

# print(data)
# data.write_parquet("shield_drop_test.parquet")
