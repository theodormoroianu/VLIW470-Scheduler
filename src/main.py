import sys
import json
import data

def main():
    INPUT_FILE = sys.argv[1]
    OUTPUT_FILE = sys.argv[2]

    input_file_content = json.load(open(INPUT_FILE, "r"))
    risc_program = data.RiscProgram.load_from_list(input_file_content)

    print(risc_program.BB0)
    print(risc_program.BB1)
    print(risc_program.BB2)

    print(f"Finished.")

if __name__ == "__main__":
    main()
