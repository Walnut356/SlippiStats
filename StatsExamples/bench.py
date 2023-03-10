from pathlib import Path
import struct
from slippi import *
import timeit

# file = Path(r'Modern Replays/Game_20221227T194333.slp')

# batch_unpack = struct.Struct(">2856087B").unpack
# normal_unpack = struct.Struct(">B").unpack


# def batch():
#     file = Path(r'Modern Replays/Game_20221227T194333.slp')
#     with open(file, 'rb') as f:
#         thing = struct.unpack(">2856087B", f.read())
#     for eef in thing:
#         pass

# def normal():
#     file = Path(r'Modern Replays/Game_20221227T194333.slp')
#     with open(file, 'rb') as f:
#         for i in range(2856087):
#             thing = struct.unpack(">B", f.read(1))

# def batch_cache():
#     file = Path(r'Modern Replays/Game_20221227T194333.slp')
#     with open(file, 'rb') as f:
#         thing = batch_unpack(f.read())
#     for eef in thing:
#         pass

# def normal_cache():
#     file = Path(r'Modern Replays/Game_20221227T194333.slp')
#     with open(file, 'rb') as f:
#         for i in range(2856087):
#             thing = normal_unpack(f.read(1))
            

# def iter_unpack():
#     i = 0
#     file = Path(r'Modern Replays/Game_20221227T194333.slp')
#     with open(file, 'rb') as f:
#         thing = struct.iter_unpack(">B", f.read())
#     for eef in thing:
#         i += 1
#     print(i)

# def un_from():
#     file = Path(r'Modern Replays/Game_20221227T194333.slp')
#     with open(file, 'rb') as f:
#         thing = struct.unpack_from(">2856087B", f.read())
#     for eef in thing:
#         pass

# print(timeit.timeit(batch, number=1))
# print(timeit.timeit(normal, number=1))
# print(timeit.timeit(batch_cache, number=1))
# print(timeit.timeit(normal_cache, number=1))
# print(timeit.timeit(iter_unpack, number=1))
# print(timeit.timeit(un_from, number=1))

def eef():
    file = Path(r'Modern Replays/Game_20221227T194333.slp')
    Game(file)

eef()
# print(timeit.timeit(eef, number=100))