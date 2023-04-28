import risc_ds
import vliw_ds
from typing import Optional
import register_renaming

def calculate_ii_lowerbound(risc: risc_ds.RiscProgram) -> int:
    """
    Finds lowerbound on II using the formula described in the handout
    """
    nr_alu_instr, nr_mul_instr, nr_mem_instr = 0, 0, 0
    for instr in risc.program[risc.BB1_start:risc.BB2_start]:
        if instr.is_alu:
            nr_alu_instr += 1
        elif instr.is_mul:
            nr_mul_instr += 1
        elif instr.is_mem:
            nr_mem_instr += 1
        else:
            assert False
    
    return max([(nr_alu_instr + 1) // 2, nr_mul_instr, nr_mem_instr])


def generate_loop_schedule(risc: risc_ds.RiscProgram) -> vliw_ds.VliwProgram:
    """
    Generates scheduling for loop
    """
    result = vliw_ds.VliwProgram()
    
    # schedule instructions
    result.schedule_loopless_instructions(risc, "BB0")

    if risc.BB1_start != len(risc.program):    
        result.schedule_loop_instructions_without_interloop_dep(risc)
        result.schedule_loopless_instructions(risc, "BB2")    
        result.fix_interloop_dependencies(risc)
    else:
        print("No loop instructions found for loop. Stopping.")
    
    # do register renaming
    renamer = register_renaming.RegisterRename(risc, result)
    renamer.rename_loop()
    
    return result
    

def generate_loop_pip_schedule(risc: risc_ds.RiscProgram) -> vliw_ds.VliwProgram:
    """
    Generates scheduling for loop.pip
    """
    result = vliw_ds.VliwProgram()
    
    # schedule instructions
    result.schedule_loopless_instructions(risc, "BB0")


    if risc.BB1_start != len(risc.program):
        ii = calculate_ii_lowerbound(risc)
        # TEO TODO: Is this ok? Won't re-scheduling stuff break the object, which means we should make a copy each time?
        while not result.schedule_loop_pip_instructions(risc, ii):
            ii += 1

        print(f"Pipelined with an II of {ii}.")

        result.schedule_loopless_instructions(risc, "BB2")
    else:
        print("No loop instructions found for loop. Stopping.")

    # do register renaming
    renamer = register_renaming.RegisterRename(risc, result)
    renamer.rename_loop_pip()
    
    # compress loop body
    result.compress_loop_body()

    return result
