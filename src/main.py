"""
Entry point of the program.
"""

import sys
import json
import risc
import vliw
import scheduler

def main():
    INPUT_FILE = sys.argv[1]
    OUTPUT_SIMPLE_FILE = sys.argv[2]
    OUTPUT_PIP_FILE = sys.argv[3]

    print(f"Loading file...")
    input_file_content = json.load(open(INPUT_FILE, "r"))
    risc_program = risc.RiscProgram.load_from_list(input_file_content)
    
    print(f"File loaded.\nTrying to generate loop schedule...")
    vliw_program = scheduler.generate_loop_schedule(risc_program)
    json.dump(vliw_program.dump(), open(OUTPUT_SIMPLE_FILE, "w"))

    print(f"Loop schedule generated.\nTrying to generate loop.pip schedule...")
    vliw_program = scheduler.generate_loop_pip_schedule(risc_program)
    json.dump(vliw_program.dump(), open(OUTPUT_PIP_FILE, "w"))

    print(f"Finished.")

if __name__ == "__main__":
    main()
