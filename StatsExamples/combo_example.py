import os, concurrent.futures, json

from slippi import *
from slippi.combo import generate_clippi_header

dolphin_queue = generate_clippi_header()

def combo_from_file(file, connect_code: str) -> ComboComputer:
    """Accept file path and connect code, process combos, and return"""
    replay:ComboComputer = ComboComputer()
    replay.prime_replay(file)
    replay.combo_compute(connect_code)
    for c in replay.combos:
        if(
            c.minimum_length(5) and
            c.did_kill and
            c.minimum_damage(60)):
            
            replay.json_export(c)
    
    return replay.queue


def multi_find_combos(dir_path, connect_code: str):
    with os.scandir(dir_path) as thing:
        with concurrent.futures.ProcessPoolExecutor() as executor:
            futures = {executor.submit(combo_from_file, os.path.join(dir_path, entry.name), connect_code) for entry in thing}

            for future in concurrent.futures.as_completed(futures):
                for result in future.result():
                    print("file processed")
                    dolphin_queue["queue"].append(result)

    with open("py_clip_combos.json", "w") as write_file:
        json.dump(dolphin_queue, write_file, indent=4)

    print("Done")


if __name__ == '__main__':
    # replay_dir = Path(input("Please enter the path to your directory of your replay files: "))
    # code_input = input("Please enter your connect code (TEST#123): ")

    replay_dir = r"E:\Slippi Replays\beep"
    code_input = "NUT#356"


    print("Processing...")
    with os.scandir(replay_dir) as thing:
        for entry in thing:
            combos = combo_from_file(os.path.join(replay_dir, entry.name), code_input)
            for c in combos:
                dolphin_queue["queue"].append(c)
            print(f"{entry.name} processed")

    with open("py_clip_combos.json", "w") as write_file:
        json.dump(dolphin_queue, write_file, indent=2)

    print("Done")


    # multi_find_combos(replay_dir, code_input)


