#!/usr/bin/env bash

# A Lot of Videos (ALOV) sanity checker by HHL
# checks ALOV release for completenes by comparing frame counts to vanilla
# github URL
#
# example usage:
# ./alov_sanity_check.sh check DB.json "Path with spaces inside double quotes" 2>&1 | tee >(sed -r "s/\x1B\[([0-9]{1,2}(;[0-9]{1,2})?)?[mGK]//g" >LOGFILE.log)
#
# requirements: bash 4, ffprobe (ffmpeg), jq >= 1.5, find, bc

# globals

function help {

    echo -e "ALOV sanity checker by HHL" >&2
    echo -e "Usage: ./alov_sanity_check ACTION [args]" >&2
    echo -e "" >&2
    echo -e "supported actions:" >&2
    printf "%-25s%s\n" \
    "help" "prints this help" \
    "getinfo BIKFILE" "reads the supplied BIKFILE and outputs its properties as json" \
    "index PATH" "gets all bik files inside (sub)directory PATH and outputs a json file with info of all biks" \
    "compare DATABASE BIKFILE" "compares the supplied BIKFILE to vanilla properties stored in DATABASE" \
    "check DATABASE ALOVPATH" "checks all (supported) biks for the given DATABASE (should hold info for either ME1/2/3) at ALOVPATH" >&2

}

function is4K {

    input=$1
    width=$(echo $input | jq '.width')
    height=$(echo $input | jq '.height')

    if [[ 1 -eq $(bc -l <<< "$width == 3840") ]] && [[ 1 -eq $(bc -l <<< "$height == 2160") ]]; then
        echo 1
    else
        echo 0
    fi

}

function is1440p {

    input=$1
    width=$(echo $input | jq '.width')
    height=$(echo $input | jq '.height')

    if [[ 1 -eq $(bc -l <<< "$width == 2560") ]] && [[ 1 -eq $(bc -l <<< "$height == 1440") ]]; then
        echo 1
    else
        echo 0
    fi

}

function is1080p {

    input=$1
    width=$(echo $input | jq '.width')
    height=$(echo $input | jq '.height')

    if [[ 1 -eq $(bc -l <<< "$width == 1920") ]] && [[ 1 -eq $(bc -l <<< "$height == 1080") ]]; then
        echo 1
    else
        echo 0
    fi

}

function is1081p {

    input=$1
    width=$(echo $input | jq '.width')
    height=$(echo $input | jq '.height')

    if [[ 1 -eq $(bc -l <<< "$width == 1920") ]] && [[ 1 -eq $(bc -l <<< "$height == 1081") ]]; then
        echo 1
    else
        echo 0
    fi

}

function getBikProperties {

    input="$1"
    if [[ ! -f "$input" ]]; then
        echo "file '$input' does not exist" >&2
        exit 1
    fi

    probe_res=$(ffprobe -v quiet -hide_banner -select_streams v -print_format json -count_frames -show_entries "stream=filename,nb_read_frames,r_frame_rate,width,height" "$input")

    width=$(echo $probe_res | jq '.streams[].width')
    height=$(echo $probe_res | jq '.streams[].height')
    fps=$(echo $probe_res | jq '.streams[].r_frame_rate' )
    fps=$(bc -l <<< "scale=2;${fps:1:-1}")
    frame_count=$(echo $probe_res | jq '.streams[].nb_read_frames')
    let frame_count=${frame_count:1:-1}
    name=$(basename "$input")

    bik="{\"name\":\"$name\",\"width\":$width,\"height\":$height,\"fps\":$fps,\"frame_count\":$frame_count}"
    echo $bik
}

function index {

    dir="$1"
    if [[ ! -d "$dir" ]]; then
        echo "directory '$dir' does not exist" >&2
        exit 1
    fi

    echo "indexing '$dir'" >&2

    outfile="alov_index_$(date +%y%m%dT%H%M).json"
    total=$(find "$dir" -name "*.bik" | wc -l)
    let count=0

    printf "[" > $outfile
    while IFS= read -r -d '' f; do
        (( count++ ))
        echo "($count/$total) reading $f" >&2
        bik=$(getBikProperties "$f")
        printf "\n$bik" >> $outfile
        printf "," >> $outfile
    done < <(find "$dir" -name "*.bik" -print0 | sort -z)

    truncate -s-1 $outfile
    echo -e "\n]" >> $outfile

    echo -e "\ndon't forget to rename $outfile to something fitting" >&2

}

function compare {

    db="$1"
    input="$2"
    if [[ ! -f "$input" ]]; then
        echo "file '$input' does not exist" >&2
        echo 1
        exit 1
    fi
    if [[ ! -f "$db" ]]; then
        echo "database '$db' does not exist" >&2
        echo 1
        exit 1
    fi

    echo "checking ""$input" >&2
    name=$(basename "$input")
    bik=$(getBikProperties "$input")
    # TODO: workaround dupes
    vanilla=$(cat $db | jq -c "[.[] | select(.name == \"$name\")][0]")

    # echo "input: $bik" >&2
    # echo "vanilla: $vanilla" >&2

    let errors=0

    # check existence
    printf "%-25s" "1. checking existence: " >&2
    if [[ $vanilla == "" ]] || [[ $vanilla == "null" ]]; then
        echo -e "\e[31mWARNING: cutscene not found in database\e[0m" >&2
        (( errors++ ))
        echo 1
        return
    else
        echo -e "\e[32mOK (cutscene found in database)\e[0m" >&2
    fi

    # check resolution
    printf "%-25s" "2. checking resolution: " >&2
    if [[ $(is1081p $bik) -eq 1 ]]; then
        echo -e "\e[32mOK (1081p)\e[0m" >&2
    elif [[ $(is1440p $bik) -eq 1 ]]; then
        echo -e "\e[32mOK (1440p)\e[0m" >&2
    elif [[ $(is4K $bik) -eq 1 ]]; then
        echo -e "\e[32mOK (4K)\e[0m" >&2
    elif [[ $(is1080p $bik) -eq 1 ]]; then
        echo -e "\e[31mWARNING: $input is 1080p -> should be 1081p\e[0m" >&2
        (( errors++ ))
    else
        echo -e "\e[31mWARNING: resolution is not 1081p/1440p/4K ($(echo $bik | jq '.width')x$(echo $bik | jq '.height'))\e[0m" >&2
        (( errors++ ))
    fi

    # check frame count
    printf "%-25s" "3. checking frame count: " >&2
    vanilla_c=$(echo $vanilla | jq '.frame_count')
    frame_count=$(echo $bik | jq '.frame_count')
    if [[ $vanilla_c == $frame_count ]]; then
        echo -e "\e[32mOK: frame counts match ($frame_count)\e[0m" >&2
    else
        vanilla_fps=$(echo $vanilla | jq '.fps')
        bik_fps=$(echo $bik | jq '.fps')
        factor=$(bc -l <<< "$bik_fps / $vanilla_fps")
        if [[ 1 -eq $(bc -l <<< "scale=0;$frame_count == ($factor * $vanilla_c + 0.5)/1") ]]; then
            echo -e "\e[32;7mOK: frames were interpolated\e[0m" >&2
            printf "%-10s %4d %s %.2f %s\n" \
                   "vanilla:" "$vanilla_c" "frames @" "$vanilla_fps" "FPS" \
                   "found:" "$frame_count" "frames @" "$bik_fps" "FPS" >&2
        else
            echo -e "\e[31mWARNING: frame rate/count mismatch\e[0m" >&2
            printf "%-10s %4d %s %.2f %s\n" \
                   "vanilla:" "$vanilla_c" "frames @" "$vanilla_fps" "FPS" \
                   "found:" "$frame_count" "frames @" "$bik_fps" "FPS" >&2
            if [[ 1 -eq $(bc -l <<< "$frame_count < $factor * $vanilla_c") ]] && [[ 1 -eq $(bc -l <<< "$bik_fps == $vanilla_fps") ]]; then
                echo "should be: vanilla probably" >&2
            else
                if [[ 0 -eq $(bc -l <<< "$bik_fps == 15") ]]; then
                    printf "%-10s %4.0f %s %.2f %s\n" \
                           "should be:" $(bc -l <<< "$factor * $vanilla_c") "frames @" $(bc -l <<< "$factor * $vanilla_fps") "FPS" >&2
                    if [[ 0 -eq $(bc -l <<< "$factor == 2") ]]; then
                        printf "%-10s %4d %s %.2f %s\n" \
                               "or:" $(bc -l <<< "2 * $vanilla_c") "frames @" $(bc -l <<< "2 * $vanilla_fps") "FPS" >&2
                    fi
                else
                    printf "%-10s %4d %s %.2f %s\n" \
                           "should be:" $(bc -l <<< "4 * $vanilla_c") "frames @" $(bc -l <<< "4 * $vanilla_fps") "FPS" >&2
                fi
                echo "(or vanilla)" >&2
            fi
            (( errors++ ))
        fi
    fi

    echo $errors

}

function check {


    db="$1"
    dir="$2"
    if [[ ! -d "$dir" ]]; then
        echo "directory '$dir' does not exist" >&2
        echo 1
        exit 1
    fi
    if [[ ! -f $db ]]; then
        echo "database '$db' does not exist" >&2
        echo 1
        exit 1
    fi

    echo -e "checking ALOV release at $dir\n" >&2

    let count=0
    let db_count=$(cat $db | jq '. | length')
    let errors=0

    while IFS= read -r -d '' f; do
        (( count++ ))
        echo "($count/$db_count)" >&2
        (( errors += $(compare "$db" "$f") ))
        echo "" >&2
    done < <(find "$dir" -name "*.bik" -print0 | sort -z)

    if [[ !$count -ne $db_count ]]; then
        echo -e "\e[31mWARNING: count mismatch\e[0m" >&2
        printf "%-8s %3d\n" \
               "vanilla:" "$db_count" \
               "found:" "$count" >&2
        (( errors++ ))
    else
        echo -e "\e[32mfound $count files in database.\n\e[32;1mrelease is complete.\e[0m" >&2
    fi

    echo $errors
}


argc=$#
let err=0

# main menu flow
if [[ $argc -eq 0 ]]; then
    echo -e "arguments required\n"
    help
    exit 1
elif [[ $1 == "help" ]] || [[ $1 == "--help" ]] || [[ $1 == "-h" ]]; then
    help
    exit
elif [[ $1 == "getinfo" ]]; then
    bik=$(getBikProperties "$2")
    echo $bik
elif [[ $1 == "index" ]]; then
    index "$2"
elif [[ $1 == "compare" ]]; then
    err=$(compare "$2" "$3")
    echo ""
    if [[ $err -gt 0 ]]; then
        echo -e "\e[31m$err issue(s) found\e[0m"
    else
        echo -e "\e[32mno issues found\e[0m"
    fi
elif [[ $1 == "check" ]]; then
    err=$(check "$2" "$3")
    echo ""
    if [[ $err -gt 0 ]]; then
        echo -e "\e[31m$err issue(s) found\e[0m"
    else
        echo -e "\e[32mno issues found\e[0m"
    fi
else
    echo -e "unsupported action\n"
    help
fi
