from typing import Callable, List, Optional, Tuple, Dict
import risc_ds

class VliwInstructionUnit:
    """
    Represents one unit (ALU / MUL / MEM / BRANCH).
    """
    def __init__(self, dest_register: Optional[int], string_representation: str, risc_idx: int):
        """
        dest_register: destination register of the instruction, if there is one.
        string_representation: string representation of the instruction.
        risc_idx: index of the instruction in the risc program.
        """
        self.dest_register = dest_register
        self.string_representation = string_representation
        self.risc_idx = risc_idx


class VliwInstruction:
    """
    Defines a very large instruction word.
    """
    def __init__(self):
        self.alu0: Optional[VliwInstructionUnit] = None
        self.alu1: Optional[VliwInstructionUnit] = None
        self.mul: Optional[VliwInstructionUnit] = None
        self.mem: Optional[VliwInstructionUnit] = None
        self.branch: Optional[VliwInstructionUnit] = None

    def try_to_set_instruction(self, instruction: risc_ds.RiscInstruction, idx: int) -> bool:
        """
        Tries to update the corresponding unit and returns `True/False` if it succedeed (if the unit is free or not)
        It does NOT work for loops
        """
        vliw_instruction = VliwInstructionUnit(instruction.dest_register, instruction.string_representation, idx)
        if instruction.is_alu:
            if self.alu0 is not None:
                self.alu0 = vliw_instruction
                return True
            elif self.alu1 is not None:
                self.alu1 = vliw_instruction
                return True

        elif instruction.is_mul and self.mul is not None:
            self.mul = vliw_instruction
            return True

        elif instruction.is_mem and self.mem is not None:
            self.mem = vliw_instruction
            return True
        
        return False

    
    def is_empty(self) -> bool:
        """
        Checks if the instruction is all nop's
        """
        return self.alu0 is None and self.alu1 is None and \
                self.mul is None and self.mem is None and self.branch is None

    def to_list(self) -> list[str]:
        """
        Dumps the VLIW instruction
        """
        return [
            i.string_representation if i is not None else "nop"
            for i in [self.alu0, self.alu1, self.mul, self.mem, self.branch]
        ]

    def dest_registers(self):
        """
        Returns all of the destination registers created by this VLIW
        """
        ans = []
        for unit in [self.alu0, self.alu1, self.mul, self.mem]:
            if unit is not None and unit.dest_register is not None:
                ans.append(unit.dest_register)
        return ans

class VliwProgram:
    """
    Encodes a Vliw program.
    """

    def __init__(self):
        self.program: list[VliwInstruction] = []
        self.risc_pos_to_vliw_pos: Dict[int, int] = {}


    def schedule_risc_instruction(
            self, 
            risc: risc_ds.RiscProgram,
            instruction: risc_ds.RiscInstruction, 
            instr_idx: int,
            schedule_start_pos: int
            ):
        """
        Finds the earliest cycle an instruction can be scheduled at in the context of a RISC program
        """
        # account for dependencies
        last_dep = instruction.get_last_producer()
        if last_dep is None:
            offset = schedule_start_pos
        else:
            offset = max(self.risc_pos_to_vliw_pos[last_dep], schedule_start_pos)
            offset += risc.program[last_dep].latency
        
        # find the first available slot
        if offset >= len(self.program):
            self.program += [VliwInstruction()] * (len(self.program) - offset + 1)
        # it has to find a slot eventually
        for idx in range(offset, len(self.program)):
            if self.program[idx].try_to_set_instruction(instruction, instr_idx):
                self.risc_pos_to_vliw_pos[instr_idx] = idx 
                break


    def schedule_loopless_instructions(self, risc: risc_ds.RiscProgram, BB: str):
        """
        Schedules instructions in a single BB in the context of a RISC program
        """
        assert BB in {"BB0", "BB1", "BB2"}
        if BB == "BB0":
            start, stop = 0, risc.BB1_start
            schedule_start_pos = 0
        elif BB == "BB1":
            start, stop = risc.BB1_start, risc.BB2_start - 1 
            schedule_start_pos = len(self.program)
        else:
            start, stop = risc.BB2_start, len(risc.program)
            schedule_start_pos = len(self.program)

        for idx in range(start, stop):
            instruction = risc.program[idx]
            self.schedule_risc_instruction(risc, instruction, idx, schedule_start_pos)
            

    def schedule_loop_instructions(self, risc: risc_ds.RiscProgram):
        """
        Schedules instructions in BB1 in the context of a RISC program with the `loop` instruction
        """
        # schedule normally
        loop_tag = len(self.program)
        self.schedule_loopless_instructions(risc, "BB1")
        # ignore any empty bundles
        while self.program[loop_tag].is_empty():
            loop_tag += 1

        # determine where to put the loop so that the II is valid



    def schedule_loop_pip_instructions(self, risc: risc_ds.RiscProgram):
        """
        Schedules instructions in BB1 in the context of a RISC program with the `loop_pip` instruction
        """


    def dump(self):
        """
        Dumps into a list of lists, which can be serialized into an output.
        """
        return [i.to_list() for i in self.program]


class RegisterRename:
    """
    Handles register renaming.
    TODO: Make this class actually work.
        Due to how RRB works, the current assignement of rotating registers is 99% wrong.
    """
    def __init__(self):
        # map from initial registers to the associated VLIW register
        self.risc_to_vliw_registers = dict()

        # ID of the next free non-rotating register we can use in BB0
        self.next_free_non_rotating_register = 0

        # ID of the next free rotating register we can use in BB1 and BB2
        self.next_free_rotating_register = 32

    def rename_non_rotating(self, risc_register: int):
        """
        Associates and returns the new non-rotating VLIW register associated to our register.
        """
        assert self.next_free_non_rotating_register < 32
        self.risc_to_vliw_registers[risc_register] = self.next_free_non_rotating_register
        self.next_free_non_rotating_register += 1

    def rename_rotating(self, risc_register: int):
        """
        Associates and returns the new rotating VLIW register associated to our register.
        """
        assert self.next_free_rotating_register < 96
        self.risc_to_vliw_registers[risc_register] = self.next_free_rotating_register
        self.next_free_rotating_register += 1

    def find_corresponding_VLIW_register(self, risc_register: int):
        """
        Finds and returns the VLIW register associated currently to our RISC register.
        """
        assert risc_register in self.risc_to_vliw_registers
        return self.risc_to_vliw_registers[risc_register]


