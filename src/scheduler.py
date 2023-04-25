import data
from typing import Optional

def try_to_find_schedule_with_given_II(risc: data.RiscProgram, is_pip: bool, ii: int = -1) -> Optional[data.VliwProgram]:
    """
    Tries to find a schedule for our program, with a given initialization interval.
    If `is_pip` == False, then `ii` must be set
    This function exists as loop and loop.pip are quite similar, and it doesn't make sense
    to do the initial / final stuff independently.
    """
    # TODO: Implement this.

    # sanity check (ii must be set if `is_pip` == False)
    assert is_pip or ii != -1

    result = data.VliwProgram()
    result.schedule_BB0(risc, is_pip)
    result.schedule_BB1(risc, is_pip, ii)
    
    if result.invalid_schedule():
        return None
    
    result.schedule_BB2(risc, is_pip)
    return result

def generate_loop_schedule(risc: data.RiscProgram) -> data.VliwProgram:
    """
    Generates scheduling for loop
    """
    result = try_to_find_schedule_with_given_II(risc, False)
    assert result is not None
    return result


def generate_loop_pip_schedule(risc: data.RiscProgram) -> data.VliwProgram:
    """
    Generates scheduling for loop.pip
    """
    # If no loop is present, then loop.pip is essentially a normal loop
    if risc.BB1 == []:
        print(f"No loop detected. Generating loop.pip as a loop schedule.")
        return generate_loop_schedule(risc)
    
    # find lowerbound on II
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
    
    # compute the lowerbound on the required ii
    ii = max([(nr_alu_instr + 1) // 2, nr_mul_instr, nr_mem_instr])

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
