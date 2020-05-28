#!/bin/bash

DOWNLOAD_PATH='/scratch/gcerutti/AudioSet/data/eval_segments'

echo $DOWNLOAD_PATH

cd $DOWNLOAD_PATH

# audio first
cd audio
for FILE in $(ls)
do
  soxi -D -- $FILE
done
cd ..

#then video
cd video
for FILE in $(ls)
do
  ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 -- $FILE
done
cd ..