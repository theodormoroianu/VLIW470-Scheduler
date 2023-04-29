#! /bin/sh

python3 ./gen_test.py
./run.sh ./generated_test.json ./output_loop.json ./output_pip.json
python3 ./vliw470.py ./output_loop.json ./cycles_lool.json
python3 ./vliw470.py ./output_pip.json ./cycles_pip.json
python3 check_results.py 
