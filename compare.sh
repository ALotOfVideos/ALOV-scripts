#!/usr/bin/env bash

# A Lot of Videos (ALOV) video comparer by HHL
# compares top half of one video to bottom half of other
# requirements: bash 4, ffmpeg

argc=$#

if [[ argc -ne 3 ]]; then
	echo "need 3 args: original (top), compare (bottom), output"
fi

original="$1"
compare="$2"
output="$3"

# TODO: detect dimensions
width=1920
height=1080
halfheight=$(($height/2))

ffmpeg \
-i "$original" \
-i "$compare" \
-filter_complex "[1:v]fps=30,scale=$width:$height[a];[0:v]fps=30,scale=$width:$height[b];[b]crop=$width:$halfheight:0:0[l];[a]crop=$width:$halfheight:0:$halfheight[r];[l][r]vstack[out]" \
-map "[out]" \
"$output.mp4"
