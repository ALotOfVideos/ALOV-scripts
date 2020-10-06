# ALOV-scripts

Crossplatform-toolkit to evaluate ALOV.

Most of these tools rely on [`ffmpeg` or `ffprobe`](https://ffmpeg.org) for video decoding and metadata reading and thus require the respective executables in your `$PATH` (Linux)/`%PATH%` (Windows).
They are not redistributed with ALOV-scripts to avoid licensing issues and to allow you to update ffmpeg independently.
On Linux, simply install a package providing ffmpeg using your packet manager (e.g. `sudo apt install ffmpeg`, `sudo pacman -Syu ffmpeg`).
On Windows, either install ffmpeg and add it to your `%PATH%` environment variable, or simply copy ffmpeg.exe and `ffprobe.exe` to this directory.

## ALOV Sanity Checker

The ALOV Sanity Checker is used to largely automate checking ALOV for integrity before release. Thus its releases happen in correspondence with ALOV itself.

### Requirements

The main tool is the `alov_sanity_checker.py` Python script. It requires at least Python 3.5.
If you want to avoid installing Python on the target system for some reason, an independent binary can be built for Windows using the `build_exe.bat` script (and similarly on Linux).
Note that the building computer needs to run the _same_ OS as the target computer, and have both Python and pip installed.

### Running

Run `./alov_sanity_checker.py --help` to display a complete list and explanation of arguments.

There are 4 modes:
1. `--get-info` to display info about a file
2. `--index` to read the properties from vanilla and store them
3. `--compare` to compare a single video to the properties of the vanilla video with the same name
4. `--check` to compare all videos in a whole set (i.e. ALOV release) to the according vanilla properties and also some additional stuff like completeness

This repo contains `index`es of the games (`MEX_complete.json`), so I don't expect you'd need to run the `index` mode.
Next to the `MEX_complete.json` databases, there is also `folder_mappings.json`.
This is needed for `--check`, because the directory structure of an ALOV release may not be the same of the installed game.
This mappings file allows the tool to find the correct matching file, even for non-unique file names, and will be updated with the newest ALOV release.
If you are `check`ing something else, e.g. `--intermediate`, and have a different directory structure, you can edit the mappings accordingly.
It maps the actual folder your file is in on the left side to the folder the file will install to on the right side, with the exception of mods which I just store with a certain structure.
