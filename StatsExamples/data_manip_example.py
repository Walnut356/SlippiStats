import polars as pl

wd_df = pl.read_parquet(r"wavedashdata.parquet")

print(wd_df)

temp = pl.read_parquet("wavedashdata_temp.parquet")

print(temp.sort("DateTime"))


# left = wd_df.filter(pl.col("Char") == "FALCO")

# right = wd_df.filter(pl.col("Char") == "MARTH")

# l_angles = left.get_column("angle")

# l_avg = l_angles.sum()/len(l_angles)

# r_angles = right.get_column("angle")

# r_avg = r_angles.sum()/len(r_angles)

# print(len(l_angles))
# print(l_avg)
# print(len(r_angles))
# print(r_avg)