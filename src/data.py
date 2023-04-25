"""
This class defines the datatypes used thoughout the project.
"""

from typing import Callable, List, Optional, Union

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
        self.producer_idx = -1
        self.producer_BB = -1
        self.is_local = False
        self.is_interloop = False
        self.is_loop_invariant = False
        self.is_post_loop = False

    def set_dep_type(self, dep_type: str, producer_idx: int, producer_BB: int):
        assert dep_type is in {"local", "interloop", "loop_invariant", "post_loop"}

        match dep_type:
            case "local":
                 self.is_local = True
            case "interloop":
                self.is_interloop = True
            case "loop_invariant":
                self.is_loop_invariant = True
            case "post_loop":
                self.is_post_loop = True
        
        self.producer_idx = producer_idx
        self.producer_BB = producer_BB

        assert self.producer_BB is in {0, 1, 2}
        assert self.is_local + self.is_interloop + \
                self.is_loop_invariant + self.is_post_loop == 1


class RiscInstruction:
    """
    Defines a standard RISC-V instruction, EXCEPT loops.
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

            

class RiscProgram:
    """
    Encodes a RISC program.
    In this particular case, we know the format is:
     * BB0, or the initialization code.
     * BB1, or the in-loop code.
     * BB2, or the finalization code.
    """

    def __init__(self):
        self.BB0: list[RiscInstruction] = []
        self.BB1: list[RiscInstruction] = []
        self.BB2: list[RiscInstruction] = []


    def get_instruction(self, instruction_idx: int, BB_idx: int) -> RiscInstruction:
        assert BB_idx is in {0, 1, 2}
        match BB_idx:
            case 0:
                return self.BB0[instruction_idx]
            case 1:
                return self.BB1[instruction_idx]
            case 2:
                return self.BB2[instruction_idx]

    def _parse_instruction_list(instructions: list[str]) -> list[RiscInstruction]:
        ans = []
        for idx, instruction in enumerate(instructions):
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

    """
    Returns the index of a dependency in the same BB.
    """
    def _find_local_dependency(self, instr_idx: int, BB_idx: int, dep: RegisterDependency) -> Union[int, None]:
        for pord_idx in range(instr_idx - 1, -1, -1):
            if self.get_instruction(instr_idx, BB_idx).dest_register == dep.reg_tag:
                return pord_idx
        return None


    """
    Returns the index of an interloop dependency. It is only called for BB1.
    """
    # TODO: figure out if we need to store the index of the producer in BB0 as well
    def _find_interloop_dependency(self, instr_idx: int, dep: RegisterDependency) -> Union[int, None]:
        for pord_idx in range(len(self.BB1) - 1, instr_idx, -1):
            if self.get_instruction(instr_idx, 1).dest_register == dep.reg_tag:
                return pord_idx
        return None


    """
    Returns the index of an loop invariant dependency. It is called in BB1 and BB2.
    """
    def _find_loop_invariant_dependency(self, dep: RegisterDependency) -> Union[int, None]:
        for pord_idx in range(len(self.BB0) - 1, -1, -1):
            if self.get_instruction(instr_idx, 0).dest_register == dep.reg_tag:
                return pord_idx
        return None
        

    """
    Returns the index of an post loop dependency. It is only called in BB2.
    """
    def _find_post_loop_dependency(self, dep: RegisterDependency) -> Union[int, None]:
        for pord_idx in range(len(self.BB1) - 1, -1, -1):
            if self.get_instruction(instr_idx, 1).dest_register == dep.reg_tag:
                return pord_idx
        return None


    def _perform_dependency_analysis(self):
        # find dependecies for instructions in BB0
        for idx, instruction in enumerate(self.BB0):
            for dep in instruction.register_dependencies:
                prod_idx = self._find_local_dependency(idx, dep)
                dep.set_dep_type("local", pord_idx, 0)
                assert prod_idx is not None

        # find dependecies for instructions in BB1
        for idx, instruction in enumerate(self.BB1):
            for dep in instruction.register_dependencies:
                prod_idx = self._find_local_dependency(idx, dep)
                if prod_idx is not None:
                    dep.set_dep_type("local", pord_idx, 1)
                else:
                    pord_idx = self._find_interloop_dependency(idx, dep)
                    if prod_idx is not None:
                        dep.set_dep_type("interloop", prod_idx, 1)
                    else:
                        prod_idx = self._find_loop_invariant_dependency(dep)
                        dep.set_dep_type("loop_invariant", prod_idx, 0)
                        assert prod_idx is not None

        # find dependecies for instructions in BB2
        for idx, instruction in enumerate(self.BB2):
            for dep in instruction.register_dependencies:
                prod_idx = self._find_local_dependency(idx, dep)
                if prod_idx is not None:
                    dep.set_dep_type("local", pord_idx, 2)
                else:
                    pord_idx = self._find_post_loop_dependency(dep)
                    if prod_idx is not None:
                        dep.set_dep_type("post_loop", prod_idx, 1)
                    else:
                        prod_idx = self._find_loop_invariant_dependency(dep)
                        dep.set_dep_type("loop_invariant", prod_idx, 0)
                        assert prod_idx is not None


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
            risc_program.BB0 = RiscProgram._parse_instruction_list(instructions[:loop_begin])
            risc_program.BB1 = RiscProgram._parse_instruction_list(instructions[loop_begin:loop_end])
            risc_program.BB2 = RiscProgram._parse_instruction_list(instructions[loop_end + 1:])
        else:
            risc_program.BB0 = RiscProgram._parse_instruction_list(instructions)

        risc_program._perform_dependency_analysis()

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
    In this particular case, we can keep the same format as for the RISC program, which is:
     * BB0, or the initialization code.
     * BB1, or the in-loop code.
     * BB2, or the finalization code.
    """

    def __init__(self):
        self.BB0: list[VliwInstruction] = []
        self.BB1: list[VliwInstruction] = []
        self.BB2: list[VliwInstruction] = []

        self.instruction_cycle = []

    def dump(self):
        """
        Dumps into a list of lists, which can be serialized into an output.
        """
        return [
            i.to_list() for i in self.BB0
        ] + [
            i.to_list() for i in self.BB1
        ] + [
            i.to_list() for i in self.BB2
        ]

    def invalid_schedule(self):
        pass

    def schedule_BB0(self, risc: RiscProgram, is_pip: bool):
        pass
    
    def schedule_BB1(self, risc: RiscProgram, is_pip: bool, ii: int):
        pass
    
    def schedule_BB2(self, risc: RiscProgram, is_pip: bool):
        pass
        

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
    
    
