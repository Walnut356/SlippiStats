# py-slippi-stats

Please refer to the [wiki](https://github.com/Walnut356/py-slippi-stats/wiki) for quick start and API reference

py-slippi-stats is a Python parser for [.slp](https://github.com/project-slippi/slippi-wiki/blob/master/SPEC.md) game replay files for [Super Smash Brothers Melee](https://en.wikipedia.org/wiki/Super_Smash_Bros._Melee) for the Nintendo GameCube. These replays are generated by Jas Laferriere's [Project Slippi](https://github.com/JLaferri/project-slippi), which runs on a Wii or the [Dolphin](https://dolphin-emu.org/) emulator.

## Overview

Py-slippi-stats is a library for slippi replay parsing and automatic stat/combo generation. It is based heavily on both slippi-js and py-slippi, though with some modifications. 

The goal of py-slippi-stats is to provide a set of more useful, accurate, and detailed statistics than what slippi-js currently offers. The stats are targeted towards competitive players, with a notable absence of some "novelty" stats like APM. The output integrates easily with existing data science libraries and can provide indications for where a player should improve, as well as tracking that improvement over time.

## Features

* Combo generation with an enhanced algorithm and togglable criteria (with clippi/dolphin-compatible json output)

* Stat generation with useful, high detail fields

* ~70-90% faster replay parsing compared to py-slippi

![image](https://user-images.githubusercontent.com/39544927/234795192-cb72149d-4d07-4d11-b8d5-46d74b143bab.png)


* Effortless conversion to Pandas/Polars DataFrames


## Differences from Py-Slippi

Py-slippi-stats originated as a fork of py-slippi, which was meant to be merged in at some point. Unfortunately, the scope increased a lot, the dev behind py-slippi has shifted focus from python to rust's Peppi parser, and the changes required to make stats work resulted in more and more breaking changes from py-slippi's existing framework. Below are some of the major changes:

* Support for all slippi replay features through version 3.14.0

* Minimum python version 3.7 -> 3.10

* Live parsing is no longer supported

* All slippi file metrics are present in the output regardless of adjacent stats (e.g. `hitstun` -> `misc_timer`, no longer requires hitstun bitflag to populate)

* More robust enums including character-specific states and ground ID's for tournament legal stages.

* Many variables renamed to keep consistency with community and/or slippi file spec (e.g. `damage` -> `percent`)

* Some class structures have been flattened (e.g. `slippi.version` -> `slippi_version`, `metadata.player[i].netplay.code` -> `metadata.player[i].connect_code`)

* Parsing code has been heavily modified to maximize speed

* Additional dependencies for data processing support

* Heavily modified file structure for scalability

* Some base classes and operator overloads have been added, modified, or removed

## Known issues/limitations

* Stats/combo generation support only games with 2 players. Doubles stats/combos are not supported.


