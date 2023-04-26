"""
This class defines the datatypes used thoughout the project.
"""

from typing import Callable, List, Optional, Tuple, Dict

class RegisterDependency:
    """
    Defines a register dependency in a RISC-V program.
    A dependency can be either:
        * local -> the producer is in the same basic block
        * interloop -> the producer is in a different basic block
                        (either BB0 or BB1 of a previous iteration)
        * loop_invariant -> the producer is in BB0 and the consumer
                            is in either BB1 or BB2
        * post_loop -> the producer is in BB1 and the consumer is in BB2

    The dependency category and the index of the producer instructions
    are to be determined after the program is parsed
    """
    def __init__(self, reg_tag: int):
        self.reg_tag = reg_tag
        self.producers_idx = []
        self.is_local = False
        self.is_interloop = False
        self.is_loop_invariant = False
        self.is_post_loop = False

    def set_dep_type(self, dep_type: str, producer_idx: Optional[int]):
        if producer_idx is None:
            return

        assert dep_type in {"local", "interloop", "loop_invariant", "post_loop"}
        match dep_type:
            case "local":
                self.is_local = True
            case "interloop":
                self.is_interloop = True
            case "loop_invariant":
                self.is_loop_invariant = True
            case "post_loop":
                self.is_post_loop = True

        self.producers_idx.append(producer_idx)

        assert self.is_local + self.is_interloop + \
                self.is_loop_invariant + self.is_post_loop == 1
        if self.is_interloop:
            assert len(self.producers_idx) <= 2
        else:
            assert len(self.producers_idx) == 1


class RiscInstruction:
    """
    Defines a standard RISC-V instruction.
    It abstracts away WHAT the operation is doing, and only focuses on:
        * The registers used by the operation, as this is essentially what
            we care about.
        * The latency of the operation (1 if not mul, 3 if mul).
    The original (unparsed) operation can be found in obj.string_representation.

    If dest_register is -1, it means it is a special register (LC / EC).

    It is also important to note that in order to perform register renaming, we need to re-parse and replace
    register names in the original unparsed operation. This seems tedius, but it is by choice, as it would be
    even worse to have to save every type of operations and how to rename them.
    """
    def __init__(
            self,
            dest_register: Optional[int],
            register_dependencies: List[RegisterDependency],
            is_alu: bool,
            is_mul: bool,
            is_mem: bool,
            string_representation: str
            ):
        self.dest_register = dest_register
        self.register_dependencies = register_dependencies
        self.is_alu = is_alu
        self.is_mul = is_mul
        self.is_mem = is_mem
        self.latency = 3 if self.is_mul else 1
        self.string_representation = string_representation

        # sanity check
        assert self.is_alu + self.is_mul + self.is_mem == 1

    # TODO: do we actually need this function ???
    def string_representation_after_register_rename(self, new_dest_register: Optional[int], rename_fn: Callable[[int], int]):
        """
        renames the instruction, respecting the register renaming.
        The idea is to extract registers (starting at 'x') and pass them through rename
        """
        # should not have a new destination register if we didn't have one in the first place.
        # similarely, we should have one if we had a destination register initially.
        assert ((new_dest_register is None) ^ (self.dest_register is None)) == False

        ans = self.string_representation
        last_x_location = -1
        is_first_iteration = True

        while ans.find('x', last_x_location) != -1:
            # still have a register to rename
            last_x_location = ans.find('x', last_x_location)
            st = last_x_location + 1
            dr = st
            while dr + 1 < len(ans) and ans[dr + 1].isnumeric():
                dr += 1
            reg = int(ans[st:dr+1])

            if is_first_iteration and self.dest_register is not None:
                # have to rename the destination register
                assert reg == self.dest_register
                ans = ans[:st] + str(new_dest_register) + ans[dr + 1:]
            else:
                assert reg in self.register_dependencies
                ans = ans[:st] + str(rename_fn(reg)) + ans[dr+1:]

            # no longer the first iteration
            is_first_iteration = False

        return ans


    def get_last_producer(self) -> Optional[int]:
        """
        Returns the index of the last producer instruction in program order.
        """
        result = -1
        for dep in self.register_dependencies:
            result = max(result, dep.producers_idx)

        if result == -1:
            result = None
        return result


class RiscProgram:
    """
    Encodes a RISC program.
    In this particular case, we know the format is:
     * BB0, or the initialization code.
     * BB1, or the in-loop code.
     * BB2, or the finalization code.
    """

    def __init__(self):
        self.program: list[RiscInstruction] = []
        self.BB1_start: int = 0
        self.BB2_start: int = 0


    @staticmethod
    def _parse_instruction_list(instructions: list[str]) -> list[RiscInstruction]:
        ans = []
        for instruction in instructions:
            # split into words, after removing ',' and 'x'
            content = instruction.replace(",", " ").replace("x", "").split()
            # split into words, after removing ',' but WITHOUT removing `x`
            content_with_x = instruction.replace(",", " ").split()

            # sanity check
            assert len(content) <= 4

            dest_register = None
            register_dependencies = []
            is_alu, is_mul, is_mem = False, False, False

            match content[0]:
                case "add" | "sub":
                    is_alu = True
                    dest_register = content[1]
                    register_dependencies = content[2:]
                case "addi":
                    is_alu = True
                    dest_register = content[1]
                    register_dependencies = content[2:3]
                case "mulu":
                    is_mul = True
                    dest_register = content[1]
                    register_dependencies = content[2:]
                case "ld" | "st":
                    # extract address from imm(addr)
                    addr = content[2]
                    addr = addr[addr.find('(') + 1:addr.find(')')]
                    is_mem = True
                    if content[0] == "ld":
                        dest_register = addr
                    elif content[0] == "st":
                        register_dependencies = [addr]
                    else:
                        assert False
                case "mov":
                    # can be one of:
                    # mov LC/EC, imm
                    # mov dest, imm
                    # mov dest, source

                    # WE ASUME WE CAN'T HAVE mov pX in RISC-V
                    assert content[1][0] != 'p'

                    is_alu = True

                    # if special mov, then dest_register is -1
                    if content[1] in ["LC", "EC"]:
                        dest_register = -1
                    else:
                        dest_register = content[1]
                        # check if the value is a register or an imm
                        if content_with_x[2].count('x') == 1:
                            register_dependencies = [content[2]]
                case _:
                    print(f"Unknown operation: {content[0]}")
                    assert False

            # convert all the strings to ints
            if dest_register is not None:
                dest_register = int(dest_register)
            register_dependencies = [
                 RegisterDependency(i) for i in register_dependencies
            ]

            ans.append(RiscInstruction(
                dest_register=dest_register,
                register_dependencies=register_dependencies,
                is_alu=is_alu,
                is_mul=is_mul,
                is_mem=is_mem,
                string_representation=instruction
            ))

        return ans

    def _find_local_dependency(self, instr_idx: int, dep: RegisterDependency) -> Optional[int]:
        """
        Returns the index of a dependency in the same BB.
        """
        if instr_idx >= self.BB2_start:
            stop_BB = self.BB2_start - 1
        elif instr_idx >= self.BB1_start:
            stop_BB = self.BB1_start - 1
        else:
            stop_BB = -1

        for prod_idx in range(instr_idx - 1, stop_BB, -1):
            if self.program[prod_idx].dest_register == dep.reg_tag:
                return prod_idx
        return None


    def _find_interloop_dependency(self, instr_idx: int, dep: RegisterDependency) -> Optional[list[int, int]]:
        """
        Returns the indexes of an interloop dependency (can be at most 2). 
        It is only called for BB1.
        """
        result = []
        # first search inside BB1
        for prod_idx in range(self.BB2_start - 1, instr_idx, -1):
            if self.program[prod_idx].dest_register == dep.reg_tag:
                result.append(prod_idx)
                break

        # now search inside BB0
        for prod_idx in range(self.BB1_start - 1, -1, -1):
            if self.program[prod_idx].dest_register == dep.reg_tag:
                result.append(prod_idx)
                break
        
        if len(result) == 0:
            return None
        else:
            return result

    def _find_loop_invariant_dependency(self, dep: RegisterDependency) -> Optional[int]:
        """
        Returns the index of an loop invariant dependency. It is called in BB1 and BB2.
        """
        for prod_idx in range(self.BB1_start - 1, -1, -1):
            if self.program[prod_idx].dest_register == dep.reg_tag:
                return prod_idx
        return None


    def _find_post_loop_dependency(self, dep: RegisterDependency) -> Optional[int]:
        """
        Returns the index of an post loop dependency. It is only called in BB2.
        
        The order of lokking for dependecies is important, as we should look for 
        interloop dependencies before loop invariant dependencies.
        """
        for prod_idx in range(self.BB2_start - 1, self.BB1_start - 1, -1):
            if self.program[prod_idx].dest_register == dep.reg_tag:
                return prod_idx
        return None


    def perform_dependency_analysis(self):
        # find dependecies for instructions in BB0
        for idx, instruction in enumerate(self.program[:self.BB1_start]):
            for dep in instruction.register_dependencies:
                prod_idx = self._find_local_dependency(idx, dep)
                dep.set_dep_type("local", prod_idx)

        # find dependecies for instructions in BB1
        for idx, instruction in enumerate(self.program[self.BB1_start:self.BB2_start]):
            for dep in instruction.register_dependencies:
                prod_idx = self._find_local_dependency(idx, dep)
                if prod_idx is not None:
                    dep.set_dep_type("local", prod_idx)
                else:
                    prod_idx = self._find_interloop_dependency(idx, dep)
                    if prod_idx is not None:
                        dep.set_dep_type("interloop", prod_idx)
                    else:
                        prod_idx = self._find_loop_invariant_dependency(dep)
                        dep.set_dep_type("loop_invariant", prod_idx)
                        assert prod_idx is not None

        # find dependecies for instructions in BB2
        for idx, instruction in enumerate(self.program[self.BB2_start:]):
            for dep in instruction.register_dependencies:
                prod_idx = self._find_local_dependency(idx, dep)
                if prod_idx is not None:
                    dep.set_dep_type("local", prod_idx)
                else:
                    prod_idx = self._find_post_loop_dependency(dep)
                    if prod_idx is not None:
                        dep.set_dep_type("post_loop", prod_idx)
                    else:
                        prod_idx = self._find_loop_invariant_dependency(dep)
                        dep.set_dep_type("loop_invariant", prod_idx)
                        assert prod_idx is not None


    @staticmethod
    def load_from_list(instructions: list[str]):
        """
        Creates and returns a RiscProgram, splitting it correctly into
        BB0, BB1 and BB2.
        """
        # sanity check: should only have one loop.
        assert len([i for i in instructions if i.startswith("loop")]) <= 1

        risc_program = RiscProgram()

        has_loop = ([i for i in instructions if i.startswith("loop")] != [])
        if has_loop:
            # read bounds of the loop
            [(loop_end, loop_begin)] = [
                (pc, int(instr.split()[-1]))
                for pc, instr in enumerate(instructions) if instr.startswith("loop")
            ]
            BB0 = RiscProgram._parse_instruction_list(instructions[:loop_begin])
            BB1 = RiscProgram._parse_instruction_list(instructions[loop_begin:loop_end])
            BB2 = RiscProgram._parse_instruction_list(instructions[loop_end + 1:])
        else:
            BB0 = RiscProgram._parse_instruction_list(instructions)
            BB1 = BB2 = []
        
        risc_program.program = BB0 + BB1 + BB2
        risc_program.BB1_start = len(BB0)
        risc_program.BB2_start = len(BB0) + len(BB1)
        
        risc_program.perform_dependency_analysis()

        return risc_program



class VliwInstructionUnit:
    """
    Represents one unit (ALU / MUL / MEM / BRANCH).
    """
    def __init__(self, dest_register: Optional[int], string_representation: str):
        """
        dest_register: destination register of the instruction, if there is one.
        string_representation: string representation of the instruction.
        """
        self.dest_register = dest_register
        self.string_representation = string_representation


class VliwInstruction:
    """
    Defines a very large instruction word.
    TODO: Check if we actually need more stuff in here.
    """
    def __init__(self):
        self.alu0: Optional[VliwInstructionUnit] = None
        self.alu1: Optional[VliwInstructionUnit] = None
        self.mul: Optional[VliwInstructionUnit] = None
        self.mem: Optional[VliwInstructionUnit] = None
        self.branch: Optional[VliwInstructionUnit] = None

    def try_to_set_instruction(self, instruction: RiscInstruction) -> bool:
        """
        Tries to update the corresponding unit and returns `True/False` if it succedeed (if the unit is free or not)
        """
        vliw_instruction = VliwInstructionUnit(instruction.dest_register, instruction.string_representation)
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
        
        elif instruction.is_branch and self.branch is not None:
            self.branch = vliw_instruction
            return True

        return False


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


    def schedule_risc_instruction(self, risc: RiscProgram, instruction: RiscInstruction):
        """
        Finds the earliest cycle an instruction can be scheduled at in the context of a RISC program
        """
        # account for dependencies
        last_dep = instruction.get_last_producer()
        if last_dep is None:
            offset = 0
        else:
            offset = self.risc_pos_to_vliw_pos[last_dep]
            offset += risc.program[last_dep].latency
        
        # find the first available slot
        if offset >= len(self.program):
            self.program += [VliwInstruction()] * (len(self.program) - offset + 1)
        for idx in range(offset, len(self.program)):


    def update_schedule(self, scheduling: list[VliwInstruction]):
        """
        Updates the current program with the scheduling of a new BB.
        """
        # TODO: how do we implement this

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


