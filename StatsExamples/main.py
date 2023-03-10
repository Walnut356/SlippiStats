from pathlib import Path
import os
from slippi import *
import polars as pl
import timeit
import slippi.enums

replay = Game(Path(r'Modern Replays/Game_20221227T194333.slp'))

thing = StatsComputer(replay)

# frames = []
# flags = []
# for frame in replay.frames:
#     frames.append(frame.ports[0].leader)
#     flags.append(frame.ports[0].leader.post.flags)

# print("done")

# data = pl.read_csv(Path(r"StatsExamples/SSBM Data Sheet (1.02) - Character Attributes.csv"))

# thing = data.filter(pl.col("name") == "Falco")

# print(thing)
# print(thing.get_column("gravity"))
#r'Modern Replays/Game_20221227T194333.slp'

# dir_path = Path(r'Modern Replays')



# with os.scandir(Path(r'Modern Replays')) as dir:
#     for entry in dir:
#         file = os.path.join(dir_path, entry.name)
#         replay = Game(file)
#         if replay.start.stage == sid.Stage.FINAL_DESTINATION:

#             print(replay.start.stage)

#             grounds = [[0,0,0]]
#             all = []

#             for i in range(2):
#                 for frame in replay.frames:
#                         if frame.ports[i].leader.post.last_ground_id != grounds[-1][1]:
#                             grounds.append([frame.index, frame.ports[i].leader.post.last_ground_id, frame.ports[i].leader.post.position])
#                         all.append(frame.ports[i].leader.post.last_ground_id)

#             print(set(all))

#             pass