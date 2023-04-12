#! /bin/sh

if [ $# -eq 2 ]
then
    echo "Running [python3 src/main.py $1 $2]..."
    python3 src/main.py "$1" "$2"
else
    echo "Usage: $1 </path/to/input.json> </path/to/output.json>"
fi
