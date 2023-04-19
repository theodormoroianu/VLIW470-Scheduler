"""
This class defines the datatypes used thoughout the project.
"""

from typing import Callable, List, Optional


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
            register_dependencies: List[int],
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
                int(i) for i in register_dependencies
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
        