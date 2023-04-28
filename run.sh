#! /bin/sh

if [ $# -eq 3 ]
then
    echo "Running [python3 src/main.py $1 $2 $3]..."
    python3 src/main.py "$1" "$2" "$3"
else
    echo "Usage: $1 </path/to/input.json> </path/to/output1.json>" "</path/to/output2.json>"
fi
