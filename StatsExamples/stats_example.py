from pathlib import Path
import timeit
import os, concurrent.futures, datetime

import polars as pl
from slippi import *

# c_code = "NUT#356"
# file = Path(r"Modern Replays/ACTI#799 (Falcon) vs NUT#356 (Falco) on FoD - 12-15-22 02.06am .slp")
# replay = Game(file)
# stats = StatsComputer()
# stats.prime_replay(replay)
# stats.stats_compute("NUT#356")

def get_default_header(stats_computer: StatsComputer, connect_code: str) -> dict:
    
    formatted_date = stats_computer.metadata.date.replace(tzinfo=None)
    # total number of frames, starting when the player has control, in seconds
    formatted_time = datetime.timedelta(seconds=((stats_computer.metadata.duration)/60)) 

    [player_port], opponent_port = stats_computer.generate_player_ports(connect_code)
    
    header = {
            "match_id" : stats_computer.rules.match_id,
            "date_time" : formatted_date, 
            "duration" : formatted_time,
            "ranked" : stats_computer.rules.is_ranked,
            "win" : stats_computer.is_winner(player_port),
            "char" : id.InGameCharacter(list(stats_computer.players[player_port].characters.keys())[0]).name, #lmao
            "opnt_Char" : id.InGameCharacter(list(stats_computer.players[opponent_port].characters.keys())[0]).name
            }

    return header

 
def get_wavedash_data(replay, connect_code) -> dict:
    stats = StatsComputer()
    stats.prime_replay(replay)
    stats.wavedash_compute(connect_code)
    
    header = get_default_header(stats, connect_code)
    wd_data = [header | wavedash.__dict__ for wavedash in stats.data.wavedash]
    return wd_data


def get_dash_data(replay, connect_code) -> dict:
    stats = StatsComputer()
    stats.prime_replay(replay)
    stats.wavedash_compute(connect_code)

    header = get_default_header(stats, connect_code)
    dash_data = [header | dash.__dict__ for dash in stats.data.dash]
    return dash_data


def get_tech_data(replay, connect_code) -> dict:
    stats = StatsComputer()
    stats.prime_replay(replay)
    stats.wavedash_compute(connect_code)

    header = get_default_header(stats, connect_code)
    tech_data = [header | tech.__dict__ for tech in stats.data.tech]
    return tech_data

def get_take_hit_data(replay, connect_code) -> dict:
    stats = StatsComputer()
    stats.prime_replay(replay)
    stats.wavedash_compute(connect_code)

    header = get_default_header(stats, connect_code)
    take_hit_data = [header | take_hit.__dict__ for take_hit in stats.data.take_hit]
    return take_hit_data

def get_l_cancel_data(replay, connect_code) -> dict:
    stats = StatsComputer()
    stats.prime_replay(replay)
    stats.wavedash_compute(connect_code)

    header = get_default_header(stats, connect_code)
    l_cancel_data = [header | l_cancel.__dict__ for l_cancel in stats.data.l_cancel]
    return l_cancel_data

def get_general_data(replay, connect_code) -> dict:
    stats = StatsComputer()
    stats.prime_replay(replay)
    stats.wavedash_compute(connect_code)

    header = get_default_header(stats, connect_code)

    #TODO aggregate data from other data outputs

def stats_from_file(file, connect_code: str) -> pl.DataFrame:
    """Accept file path and connect code, process combos, and return"""
    print(file)
    data_frame = pl.DataFrame(get_wavedash_data(file, connect_code))
    try: 
        data_frame.sort("date_time")
    except:
        data_frame = None
    return data_frame


def multi_find_stats(dir_path, connect_code: str):
    dfs = None
    ind = 0
    with os.scandir(dir_path) as thing:
    #     for entry in thing:
    #         df = stats_from_file(os.path.join(dir_path, entry.name), connect_code)
    #         print("file processed")
    #         if df is not None:
    #             doodad = pl.read_parquet("wavedashdata.parquet")
    #             doodad = pl.concat([doodad, df], how='vertical')
    #             print(doodad)
    #             doodad.write_parquet("wavedashdata.parquet")
    #             print("file written")
        with concurrent.futures.ProcessPoolExecutor() as executor:
            futures = {executor.submit(stats_from_file, os.path.join(dir_path, entry.name), connect_code) for number, entry in enumerate(thing)}
            
            for future in concurrent.futures.as_completed(futures):
                print(f"processed {ind}")
                ind +=1
                if future.result() is not None:
                    if dfs is None:
                        dfs = future.result()
                        print("creating initial")
                    else:
                        dfs = pl.concat([dfs, future.result()], how='vertical')
                        print("concatting")
                    dfs.write_parquet("wavedashdata_temp.parquet")
                    print("file written")

    # print("start concat")
    # doodad = pl.concat(dfs, how='vertical')
    # print("start write")
    # doodad.write_parquet("wavedashdata_temp.parquet")
    print("Done")



if __name__ == '__main__':
    replay_dir = Path(input("Please enter the path to your directory of your replay files: "))
    code_input = input("Please enter your connect code (TEST#123): ")

    replay_dir = Path(r"C:\Users\ant_b\Documents\Coding Projects\starcraft calculator\sc2calc\py-slippi\Modern Replays")
    code_input = "NUT#356"
    
    print("Processing...")
    multi_find_stats(replay_dir, code_input)