"""
Entry point of the program.
"""

import sys
import json
import risc_ds
import vliw_ds
import scheduler

def main():
    if False:
        INPUT_FILE = "test/18/input.json" # sys.argv[1]
        OUTPUT_SIMPLE_FILE = "loop.json" # sys.argv[2]
        OUTPUT_PIP_FILE = "loop_pip.json" # sys.argv[3]
    else:
        INPUT_FILE = sys.argv[1]
        OUTPUT_SIMPLE_FILE = sys.argv[2]
        OUTPUT_PIP_FILE =  sys.argv[3]

    print("Loading file...")
    input_file_content = json.load(open(INPUT_FILE, "r"))
    risc_program = risc_ds.RiscProgram.load_from_list(input_file_content)
    
    print("File loaded.\nTrying to generate loop schedule...")
    vliw_program = scheduler.generate_loop_schedule(risc_program)
    json.dump(vliw_program.dump(), open(OUTPUT_SIMPLE_FILE, "w"))

    print("Loop schedule generated.\nTrying to generate loop.pip schedule...")
    input_file_content = json.load(open(INPUT_FILE, "r"))
    risc_program = risc_ds.RiscProgram.load_from_list(input_file_content)
    vliw_program = scheduler.generate_loop_pip_schedule(risc_program)
    json.dump(vliw_program.dump(), open(OUTPUT_PIP_FILE, "w"))

    print("Finished.")

if __name__ == "__main__":
    main()
