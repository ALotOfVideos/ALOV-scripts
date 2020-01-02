#!/usr/bin/env python3

# A Lot of Videos (ALOV) sanity checker by HHL
# checks ALOV release for completeness by comparing frame counts to vanilla
# github URL
#
# requirements: python 3.5, ffprobe (ffmpeg)

import os.path
from os import sep
import sys
import subprocess as sp
import json
from datetime import datetime
import argparse
import glob
import math
import re

verbosity = 1
log_to_file = True
logfile = None
log_verbosity = 2

ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')

def log(s, level=2):
    global verbosity
    global log_to_file
    global logfile
    # verbosity levels:
    # 0 WARN
    # 1 INFO
    # 2 ALL
    # 3 DEBUG
    if level <= verbosity:
        if verbosity == 3:
            s = "(seriousness %d) %s" % (level, s)
        print(s, end='')

    if log_to_file and level <= log_verbosity:
        if log_verbosity == 3:
            s = "(seriousness %d) %s" % (level, s)
        print(ansi_escape.sub('', s), end='', file=logfile)

def error(s):
    # always print errors
    log("\033[31m%s\033[0m" % s, 0)

def log_ok(s, level=2):
    log("\033[32m%s\033[0m" % s, level)

def log_info(s, level=1):
    log("\033[32;7m%s\033[0m" % s, level)

def debug(s, level=3):
    log(s, level)

def isRes(input, w, h):
    return (input.get("width") == w and input.get("height") == h)

def is4K(input):
    return isRes(input, 3840, 2160)

def is1440p(input):
    return isRes(input, 2560, 1440)

def is1081p(input):
    return isRes(input, 1920, 1081)

def is1080p(input):
    return isRes(input, 1920, 1080)

def getBikProperties(f):
    if not os.path.isfile(f):
        error("file %s does not exist\n" % f)
        sys.exit(1)

    ffmpeg_command = ["ffprobe", "-v", "quiet", "-hide_banner", "-select_streams", "v", "-print_format", "json", "-count_frames", "-show_entries", "stream=filename,nb_read_frames,r_frame_rate,width,height", "%s" % f]
    probe = sp.Popen(ffmpeg_command, stdout=sp.PIPE)
    probe_bik = json.loads(probe.stdout.read())

    bik = {
        "name": os.path.basename(f),
        "width": probe_bik.get("streams")[0].get("width"),
        "height": probe_bik.get("streams")[0].get("height"),
        "fps": round(eval(probe_bik.get("streams")[0].get("r_frame_rate")), 2),
        "frame_count": int(probe_bik.get("streams")[0].get("nb_read_frames"))
        }

    return bik

def index(d):
    if (not os.path.isdir(d)):
        error("directory %s does not exist\n" % d)
        sys.exit(1)

    log("indexing %s\n" % d, level=0)

    while True:
        outfile = "alov_index_%s" % datetime.now().strftime("%y%m%dT%H%M")
        outfile = input("choose output database file name: [%s.json]: " % outfile) or outfile
        if outfile[-5:] != ".json":
            outfile += ".json"
        if not os.path.isfile(outfile):
            break
    log("output database: %s\n" % outfile)
    log("\n", level=0)

    biks = sorted(glob.glob("%s%s**%s*.bik" % (d, os.sep, os.sep), recursive=True), key=str.lower)

    total = len(biks)
    mag = math.floor(math.log(total, 10)) + 1
    log_string = "({:0" + str(mag) + "d}/{:0" + str(mag) + "d}) reading {:s}\n"
    count = 0
    l = list()
    for f in biks:
        count += 1
        log(log_string.format(count, total, f), level=0)
        l.append(getBikProperties(f))

    with open(outfile, 'w') as out:
        json.dump(l, out, indent=0)

    log("\n", level=0)
    log("saved bik properties to %s\n" % outfile, level=0)

def compare(db_path, f):
    if (not os.path.isfile(db_path)):
        error("database %s does not exist\n" % db_path)
        return 1
    if (not os.path.isfile(f)):
        error("file %s does not exist\n" % f)
        return 1

    # TODO this globally instead of each time
    with open(db_path, 'r') as db_fp:
        db = json.load(db_fp)

    log("checking %s\n" % f, level=0)

    name = os.path.basename(f)
    bik = getBikProperties(f)
    vanilla = dict()
    for v in db:
        if (v.get("name") == name):
            vanilla = v
            break

    errors = 0
    capitalization_string = "{:>8s} {:s}\n"
    check_string = "{:<25s}"
    mag = math.floor(math.log(max(vanilla.get("frame_count", 0), bik.get("frame_count", 0)), 10)) + 1
    frames_string = "{:>10s} {:0" + str(mag) + "d} {:s} {:.2f} {:s}\n"

    # check existence
    if (vanilla.get("name") is None):
        log(check_string.format("1. checking existence:"), level=0)
        # search case-insensitive
        for v in db:
            if (v.get("name").lower() == name.lower()):
                vanilla = v
                break
        if (vanilla.get("name") is None):
            error("WARNING: cutscene not found in vanilla database\n")
            errors += 1
            return errors
        else:
            error("WARNING: cutscene uses wrong capitalization\n")
            log(capitalization_string.format("vanilla:", v.get("name")), level=0)
            log(capitalization_string.format("found:", name), level=0)
            errors += 1
    else:
        log(check_string.format("1. checking existence:"))
        log_ok("OK: cutscene found in database\n")

    # check resolution
    if is1081p(bik):
        log(check_string.format("2. checking resolution:"))
        log_ok("OK: 1081p\n")
    elif is1440p(bik):
        log(check_string.format("2. checking resolution:"))
        log_ok("OK: 1440p\n")
    elif is4K(bik):
        log(check_string.format("2. checking resolution:"))
        log_ok("OK: 4K\n")
    elif (is1080p(bik)):
        log(check_string.format("2. checking resolution:"), level=0)
        error("WARNING: %s is 1080p -> should be 1081p\n" % f)
        errors += 1
    else:
        log(check_string.format("2. checking resolution:"), level=0)
        error("WARNING: resolution is not 1081p/1440p/4K (%dx%d)\n" % (bik.get("width"), bik.get("height")))
        errors += 1

    # check frame count
    bfc = bik.get("frame_count")
    bfps = bik.get("fps")
    vfc = vanilla.get("frame_count")
    vfps = vanilla.get("fps")

    if bfc == vfc and bfps == vfps:
        log(check_string.format("3. checking frame count:"))
        log_ok("OK: frame counts match (%d)\n" % vfc)
    else:
        factor = bfps / vfps
        # TODO: sped up without interpolation
        if factor >= 1.9 and bfc == round(factor * vfc):
            log(check_string.format("3. checking frame count:"), level=1)
            log_info("OK: frames were interpolated\n")
            log(frames_string.format("vanilla:", vfc, "frames @", vfps, "FPS"), level=1)
            log(frames_string.format("found:", bfc, "frames @", bfps, "FPS"), level=1)
        elif (factor != 1 and factor >= 29.97/30 and factor <= 30/29.97):
            if bfc == vfc:
                log(check_string.format("3. checking frame count:"), level=1)
                log_info("OK: FPS was rounded (%0.2f -> %0.2f)\n" % (vfps, bfps))
            elif bfc == round(factor * vfc):
                log(check_string.format("3. checking frame count:"), level=1)
                log_info("OK: frames were interpolated\n")
                log(frames_string.format("vanilla:", vfc, "frames @", vfps, "FPS"), level=1)
                log(frames_string.format("found:", bfc, "frames @", bfps, "FPS"), level=1)
            # else:
            #     log(check_string.format("3. checking frame count:"), level=0)
            #     error("ERROR: unhandled situation\n")
            #     log(frames_string.format("vanilla:", vfc, "frames @", vfps, "FPS"), level=0)
            #     log(frames_string.format("found:", bfc, "frames @", bfps, "FPS"), level=0)
        else:
            log(check_string.format("3. checking frame count:"), level=0)
            error("WARNING: frame rate/count mismatch\n")
            log(frames_string.format("vanilla:", vfc, "frames @", vfps, "FPS"), level=0)
            log(frames_string.format("found:", bfc, "frames @", bfps, "FPS"), level=0)

            if bfps == vfps and bfc < factor * vfc:
                log("{:>10s} {:s}\n".format("should be:", "vanilla probably"), level=0)
            else:
                if not round(bfps) == 15:
                    log(frames_string.format("should be:", bfc, "frames @", bfps, "FPS"), level=0)
                    if not factor == 2:
                        log(frames_string.format("or:", 2*vfc, "frames @", 2*vfps, "FPS"), level=0)
                else:
                    log(frames_string.format("should be:", 4*bfc, "frames @", 4*bfps, "FPS"), level=0)
                log("(or vanilla)\n", level=0)
            errors += 1
    return errors

def check(db_path, d):
    if (not os.path.isfile(db_path)):
        error("database %s does not exist\n" % db_path)
        return 1
    if (not os.path.isdir(d)):
        error("directory %s does not exist\n" % d)
        return 1

    log("checking ALOV release at %s\n\n" % d, level=0)

    # TODO this globally instead of each time
    with open(db_path, 'r') as db_fp:
        db = json.load(db_fp)

    total = len(db)
    mag = math.floor(math.log(total, 10)) + 1
    log_string = "({:0" + str(mag) + "d}/{:0" + str(mag) + "d}) "
    count = 0
    errors = 0

    biks = sorted(glob.glob("%s%s**%s*.bik" % (d, os.sep, os.sep), recursive=True), key=str.lower)

    for bik in biks:
        count += 1
        log(log_string.format(count, total), level=0)
        errors += compare(db_path, bik)
        # TODO pop these to display list of missing in the end

    log("\n", level=0)
    if count != total:
        mismatch_string = "{:>8s} {:3d}\n"
        error(mismatch_string.format("vanilla:", total))
        error(mismatch_string.format("found:", count))
        errors += total - count
    else:
        log_ok("found %d files in database\n")
        log("\033[32;1mrelease is complete.\033[0m\n")

    return errors

def init_parser():
    parser = argparse.ArgumentParser(description='ALOV sanity checker by HHL')
    actiongroup = parser.add_mutually_exclusive_group(required=True) # TODO name group once feature releases
    actiongroup.add_argument('-g', '--get-info', nargs=1, metavar='BIK', help='reads the supplied BIK file and outputs its properties as json')
    actiongroup.add_argument('-i', '--index', nargs=1, metavar='PATH', help='gets all bik files inside (sub)directory PATH and outputs a json file with info of all biks')
    actiongroup.add_argument('--compare', nargs=2, metavar=('DB','BIK'), help='compares the supplied BIK to vanilla properties stored in DB')
    actiongroup.add_argument('-c', '--check', nargs=2, metavar=('DB','PATH'), help='checks all (supported) biks in PATH against the given DB (should hold info for either ME1/2/3)')

    verbositygroup = parser.add_mutually_exclusive_group()
    verbositygroup.add_argument("-v", "--verbosity", action="count", default=0, help="increase output (stdout) verbosity")
    verbositygroup.add_argument("-q", "--quiet", "--silent", action='store_const', const=-0, help="decrease output (stdout) verbosity to silent")
    verbositygroup.add_argument('--debug', action='store_const', const=3, help='set stdout verbosity level to debug (maximum)')
    loggroup = parser.add_mutually_exclusive_group()
    loggroup.add_argument('--no-log', action='store_const', const=False, help='disable log file')
    loggroup.add_argument("--log-verbosity", default=2, help="set log verbosity")
    loggroup.add_argument("--short-log", action='store_const', const=1, help="set log file verbosity to INFO")
    loggroup.add_argument("--error-log", action='store_const', const=0, help="set log file verbosity to WARN")
    return parser

def main():
    global verbosity
    global log_to_file
    global logfile
    global log_verbosity

    parser = init_parser()
    args = parser.parse_args()

    verbosity += args.verbosity
    verbosity = verbosity if args.quiet is None else args.quiet
    verbosity = verbosity if args.debug is None else args.debug
    log_to_file = True if args.no_log is None else args.no_log
    if log_to_file:
        logfile = open("alov_sanity_checker_%s.log" % datetime.now().strftime("%y%m%dT%H%M"), 'w')
    log_verbosity = args.log_verbosity
    log_verbosity = log_verbosity if args.error_log is None else args.error_log
    log_verbosity = log_verbosity if args.short_log is None else args.short_log

    log("%s\n" % args, level=3)

    errors = 0

    if args.get_info is not None:
        bik = getBikProperties(args.get_info[0])
        print(bik)
    elif args.index is not None:
        index(args.index[0])
    else:
        if args.compare is not None:
            errors = compare(args.compare[0], args.compare[1])
        elif args.check is not None:
            errors = check(args.check[0], args.check[1])

        log("\n", level=0)
        if errors > 0:
            error("%d issue(s) found\n" % errors)
        else:
            log_ok("no issues found\n", level=0)

    if log_to_file:
        logfile.close()

if __name__== "__main__":
    main()
