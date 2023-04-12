#!/bin/bash

./build.sh

for tnum in ./test/*
do
    ./run.sh $tnum/input.json $tnum/simple.json $tnum/pip.json
done

