# ALOV-scripts

Crossplatform-toolkit to evaluate ALOV.

Most of these tools rely on ffmpeg or ffprobe for video decoding and metadata reading and thus require the respective executables in your $PATH or %PATH%. They are not redistributed with ALOV-scripts to avoid licensing issues and to allow you to update ffmpeg independently. On Linux, simply install a package providing ffmpeg using your packet manager. On Windows, either install ffmpeg and add it to your %PATH% environment variable, or simply copy ffmpeg.exe and ffprobe.exe to this directory.

## ALOV Sanity Checker

### Requirements

The biggest tool is the alov_sanity_checker.py Python script. It requires at least Python 3.5. If you want for any reason to avoid installing Python on the target system, an independent binary can be built for Windows using the build_exe.bat script (and similarly on Linux). Note that the building computer needs to run the _same_ os as the target computer, and have both Python and pip installed.

### Running

```
$ ./ALOV\ Sanity\ Checker.exe  --help
usage: ALOV Sanity Checker.exe [-h]
                               (-g BIK | -i PATH | --compare GAME BIK | -c GAME PATH)
                               [--quick] [--intermediate] [-v | -q | --debug]
                               [--no-log | --log-verbosity LOG_VERBOSITY | --short-log | --error-log]

ALOV sanity checker by HHL

optional arguments:
  -h, --help            show this help message and exit
  -g BIK, --get-info BIK
                        reads the supplied BIK file and outputs its properties
                        as json
  -i PATH, --index PATH
                        gets all bik files inside (sub)directory PATH and
                        outputs a json file with info of all biks
  --compare GAME BIK    compares the supplied BIK to vanilla properties stored
                        in database of GAME (ME1|ME2|ME3)
  -c GAME PATH, --check GAME PATH
                        checks all (supported) biks in PATH against the
                        database of given GAME (ME1|ME2|ME3)
  --quick, --fast       only read bik header instead of actually counting
                        frames
  --intermediate, --prores
                        check using Apple ProRes .mov intermediate files
                        instead of release biks
  -v, --verbosity       increase output (stdout) verbosity
  -q, --quiet, --silent
                        decrease output (stdout) verbosity to silent
  --debug               set stdout verbosity level to debug (maximum)
  --no-log              disable log file
  --log-verbosity LOG_VERBOSITY
                        set log verbosity
  --short-log           set log file verbosity to INFO
  --error-log           set log file verbosity to WARN
```
