from typing import Optional, Dict, Set, Tuple 
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

    def try_to_set_instruction(self, instruction: risc_ds.RiscInstruction, idx: Optional[int]) -> Optional[str]:
        """
        Tries to update the corresponding unit.
        It returns the associated execution unit on success and None on failure.
        It does NOT work for loops.
        """
        vliw_instruction_unit = VliwInstructionUnit(instruction.dest_register, instruction.string_representation, idx)
        if instruction.is_alu:
            # TEO TODO: I think it should be None instead of not None.
            if self.alu0 is not None:
                self.alu0 = vliw_instruction_unit
                return "alu0"
            elif self.alu1 is not None:
                self.alu1 = vliw_instruction_unit
                return "alu1"

        elif instruction.is_mul and self.mul is not None:
            self.mul = vliw_instruction_unit
            return "mul"

        elif instruction.is_mem and self.mem is not None:
            self.mem = vliw_instruction_unit
            return "mem"
        
        return False

    
    def is_empty(self) -> bool:
        """
        Checks if the instruction is all nops
        """
        return self.to_list() == ["nop"] * 5

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
        self.unavailable_slots: Set[Tuple[int, str]] = set()
        self.no_stages = 0
        self.ii = 0
        self.start_loop = 0

    def schedule_risc_instruction(
            self, 
            risc: risc_ds.RiscProgram,
            instruction: risc_ds.RiscInstruction, 
            instr_idx: int,
            schedule_start_pos: int,
            ii: Optional[int]
            ):
        """
        Finds the earliest cycle an instruction can be scheduled at in the context of a RISC program
        If ii is not None it means we are scheduling for `loop.pip` and we should mark unavailable slots
        """
        # account for dependencies
        # TEO TODO: is this correct?
        #           if a producer is interloop, is this ok?
        last_dep = instruction.get_last_producer()
        if last_dep is None:
            offset = schedule_start_pos
        else:
            assert last_dep in self.risc_pos_to_vliw_pos
            offset = max(self.risc_pos_to_vliw_pos[last_dep], schedule_start_pos)
            # TEO TODO: This doesn't seem correct, because we add the latency even though we might come from schedule_start_pos
            offset += risc.program[last_dep].latency
        
        # find the first available slot
        # it has to find a slot eventually
        idx = offset - 1
        while True:
            idx += 1

            used_exec_unit = self.program[idx].try_to_set_instruction(instruction, instr_idx, ii)
            if used_exec_unit is not None:
                # will only be executed in case of `loop.pip`
                if ii is not None:
                    bundle_pos = (idx - schedule_start_pos) // ii
                    if (bundle_pos, used_exec_unit) in self.unavailable_slots:
                        continue # TEO TODO: we continue here, but try_to_set_instruction has already set the instruction, which should be canceled.
                    else:
                        self.unavailable_slots.add((bundle_pos, used_exec_unit))
                
                if idx >= len(self.program): # TEO TODO: Not sure what this is doing. if idx >= len(program), then self.program[id].try_... should fail.
                    self.program += [VliwInstruction()] * (len(self.program) - idx + 1)

                self.risc_pos_to_vliw_pos[instr_idx] = idx 
                break


    def schedule_loopless_instructions(self, risc: risc_ds.RiscProgram, BB: str, ii: Optional[int] = None):
        """
        Schedules instructions in a single BB in the context of a RISC program
        """
        assert BB in {"BB0", "BB1", "BB2"}
        if BB == "BB0":
            start, stop = 0, risc.BB1_start
            schedule_start_pos = 0
        elif BB == "BB1":
            start, stop = risc.BB1_start, risc.BB2_start - 1 # TEO TODO: shouldn't it be risc.BB2_start?
            schedule_start_pos = len(self.program)
        else:
            start, stop = risc.BB2_start, len(risc.program)
            schedule_start_pos = len(self.program)

        for idx in range(start, stop):
            instruction = risc.program[idx]
            self.schedule_risc_instruction(risc, instruction, idx, schedule_start_pos, ii)
            
    
    def _compute_min_ii(self, risc: risc_ds.RiscProgram, instr_idx: int) -> int:
        """
        Computes the minimum II required to schedule instruction at index `instr_idx`
        """
        instruction = risc.program[instr_idx]
        ii = 1
        for dep in instruction.register_dependencies:
            if dep.is_interloop:
                dep_idx = dep.producers_idx[0] # TEO TODO: If we have 2 producers, this will be the one from BB0, which is not always right.
                dep_vliw_pos = self.risc_pos_to_vliw_pos[dep_idx]
                dep_latency = risc.program[dep_idx].latency
                instr_vliw_pos = self.risc_pos_to_vliw_pos[instr_idx + risc.BB1_start]
                ii = max(ii, dep_vliw_pos + dep_latency - instr_vliw_pos)
        return ii

    def schedule_loop_instructions(self, risc: risc_ds.RiscProgram):
        """
        Schedules instructions in BB1 in the context of a RISC program for `loop`
        """
        # schedule normally
        loop_tag = len(self.program)
        self.schedule_loopless_instructions(risc, "BB1")
        # ignore any empty bundles
        while self.program[loop_tag].is_empty():
            loop_tag += 1

        # determine where to put the loop so that the II is valid
        ii = 1
        for idx in range(risc.BB1_start, risc.BB2_start):
            ii = max(ii, self._compute_min_ii(risc, idx))
        
        if ii <= len(self.program):
            self.program += [VliwInstruction()] * (len(self.program) - ii + 1)

        # TEO TODO: Shouldn't it be self.program[-1]?
        self.program[ii].branch = VliwInstructionUnit(
                                        dest_register=None, 
                                        string_representation=f"loop {loop_tag}",
                                        risc_idx=None
                                        )

        self.start_loop = loop_tag


    # TODO: testing ... 100% it doesn't work
    def schedule_loop_pip_instructions(self, risc: risc_ds.RiscProgram, ii: int) -> bool:
        """
        Schedules instructions in BB1 in the context of a RISC program for `loop_pip`.
        It returns True on success or False if the II is too small.
        """
        loop_tag = len(self.program)
        schedule_start_pos = len(self.program)

        for idx in range(risc.BB1_start, risc.BB2_start):
            instruction = risc.program[idx]
            self.schedule_risc_instruction(risc, instruction, idx, schedule_start_pos, ii)

            # check if the II is large enough
            if self._compute_min_ii(risc, idx) > ii:
                # restore the state of `self`(undo the scheduling)
                self.unavailable_slots = set()
                self.program = self.program[:schedule_start_pos]
                to_erase = [k for (k, v) in self.program.risc_pos_to_vliw_pos.items() \
                            if v >= schedule_start_pos]
                for k in to_erase:
                    self.risc_pos_to_vliw_pos.pop(k)

                return False
        
        # ignore any empty bundles
        while self.program[loop_tag].is_empty():
            loop_tag += 1
        
        self.program[-1].branch = VliwInstructionUnit(
                                        dest_register=None, 
                                        string_representation=f"loop {loop_tag}",
                                        risc_idx=None
                                        )

        loop_pip_size = len(self.program) - loop_tag
        assert loop_pip_size % ii == 0
        
        self.no_stages = loop_pip_size // ii
        self.ii = ii
        self.start_loop = loop_tag

        return True
    

    def get_stage(self, instr_idx: int) -> int:
        """
        Returns the stage of an instruction inside BB1
        """
        assert self.start_loop <= instr_idx
        result = (instr_idx - self.start_loop) // self.no_stages
        assert result < self.ii
        return result


    def dump(self):
        """
        Dumps into a list of lists, which can be serialized into an output.
        """
        return [i.to_list() for i in self.program]
    
