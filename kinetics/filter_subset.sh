FILTER_LIST=$1
SUBSET=$2
OUTPUT_FILE=$3

awk -F',' '{if (FNR == NR) { labels[$0]} else { if (((FNR!=1) && ($1 in labels)) || ("\"" $1 "\"" in labels)) { print $2 "," $3 "," $4 "," $1}}}' $FILTER_LIST $SUBSET > $3
