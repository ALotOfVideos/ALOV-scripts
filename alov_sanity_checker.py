#!/usr/bin/env python3

# A Lot of Videos (ALOV) sanity checker by HHL
# checks ALOV release for completeness by comparing frame counts to vanilla
# github URL
#
# requirements: python 3.5, ffprobe (ffmpeg)

import os.path
from os import name as osname
import pathlib
import sys
import subprocess as sp
import json
from datetime import datetime
import argparse
import glob
import math
import re
from collections import Counter

quick = False
intermediate = False
filetype = ""

game: str
folder_mappings = None
global_db = None

verbosity = 1
log_to_file = False
logfile = None
log_verbosity = 2

ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')

def log(s, level=2):
    global verbosity
    global log_to_file
    global logfile
    global log_verbosity
    # verbosity levels:
    # 0 WARN
    # 1 INFO
    # 2 ALL
    # 3 DEBUG
    so = s
    sf = s
    if level <= verbosity:
        if verbosity == 3:
            so = "(seriousness %d) %s" % (level, s)
        # disable colors on windows for now
        # TODO curses colors? or colorama pkg? or? https://docs.python.org/3/howto/curses.html?highlight=color
        if osname == 'nt':
            print(ansi_escape.sub('', so), end='')
        else:
            print(so, end='')

    if log_to_file and level <= log_verbosity:
        if log_verbosity == 3:
            sf = "(seriousness %d) %s" % (level, s)
        print(ansi_escape.sub('', sf), end='', file=logfile)

def error(s):
    # always print errors
    log("\033[31m%s\033[0m" % s, 0)

def warning(s, level=1):
    log("\033[31;7m%s\033[0m" % s, level)

def log_ok(s, level=2):
    log("\033[32m%s\033[0m" % s, level)

def log_info(s, level=1):
    log("\033[32;7m%s\033[0m" % s, level)

def debug(s, level=3):
    log(s, level)

def isRes(i, w, h):
    return i.get("width") == w and i.get("height") == h

def is4K(i):
    return isRes(i, 3840, 2160)

def is1440p(i):
    return isRes(i, 2560, 1440)

def is1081p(i):
    return isRes(i, 1920, 1081)

def is1079p(i):
    return isRes(i, 1920, 1079)

def is1080p(i):
    return isRes(i, 1920, 1080)

def getMappings():
    global folder_mappings
    global game
    folder_mappings_path = 'folder_mappings.json'
    if folder_mappings is None:
        if not os.path.isfile(folder_mappings_path):
            error("folder mappings %s does not exist\n" % folder_mappings_path)
            return None
        with open(folder_mappings_path, 'r') as fm_fp:
            folder_mappings = json.load(fm_fp).get(game)
    return folder_mappings

def getDB():
    global global_db
    global game
    db_path = game + "_complete.json"
    if global_db is None:
        if not os.path.isfile(db_path):
            error("database %s does not exist\n" % db_path)
            return None
        with open(db_path, 'r') as db_fp:
            global_db = json.load(db_fp)
    return global_db

def getRelativeDir(p, to=''):
    if to == '':
        return str(pathlib.Path(*pathlib.Path(p).parts[1:-1]))
    return str(pathlib.Path(p).relative_to(to))

def getBikProperties(f, root=''):
    if not os.path.isfile(f):
        error("file %s does not exist\n" % f)
        sys.exit(1)

    ffmpeg_command = ["ffprobe", "-v", "quiet", "-hide_banner", "-select_streams", "v", "-print_format", "json", "-show_entries", "stream=filename,nb_read_frames,r_frame_rate,width,height,duration_ts", "%s" % f]
    if not quick:
        ffmpeg_command.append("-count_frames")
    probe = sp.Popen(ffmpeg_command, stdout=sp.PIPE)
    probe_bik = json.loads(probe.stdout.read())

    bik = {
        "name": os.path.basename(f),
        "dir": getRelativeDir(os.path.dirname(f), root),
        "width": probe_bik.get("streams")[0].get("width"),
        "height": probe_bik.get("streams")[0].get("height"),
        "fps": round(eval(probe_bik.get("streams")[0].get("r_frame_rate")), 2),
        "frame_count": int(probe_bik.get("streams")[0].get("nb_read_frames") if not quick else probe_bik.get("streams")[0].get("duration_ts")),
        "frame_count_header": int(probe_bik.get("streams")[0].get("duration_ts"))
        }

    return bik

def index(d):
    if not os.path.isdir(d):
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
        l.append(getBikProperties(f, d))

    with open(outfile, 'w') as out:
        json.dump(l, out, indent=0)

    log("\n", level=0)
    log("saved bik properties to %s\n" % outfile, level=0)

def compare(f, root=''):
    global quick
    global intermediate

    if not os.path.isfile(f):
        error("file %s does not exist\n" % f)
        return 1

    db = getDB()
    if db is None:
        error("database missing\n")
        return 1


    fm = getMappings()
    if fm is None:
        error("folder mappings missing\n")
        return 1

    bik = getBikProperties(f, root)
    realname = bik.get("name")
    name = realname
    if intermediate:
        name = realname[:-3] + "bik"
    realfolder = bik.get("dir")
    # DLC_MOD_ALOV_Optional contains single files mapped to various origins
    if realfolder == os.path.join("DLC_MOD_ALOV_Optional", "Movies") or \
       (realfolder == os.path.join("BASEGAME", "Movies") and name == "STA_ArrivalSEQ04a.bik"):
        realfolder = os.path.join(realfolder, name)
    if osname == 'nt':
        folder = fm.get(realfolder.replace('\\', '/'))
    else:
        folder = fm.get(realfolder)

    log("checking %s\n" % os.path.join(bik.get("dir"), realname), level=0)

    vanilla = dict()
    if root == '':
        # comparing a bik manually(?): best effort search
        for v in db:
            if v.get("name") == name:
                vanilla = v
                break
    else:
        # checking a release: we know the corresponding folder
        for v in db:
            if v.get("dir") == folder and v.get("name") == name:
                vanilla = v
                break

    log("ALOV file:    %s%s%s\n" % (bik.get("dir"), os.sep, name), level=3)
    log("resolved dir: %s\n" % folder, level=3)
    log("vanilla file: %s%s%s\n" % (vanilla.get("dir"), os.sep, vanilla.get("name")), level=3)

    errors = {"db": 0, "res": 0, "frame": 0}
    capitalization_string = "{:>8s} {:s}\n"
    check_string = "{:<25s}"
    mag = math.floor(math.log(max(vanilla.get("frame_count", 0), bik.get("frame_count", 0)), 10)) + 1
    frames_string = "{:>10s} {:0" + str(mag) + "d} {:s} {:.2f} {:s}\n"
    header_string = "{:>7s} {:0" + str(mag) + "d}\n"

    # check existence
    if vanilla.get("name") is None:
        log(check_string.format("1. checking existence:"), level=0)
        # search case-insensitive
        if root == '':
            for v in db:
                if v.get("name").lower() == name.lower():
                    vanilla = v
                    break
        else:
            for v in db:
                if v.get("dir") == folder and v.get("name").lower() == name.lower():
                    vanilla = v
                    break
        if vanilla.get("name") is None:
            error("WARNING: cutscene not found in vanilla database\n")
            errors["db"] += 1
            return errors
        else:
            error("WARNING: cutscene uses wrong capitalization\n")
            log(capitalization_string.format("vanilla:", vanilla.get("name")), level=0)
            log(capitalization_string.format("found:", name), level=0)
            errors["db"] += 1
    else:
        log(check_string.format("1. checking existence:"))
        log_ok("OK: cutscene found in database\n")

    # check resolution
    if is1081p(bik):
        log(check_string.format("2. checking resolution:"))
        log_ok("OK: 1081p\n")
    elif is1079p(bik):
        log(check_string.format("2. checking resolution:"))
        log_ok("OK: 1079p\n")
    elif is1440p(bik):
        log(check_string.format("2. checking resolution:"))
        log_ok("OK: 1440p\n")
    elif is4K(bik):
        log(check_string.format("2. checking resolution:"))
        log_ok("OK: 4K\n")
    elif is1080p(bik):
        log(check_string.format("2. checking resolution:"), level=0)
        error("WARNING: %s is 1080p -> should be 1079p\n" % f)
        errors["res"] += 1
    else:
        log(check_string.format("2. checking resolution:"), level=0)
        error("WARNING: resolution is not 1079p/1081p/1440p/4K (%dx%d)\n" % (bik.get("width"), bik.get("height")))
        errors["res"] += 1

    # check frame count
    bfc = bik.get("frame_count")
    bfps = bik.get("fps")
    vfc = vanilla.get("frame_count")
    vfps = vanilla.get("fps")

    debug_path = list()

    if bfc == vfc and bfps == vfps:
        debug_path.append("if bfc == vfc and bfps == vfps:")
        log(check_string.format("3. checking frame count:"))
        log_ok("OK: frame counts match (%d)\n" % vfc)
    else:
        debug_path.append("else")
        factor = bfps / vfps
        factor_thresh = 29.7/30
        # TODO: sped up without interpolation
        if factor > 1/factor_thresh and bfc == round(factor * vfc):
            debug_path.append("if factor > 1/factor_thresh and bfc == round(factor * vfc):")
            log(check_string.format("3. checking frame count:"), level=1)
            log_info("OK: frames were interpolated\n")
            log(frames_string.format("vanilla:", vfc, "frames @", vfps, "FPS"), level=1)
            log(frames_string.format("found:", bfc, "frames @", bfps, "FPS"), level=1)
        elif factor != 1 and factor >= factor_thresh and factor <= 1/factor_thresh:
            debug_path.append("elif (factor != 1 and factor >= factor_thresh and factor <= 1/factor_thresh):")
            if bfc == vfc:
                debug_path.append("if bfc == vfc:")
                log(check_string.format("3. checking frame count:"), level=1)
                log_info("OK: FPS rounded (%0.2f -> %0.2f)\n" % (vfps, bfps))
            elif bfc == round(factor * vfc):
                debug_path.append("elif bfc == round(factor * vfc):")
                log(check_string.format("3. checking frame count:"), level=1)
                log_info("OK: frames were interpolated\n")
                log(frames_string.format("vanilla:", vfc, "frames @", vfps, "FPS"), level=1)
                log(frames_string.format("found:", bfc, "frames @", bfps, "FPS"), level=1)
            # else:
            #     log(check_string.format("3. checking frame count:"), level=0)
            #     error("ERROR: unhandled situation\n")
            #     log(frames_string.format("vanilla:", vfc, "frames @", vfps, "FPS"), level=0)
            #     log(frames_string.format("found:", bfc, "frames @", bfps, "FPS"), level=0)
        elif vfps in (15,20) and bfps == 60 and bfc == vfc:
            debug_path.append("elif vfps in (15,20) and bfps == 60 and bfc == vfc:")
            log(check_string.format("3. checking frame count:"), level=1)
            log_info("OK: FPS upgraded (%0.2f -> %0.2f)\n" % (vfps, bfps))
        elif bfps == vfps and vfc > bfc and bfc >= vfc - 3:
            debug_path.append("elif bfps == vfps and vfc > bfc and bfc >= vfc - 3:")
            log(check_string.format("3. checking frame count:"), level=1)
            warning("WARNING: missing a few frames\n")
            log(frames_string.format("vanilla:", vfc, "frames @", vfps, "FPS"), level=1)
            log(frames_string.format("found:", bfc, "frames @", bfps, "FPS"), level=1)
            errors["frame"] += 1
        elif factor < factor_thresh:
            debug_path.append("elif factor < factor_thresh:")
            log(check_string.format("3. checking frame count:"), level=0)
            log("WARNING: FPS downgraded", level=0)
            errors["frame"] += 1
        else:
            debug_path.append("else:")
            log(check_string.format("3. checking frame count:"), level=0)
            if bfps == vfps and bfc < factor * vfc:
                debug_path.append("if bfps == vfps and bfc < factor * vfc:")
                error("WARNING: missing frames\n")
                log(frames_string.format("vanilla:", vfc, "frames @", vfps, "FPS"), level=0)
                log(frames_string.format("found:", bfc, "frames @", bfps, "FPS"), level=0)
                log("{:>10s} {:s}\n".format("should be:", "vanilla probably"), level=0)
            else:
                debug_path.append("else:")
                error("WARNING: frame rate/count mismatch\n")
                log(frames_string.format("vanilla:", vfc, "frames @", vfps, "FPS"), level=0)
                log(frames_string.format("found:", bfc, "frames @", bfps, "FPS"), level=0)
                if not round(bfps) == 15:
                    debug_path.append("if not round(bfps) == 15:")
                    log(frames_string.format("should be:", round(factor*vfc), "frames @", round(factor*vfps), "FPS"), level=0)
                    if not factor == 2:
                        debug_path.append("if not factor == 2:")
                        log(frames_string.format("or:", 2*vfc, "frames @", 2*vfps, "FPS"), level=0)
                else:
                    debug_path.append("else:")
                    log(frames_string.format("should be:", 4*vfc, "frames @", 4*vfps, "FPS"), level=0)
                    log(frames_string.format("or:", vfc, "frames @", 4*vfps, "FPS"), level=0)
                log("(or vanilla)\n", level=0)
            errors["frame"] += 1

    log(debug_path, level=3)

    # check header integrity
    if not quick:
        if bik.get("frame_count") == bik.get("frame_count_header"):
            log(check_string.format("4. checking header:"))
            log_ok("OK: header contains actual number of frames\n")
        else:
            log(check_string.format("4. checking header"), level=0)
            error("WARNING: header does not indicate actual number of frames\n")
            log(header_string.format("header:", bik.get("frame_count_header")), level=0)
            log(header_string.format("actual:", bik.get("frame_count")), level=0)

    return errors

def check(d):
    global filetype
    
    if not os.path.isdir(d):
        error("directory %s does not exist\n" % d)
        return 1

    log("checking ALOV release at %s\n\n" % d, level=0)

    db = getDB()
    if db is None:
        error("database missing\n")
        return 1

    total = len(db)
    mag = math.floor(math.log(total, 10)) + 1
    log_string = "({:0" + str(mag) + "d}/{:0" + str(mag) + "d}) "
    count = 0
    errors = {"db": 0, "res": 0, "frame": 0, "missing": 0}

    biks = sorted(glob.glob("%s%s**%s*.%s" % (d, os.sep, os.sep, filetype), recursive=True), key=str.lower)

    for bik in biks:
        count += 1
        log(log_string.format(count, total), level=0)
        errors = dict(Counter(errors) + Counter(compare(bik, d)))
        # TODO pop these to display list of missing in the end

    count -= errors.get("db", 0)

    log("\n", level=0)
    if count != total:
        mismatch_string = "{:>8s} {:3d}\n"
        error(mismatch_string.format("vanilla:", total))
        error(mismatch_string.format("found:", count))
        errors = dict(Counter(errors) + Counter({"missing": total - count}))
    else:
        log_ok("found %d files in database\n")
        log("\033[32;1mrelease is complete.\033[0m\n")

    return errors

def init_parser():
    parser = argparse.ArgumentParser(description='ALOV sanity checker by HHL')
    actiongroup = parser.add_mutually_exclusive_group(required=True) # TODO name group once feature releases
    actiongroup.add_argument('-g', '--get-info', nargs=1, metavar='BIK', help='reads the supplied BIK file and outputs its properties as json')
    actiongroup.add_argument('-i', '--index', nargs=1, metavar='PATH', help='gets all bik files inside (sub)directory PATH and outputs a json file with info of all biks')
    actiongroup.add_argument('--compare', nargs=2, metavar=('GAME','BIK'), help='compares the supplied BIK to vanilla properties stored in database of GAME (ME1|ME2|ME3)')
    actiongroup.add_argument('-c', '--check', nargs=2, metavar=('GAME','PATH'), help='checks all (supported) biks in PATH against the database of given GAME (ME1|ME2|ME3)')

    parser.add_argument('--quick', '--fast', action='store_const', const=True, default=False, help='only read bik header instead of actually counting frames')
    parser.add_argument('--intermediate', '--prores', action='store_const', const=True, default=False, help='check using Apple ProRes .mov intermediate files instead of release biks')

    verbositygroup = parser.add_mutually_exclusive_group()
    verbositygroup.add_argument("-v", "--verbosity", action="count", default=0, help="increase output (stdout) verbosity")
    verbositygroup.add_argument("-q", "--quiet", "--silent", action='store_const', const=-0, help="decrease output (stdout) verbosity to silent")
    verbositygroup.add_argument('--debug', action='store_const', const=3, help='set stdout verbosity level to debug (maximum)')
    loggroup = parser.add_mutually_exclusive_group()
    loggroup.add_argument('--no-log', action='store_const', const=False, default=True, help='disable log file')
    loggroup.add_argument("--log-verbosity", default=2, help="set log verbosity")
    loggroup.add_argument("--short-log", action='store_const', const=1, help="set log file verbosity to INFO")
    loggroup.add_argument("--error-log", action='store_const', const=0, help="set log file verbosity to WARN")
    return parser

def main():
    global quick
    global intermediate
    global filetype
    global game
    global verbosity
    global log_to_file
    global logfile
    global log_verbosity

    parser = init_parser()
    args = parser.parse_args()

    if args.compare is not None and args.compare[0] not in ("ME1", "ME2", "ME3"):
        error("wrong value for GAME: %s. Must be either ME1, ME2 or ME3.\n" % args.compare[0])
        exit(1)
    elif args.compare is not None:
        game = args.compare[0]
    if args.check is not None and args.check[0] not in ("ME1", "ME2", "ME3"):
        error("wrong value for GAME: %s. Must be either ME1, ME2 or ME3.\n" % args.check[0])
        exit(1)
    elif args.check is not None:
        game = args.check[0]

    quick = args.quick
    intermediate = args.intermediate
    filetype = "bik"
    if intermediate:
        filetype = "mov"

    verbosity += args.verbosity
    verbosity = verbosity if args.quiet is None else args.quiet
    verbosity = verbosity if args.debug is None else args.debug
    log_to_file = args.no_log
    log_path = "alov_sanity_checker_%s_%s.log" % (game, datetime.now().strftime("%y%m%dT%H%M"))
    if log_to_file:
        logfile = open(log_path, 'w')
        log("opened log file %s\n\n" % log_path, level=3)
    log_verbosity = args.log_verbosity
    log_verbosity = log_verbosity if args.error_log is None else args.error_log
    log_verbosity = log_verbosity if args.short_log is None else args.short_log

    log("%s\n\n" % args, level=3)

    errors = {"db": 0, "res": 0, "frame": 0, "missing": 0}

    if args.get_info is not None:
        bik = getBikProperties(args.get_info[0])
        print(bik)
    elif args.index is not None:
        index(args.index[0])
    else:
        if args.compare is not None:
            errors = compare(args.compare[1])
        elif args.check is not None:
            errors = check(args.check[1])

        log("\n", level=0)
        errors["total"] = sum(errors.values())
        if errors["total"] > 0:
            error("%d issue(s) found:\n\n" % errors["total"])
            errors_string = "{:<16s}: {:d}\n"
            error(errors_string.format("Not in DB", errors.get("db", 0)))
            error(errors_string.format("Wrong resolution", errors.get("res", 0)))
            error(errors_string.format("Frame count/FPS", errors.get("frame", 0)))
            error(errors_string.format("Missing files", errors.get("missing", 0)))
        else:
            log_ok("no issues found\n", level=0)

    if log_to_file:
        log("\nlogged to %s with verbosity %d\n" %(log_path, log_verbosity), level=0)
        logfile.close()

if __name__== "__main__":
    main()
