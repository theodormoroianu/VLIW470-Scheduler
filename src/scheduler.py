import data
from typing import Optional

def calculate_ii_lowerbound(risc: data.RiscProgram) -> int:
    """
    Finds lowerbound on II using the formula described in the handout
    """
    nr_alu_instr, nr_mul_instr, nr_mem_instr = 0, 0, 0
    for instr in risc.BB1:
        if instr.is_alu:
            nr_alu_instr += 1
        elif instr.is_mul:
            nr_mul_instr += 1
        elif instr.is_mem:
            nr_mem_instr += 1
        else:
            assert False
    
    return max([(nr_alu_instr + 1) // 2, nr_mul_instr, nr_mem_instr])




def schedule_loopless_instructions(risc: data.RiscProgram, vliw: data.VliwProgram, BB: str) -> data.VliwProgram:
    """
    Schedules instructions in BB0 and BB2 in the context of a VLIW program
    """
    for idx, instruction in risc.program:


def schedule_loop_instructions(risc:data.RiscProgram, vliw: data.VliwProgram, is_pip: bool) -> data.VliwProgram:
    """
    Schedules instructions in BB1 in the context of a VLIW program
    """

def generate_loop_schedule(risc: data.RiscProgram) -> data.VliwProgram:
    """
    Generates scheduling for loop
    """
    

def generate_loop_pip_schedule(risc: data.RiscProgram) -> data.VliwProgram:
    """
    Generates scheduling for loop.pip
    """
    # If no loop is present, then loop.pip is essentially a normal loop
    if risc.BB1 == []:
        print(f"No loop detected. Generating loop.pip as a loop schedule.")
        return generate_loop_schedule(risc)
    

    # sequentially search for a working ii
    while True:
        # sanitization: ii should be less than 1000
        # TODO: Check this is actually true
        if ii > 1000:
            raise "Stopped searching for schedule. ii too large"
        
        result = try_to_find_schedule_with_given_II(risc, True, ii=ii)
        if result is not None:
            return result
        # increase ii, as the previous ii was too tight
        ii += 1
