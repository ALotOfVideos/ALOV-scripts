#!/usr/bin/env python3

# A Lot of Videos (ALOV) sanity checker by HHL
# checks ALOV release for completeness by comparing frame counts to vanilla
# https://github.com/ALotOfVideos/ALOV-scripts
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
from enum import IntEnum

quick = False
intermediate = False
filetype = ""

game: str = None
folder_mappings = None
global_db = None
resolutions = None
config = None


class Verb(IntEnum):
    WARN = 0
    INFO = 1
    ALL = 2
    DEBUG = 3


verbosity = Verb.INFO
log_to_file = False
logfile = None
log_verbosity = Verb.ALL

poplist = []
unknownlist = []

ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')
file_ext = re.compile(r'\..+$')
log_newlines = re.compile(r'\n+$')


def log(s, level=Verb.ALL, pre='', post=''):
    global verbosity
    global log_to_file
    global logfile
    global log_verbosity

    if level <= verbosity:
        # disable colors on windows for now
        # TODO curses colors? or colorama pkg? or? https://docs.python.org/3/howto/curses.html?highlight=color
        if osname == 'nt':
            pre = post = ''
            
        so = log_newlines.sub('', s)
        so = f"{pre}{so}{post}"
        newlines = s.count("\n")
        if verbosity == Verb.DEBUG:
            so = f"[{pre}{level.name:5}{post}] {so}"
            newlines = max(1, newlines)

        so += newlines * "\n"
        print(so, end='')

    if log_to_file and level <= log_verbosity:
        sf = s
        if log_verbosity == Verb.DEBUG:
            sf = f"[{level.name:5}] {s}"
            if sf[-1] != "\n":
                sf += "\n"
        print(sf, end='', file=logfile)


def error(s):
    # always print errors
    log(s, level=Verb.WARN, pre="\033[31m", post="\033[0m")


def warning(s, level=Verb.INFO):
    log(s, level=level, pre="\033[31;7m", post="\033[0m")


def log_ok(s, level=Verb.ALL):
    log(s, level=level, pre="\033[32m", post="\033[0m")


def log_info(s, level=Verb.INFO):
    log(s, level=level, pre="\033[32;7m", post="\033[0m")


def debug(s, level=Verb.DEBUG):
    log(s, level=level)


def isRes(i, w, h):
    return i.get("width") == w and i.get("height") == h


def isResolutionOK(i):
    global resolutions
    global config
    allowed = config.get("resolutions")
    for n in allowed:
        r = resolutions.get(n, {})
        if isRes(i, r.get("w"), r.get("h")):
            return n


def isResolutionIllegal(i):
    global resolutions
    global config
    blacklist = ["1080p", "1440p"]
    for n in blacklist:
        r = resolutions.get(n, {})
        if isRes(i, r.get("w"), r.get("h")):
            return n


def getMappings():
    global folder_mappings
    global game
    global intermediate

    if folder_mappings is None:
        if intermediate:
            folder_mappings_path = 'folder_mappings_intermediate.json'
        else:
            folder_mappings_path = 'folder_mappings.json'
        log_ok("loading %s\n\n" % folder_mappings_path)

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
    try:
        probe_bik = probe_bik.get("streams")[0]
    except TypeError:
        error("%s could not be read: verify whether the file is intact\n" % f)
        return {"defect": 1}

    bik = {
        "name": os.path.basename(f), # localisation .replace(f[-7:-4], "INT"),
        "dir": getRelativeDir(os.path.dirname(f), root),
        "width": probe_bik.get("width", 0),
        "height": probe_bik.get("height", 0),
        "fps": round(eval(probe_bik.get("r_frame_rate")), 2),
        "frame_count": int(probe_bik.get("nb_read_frames") if not quick else probe_bik.get("duration_ts")),
        "frame_count_header": int(probe_bik.get("duration_ts"))
        }

    return bik


def checkHeader(video, check_fstring, header_string="checking header: "):
    global quick

    mag = math.floor(math.log(max(video.get("frame_count", 0), video.get("frame_count_header", 0)), 10)) + 1
    header_fstring = "{:>7s} {:0" + str(mag) + "d}\n"

    if not quick:
        if video.get("frame_count") == video.get("frame_count_header"):
            log(check_fstring.format(header_string))
            log_ok("OK: header contains actual number of frames\n")
            return 0
        else:
            log(check_fstring.format(header_string), level=Verb.WARN)
            error("WARNING: header does not indicate actual number of frames\n")
            log(header_fstring.format("header:", video.get("frame_count_header")), Verb.WARN)
            log(header_fstring.format("actual:", video.get("frame_count")), Verb.WARN)
            return 1
    return 0


def index(d):
    if not os.path.isdir(d):
        error("directory %s does not exist\n" % d)
        sys.exit(1)

    log("indexing %s\n" % d, level=Verb.WARN)

    while True:
        outfile = "alov_index_%s" % datetime.now().strftime("%y%m%dT%H%M")
        outfile = input("choose output database file name: [%s.json]: " % outfile) or outfile
        if outfile[-5:] != ".json":
            outfile += ".json"
        if not os.path.isfile(outfile):
            break
    log("output database: %s\n" % outfile)
    log("\n", level=Verb.WARN)

    biks = sorted(glob.glob("%s%s**%s*.bik" % (d, os.sep, os.sep), recursive=True), key=str.lower)

    total = len(biks)
    mag = math.floor(math.log(total, 10)) + 1
    log_string = "({:0" + str(mag) + "d}/{:0" + str(mag) + "d}) reading {:s}\n"
    count = 0
    l = list()
    for f in biks:
        count += 1
        log(log_string.format(count, total, f), level=Verb.WARN)
        bik = getBikProperties(f, d)
        if bik.get("defect") is None:
            l.append(bik)

    with open(outfile, 'w') as out:
        json.dump(l, out, indent=0)

    log("\n", level=Verb.WARN)
    log("saved bik properties to %s\n" % outfile, level=Verb.WARN)


def compare(f, root=''):
    global quick
    global poplist
    global unknownlist
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
    if bik.get("defect") is not None:
        return bik

    realname = bik.get("name")
    name = realname

    # replace intermediate file extension with vanilla extension to match library
    if intermediate:
        ext = ".bik"
        name = file_ext.sub(ext, realname)

    realfolder = bik.get("dir")
    if osname == 'nt':
        realfolder = realfolder.replace('\\', '/')

    # some dirs contain single files mapped to various origins
    # such single file mappings are preferred over the folder mapping
    folder = realfolder + "/" + name  # needs literal / as database uses unix style separator
    folder = fm.get(folder)
    if folder is None:
        folder = fm.get(realfolder)

    log("checking %s\n" % os.path.join(bik.get("dir"), realname), level=Verb.WARN)

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

    log("ALOV file:    %s%s%s\n" % (bik.get("dir"), os.sep, name), level=Verb.DEBUG)
    log("resolved dir: %s\n" % folder, level=Verb.DEBUG)
    log("vanilla file: %s%s%s\n" % (vanilla.get("dir"), os.sep, vanilla.get("name")), level=Verb.DEBUG)

    errors = {"db": 0, "res": 0, "frame": 0, "missing": 0, "header": 0}
    capitalization_fstring = "{:>10s} {:s}\n"
    check_fstring = "{:<25s}"
    exist_string = "1. checking existence:"
    rez_string = "2. checking resolution:"
    frame_string = "3. checking frame count:"
    mag = math.floor(math.log10(max(vanilla.get("frame_count", 0), bik.get("frame_count", 0)))) + 1
    frames_fstring = "{:>10s} {:0" + str(mag) + "d} {:s} {:.2f} {:s}\n"
    header_string = "{:>10s} {:0" + str(mag) + "d}\n"

    # check existence
    if vanilla.get("name") is None:
        log(check_fstring.format(exist_string), level=Verb.WARN)
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
            return errors
        else:
            error("WARNING: cutscene uses wrong capitalization\n")
            log(capitalization_fstring.format("vanilla:", vanilla.get("name")), level=Verb.WARN)
            log(capitalization_fstring.format("found:", name), level=Verb.WARN)
            unknownlist.append({'n': name, 'd': folder})
            errors["missing"] -= 1
        errors["db"] += 1
    else:
        log(check_fstring.format(exist_string))
        log_ok("OK: cutscene found in database\n")
    if vanilla is not None:
        poplist.append(vanilla)

    # check resolution
    if (r := isResolutionOK(bik)) is not None:
        log(check_fstring.format(rez_string))
        log_ok(f"OK: {r}\n")
    elif (r := isResolutionIllegal(bik)) is not None:
        log(check_fstring.format(rez_string), level=Verb.WARN)
        error(f"WARNING: %s is using an illegal resolution ({r})\n" % f)
        errors["res"] += 1
    else:
        log(check_fstring.format(rez_string), level=Verb.WARN)
        error("WARNING: resolution not recognized (%dx%d)\n" % (bik.get("width"), bik.get("height")))
        errors["res"] += 1

    # check frame count
    bfc = bik.get("frame_count")
    bfps = bik.get("fps")
    vfc = vanilla.get("frame_count")
    vfps = vanilla.get("fps")

    debug_path = list()

    if bfc == vfc and bfps == vfps:
        debug_path.append("if bfc == vfc and bfps == vfps:")
        log(check_fstring.format(frame_string))
        log_ok("OK: frame counts match (%d)\n" % vfc)
    else:
        debug_path.append("else")
        factor = bfps / vfps
        factor_thresh = 29.7/30
        # TODO: sped up without interpolation
        if factor > 1/factor_thresh and bfc == round(factor * vfc):
            debug_path.append("if factor > 1/factor_thresh and bfc == round(factor * vfc):")
            log(check_fstring.format(frame_string), level=Verb.INFO)
            log_info("OK: frames were interpolated\n")
            log(frames_fstring.format("vanilla:", vfc, "frames @", vfps, "FPS"), level=Verb.INFO)
            log(frames_fstring.format("found:", bfc, "frames @", bfps, "FPS"), level=Verb.INFO)
        elif factor != 1 and factor >= factor_thresh and factor <= 1/factor_thresh:
            debug_path.append("elif (factor != 1 and factor >= factor_thresh and factor <= 1/factor_thresh):")
            if bfc == vfc:
                debug_path.append("if bfc == vfc:")
                log(check_fstring.format(frame_string), level=Verb.INFO)
                log_info("OK: FPS rounded (%0.2f -> %0.2f)\n" % (vfps, bfps))
            elif bfc == round(factor * vfc):
                debug_path.append("elif bfc == round(factor * vfc):")
                log(check_fstring.format(frame_string), level=Verb.INFO)
                log_info("OK: frames were interpolated\n")
                log(frames_fstring.format("vanilla:", vfc, "frames @", vfps, "FPS"), level=Verb.INFO)
                log(frames_fstring.format("found:", bfc, "frames @", bfps, "FPS"), level=Verb.INFO)
            # else:
            #     log(check_string.format(frame_string), level=Verb.WARN)
            #     error("ERROR: unhandled situation\n")
            #     log(frames_string.format("vanilla:", vfc, "frames @", vfps, "FPS"), level=Verb.WARN)
            #     log(frames_string.format("found:", bfc, "frames @", bfps, "FPS"), level=Verb.WARN)
        elif vfps in (15,20) and bfps == 60 and bfc == vfc:
            debug_path.append("elif vfps in (15,20) and bfps == 60 and bfc == vfc:")
            log(check_fstring.format(frame_string), level=Verb.INFO)
            log_info("OK: FPS upgraded (%0.2f -> %0.2f)\n" % (vfps, bfps))
        elif bfps == vfps and vfc > bfc and bfc >= vfc - 3:
            debug_path.append("elif bfps == vfps and vfc > bfc and bfc >= vfc - 3:")
            log(check_fstring.format(frame_string), level=Verb.INFO)
            warning("WARNING: missing a few frames\n")
            log(frames_fstring.format("vanilla:", vfc, "frames @", vfps, "FPS"), level=Verb.INFO)
            log(frames_fstring.format("found:", bfc, "frames @", bfps, "FPS"), level=Verb.INFO)
            errors["frame"] += 1
        elif factor < factor_thresh:
            debug_path.append("elif factor < factor_thresh:")
            log(check_fstring.format(frame_string), level=Verb.WARN)
            log("WARNING: FPS downgraded", level=Verb.WARN)
            errors["frame"] += 1
        else:
            debug_path.append("else:")
            log(check_fstring.format(frame_string), level=Verb.WARN)
            if bfps == vfps:
                debug_path.append("if bfps == vfps:")
                if bfc < vfc:
                    debug_path.append("if bfc < vfc:")
                    error("WARNING: missing frames\n")
                    log(frames_fstring.format("vanilla:", vfc, "frames @", vfps, "FPS"), level=Verb.WARN)
                    log(frames_fstring.format("found:", bfc, "frames @", bfps, "FPS"), level=Verb.WARN)
                    log("{:>10s} {:s}\n".format("should be:", "vanilla probably"), level=Verb.WARN)
                    errors["frame"] += 1
                elif bfc % vfc == 0:
                    debug_path.append("elif bfc % vfc == 0:")
                    log_info("OK: extended/looped clip\n")
                    log(frames_fstring.format("vanilla:", vfc, "frames @", vfps, "FPS"), level=Verb.INFO)
                    log(frames_fstring.format("found:", bfc, "frames @", bfps, "FPS"), level=Verb.INFO)
            else:
                debug_path.append("else:")
                error("WARNING: frame rate/count mismatch\n")
                log(frames_fstring.format("vanilla:", vfc, "frames @", vfps, "FPS"), level=Verb.WARN)
                log(frames_fstring.format("found:", bfc, "frames @", bfps, "FPS"), level=Verb.WARN)
                if not round(bfps) == 15:
                    debug_path.append("if not round(bfps) == 15:")
                    log(frames_fstring.format("should be:", round(factor*vfc), "frames @", round(factor*vfps), "FPS"), level=Verb.WARN)
                    if not factor == 2:
                        debug_path.append("if not factor == 2:")
                        log(frames_fstring.format("or:", 2*vfc, "frames @", 2*vfps, "FPS"), level=Verb.WARN)
                else:
                    debug_path.append("else:")
                    log(frames_fstring.format("should be:", 4*vfc, "frames @", 4*vfps, "FPS"), level=Verb.WARN)
                    log(frames_fstring.format("or:", vfc, "frames @", 4*vfps, "FPS"), level=Verb.WARN)
                log("(or vanilla)\n", level=Verb.WARN)
                errors["frame"] += 1

    log("%s\n" % debug_path, level=Verb.DEBUG)

    # check header integrity
    errors["header"] += checkHeader(bik, check_fstring, "4. checking header:")

    return errors


def check(d):
    global poplist
    global unknownlist
    global filetype

    if not os.path.isdir(d):
        error("directory %s does not exist\n" % d)
        return 1

    log("checking ALOV release at %s\n" % d, level=Verb.WARN)
    getMappings()

    db = getDB()
    if db is None:
        error("database missing\n")
        return 1

    total = len(db)
    mag = math.floor(math.log(total, 10)) + 1
    log_string = "({:0" + str(mag) + "d}/{:0" + str(mag) + "d}) "
    count = 0
    errors = {"db": 0, "res": 0, "frame": 0, "missing": 0, "header": 0}

    biks = sorted(glob.glob("%s%s**%s*.%s" % (d, os.sep, os.sep, filetype), recursive=True), key=str.lower)

    for bik in biks:
        count += 1
        log(log_string.format(count, total), level=Verb.WARN)
        errors = dict(Counter(errors) + Counter(compare(bik, d)))

    # TODO pop these to display list of missing in the end
    missing = db
    for i in poplist:
        if i in missing:
            missing.remove(i)

    log("\n", level=Verb.WARN)
    if count != total or errors.get("db", 0) != 0:
        mismatch_string = "{:>12s} {:3d}\n"
        missing_string = "{:>18s} {:s}\n"
        error(mismatch_string.format("vanilla:", total))
        error(mismatch_string.format("found:", count))
        if errors.get("db", 0) != 0:
            error("    therein:\n")
            error(mismatch_string.format("in db:", count - errors.get("db", 0)))
            error(mismatch_string.format("unexpected:", errors.get("db", 0)))
            error("\n")
            error(missing_string.format("unexpected files:", ', '.join([i.get('n') + " (" + i.get('d') + ")" for i in unknownlist])))
        if len(missing) > 0:
            error(missing_string.format("missing files:", ', '.join([i.get('name') for i in missing])))
        errors = dict(Counter(errors) + Counter({"missing": total - (count - errors.get("db", 0))}))
    else:
        log_ok("found %d files in database\n")
        log("\033[32;1mrelease is complete.\033[0m\n")

    return errors


def init_parser():
    global verbosity
    global log_verbosity

    parser = argparse.ArgumentParser(description='ALOV sanity checker by HHL')

    actiongroup = parser.add_mutually_exclusive_group(required=True)
    actiongroup.add_argument('-g', '--get-info', nargs=1, metavar='BIK', help='reads the supplied BIK file and outputs its properties as json')
    actiongroup.add_argument('-i', '--index', nargs=1, metavar='PATH', help='gets all bik files inside (sub)directory PATH and outputs a json file with info of all biks')
    actiongroup.add_argument('--compare', nargs=2, metavar=('GAME','BIK'), help='compares the supplied BIK to vanilla properties stored in database of GAME (ME1|ME2|ME3)')
    actiongroup.add_argument('-c', '--check', nargs=2, metavar=('GAME','PATH'), help='checks all (supported) biks in PATH against the database of given GAME (ME1|ME2|ME3)')

    parser.add_argument('--quick', '--fast', action='store_const', const=True, default=False, help='only read bik header instead of actually counting frames')
    parser.add_argument('--intermediate', '--prores', action='store_const', const=True, default=False, help='check using Apple ProRes .mov intermediate files instead of release biks')

    verbositygroup = parser.add_mutually_exclusive_group()
    verbositygroup.add_argument("-v", "--verbosity", action="count", default=0, help="increase output (stdout) verbosity (default %d=%s)" % (verbosity.value, verbosity.name))
    verbositygroup.add_argument("-q", "--quiet", "--silent", action='store_const', const=Verb.WARN, help="decrease output (stdout) verbosity to silent")
    verbositygroup.add_argument('--debug', action='store_const', const=Verb.DEBUG, help='set stdout verbosity level to debug (maximum)')
    loggroup = parser.add_mutually_exclusive_group()
    loggroup.add_argument('--no-log', action='store_const', const=False, default=True, help='disable log file')
    loggroup.add_argument("--log-verbosity", default=log_verbosity, help="set log verbosity (default %d=%s)" % (log_verbosity.value, log_verbosity.name))
    loggroup.add_argument("--short-log", action='store_const', const=Verb.INFO, help="set log file verbosity to INFO")
    loggroup.add_argument("--error-log", action='store_const', const=Verb.WARN, help="set log file verbosity to WARN")
    return parser


def main():
    global quick
    global intermediate
    global filetype
    global game
    global resolutions
    global config
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
    if log_to_file:
        log_path = "alov_sanity_checker_%s.log" % (datetime.now().strftime("%y%m%dT%H%M"))
        if game is not None:
            log_path = "alov_sanity_checker_%s_%s.log" % (game, datetime.now().strftime("%y%m%dT%H%M"))
            if intermediate:
                log_path = "alov_sanity_checker_%s_prores_%s.log" % (game, datetime.now().strftime("%y%m%dT%H%M"))
        logfile = open(log_path, 'w')
        log("opened log file %s\n\n" % log_path, level=Verb.DEBUG)
    log_verbosity = args.log_verbosity
    log_verbosity = log_verbosity if args.error_log is None else args.error_log
    log_verbosity = log_verbosity if args.short_log is None else args.short_log

    log("%s\n\n" % args, level=Verb.DEBUG)

    errors = {"db": 0, "res": 0, "frame": 0, "missing": 0}

    with open("resolutions.json", 'r') as rez:
        resolutions = json.load(rez)

    if game:
        with open("config.json", 'r') as conf:
            config = json.load(conf).get(game)

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

        log("\n", level=Verb.WARN)
        errors["total"] = sum(errors.values())
        if errors["total"] > 0:
            error("%d issue(s) found:\n\n" % errors["total"])
            errors_string = "{:<16s}: {:d}\n"
            error(errors_string.format("Not in DB", errors.get("db", 0)))
            error(errors_string.format("Wrong resolution", errors.get("res", 0)))
            error(errors_string.format("Frame count/FPS", errors.get("frame", 0)))
            error(errors_string.format("Missing files", errors.get("missing", 0)))
            if not quick:
                error(errors_string.format("Broken headers", errors.get("header", 0)))
        else:
            log_ok("no issues found\n", level=Verb.WARN)

    if log_to_file:
        log("\nlogged to %s with verbosity %d\n" % (log_path, log_verbosity), level=Verb.WARN)
        logfile.close()


if __name__ == "__main__":
    main()
