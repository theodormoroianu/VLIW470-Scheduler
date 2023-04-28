#!/bin/bash

for tnum in ./test/*
do
    cat ${tnum}/desc.txt
    echo $tnum
    python compare.py --loop ${tnum}/simple.json --refLoop ${tnum}/simple_ref.json  --pip ${tnum}/pip.json  --refPip ${tnum}/pip_ref.json
done

