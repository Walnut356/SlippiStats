# import slippistats as slp
from pathlib import Path
import polars as pl

# replay_dir = Path(R"E:\Slippi Replays\Netplay")
# connect_code = "NUT#356"

# if __name__ == "__main__":
#     stats = slp.get_stats(replay_dir, connect_code)
#     pass
#     stats.wavedashes.write_parquet(R"StatsExamples\Output\wavedashes.parquet")
#     stats.dashes.write_parquet(R"StatsExamples\Output\dashes.parquet")
#     stats.techs.write_parquet(R"StatsExamples\Output\techs.parquet")
#     stats.take_hits.write_parquet(R"StatsExamples\Output\take_hits.parquet")
#     stats.l_cancels.write_parquet(R"StatsExamples\Output\l_cancels.parquet")
#     pass


def l_cancel_demo():
    l_cancel = pl.read_parquet(Path(R"StatsExamples\Output\l_cancels.parquet"))

    percent = l_cancel.filter(pl.col("character") == "FALCO").groupby("l_cancel").agg(pl.count())

    print(percent)

    by_move = l_cancel.filter(pl.col("character") == "FALCO").groupby(pl.col("move")).agg([pl.col("l_cancel").mean()])

    print(by_move)

    by_move_by_location = (
        l_cancel.filter(pl.col("character") == "FALCO")
        .groupby(pl.col("position"))
        .agg([pl.col("l_cancel").mean(), pl.count()])
    )

    print(by_move_by_location)

    by_opnt = (
        l_cancel.filter(pl.col("character") == "FALCO")
        .groupby(pl.col("opnt_character"))
        .agg([pl.col("l_cancel").mean(), pl.count()])
        .sort(pl.col("count"))
    )

    print(by_opnt)

    by_stocks = (
        l_cancel.filter(pl.col("character") == "FALCO")
        .groupby(pl.col("stocks_remaining"))
        .agg([pl.col("l_cancel").mean(), pl.count()])
    )

    print(by_stocks)
