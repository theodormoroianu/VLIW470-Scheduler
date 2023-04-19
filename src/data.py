"""
This class defines the datatypes used thoughout the project.
"""

from typing import List, Optional


class RiscInstruction:
    """
    Defines a standard RISC-V instruction, EXCEPT loops.
    It abstracts away WHAT the operation is doing, and only focuses on:
        * The registers used by the operation, as this is essentially what
            we care about.
        * The latency of the operation (1 if not mul, 3 if mul).
    The original (unparsed) operation can be found in obj.string_representation.
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
                case _:
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
        assert len([i for i in instructions if i.startswith("loop")]) == 1

        # read bounds of the loop
        [(loop_end, loop_begin)] = [
            (pc, int(instr.split()[-1]))
            for pc, instr in enumerate(instructions) if instr.startswith("loop")
        ]

        risc_program = RiscProgram()
        risc_program.BB0 = RiscProgram._parse_instruction_list(instructions[:loop_begin - 1])
        risc_program.BB0 = RiscProgram._parse_instruction_list(instructions[loop_begin:loop_end + 1])
        risc_program.BB0 = RiscProgram._parse_instruction_list(instructions[loop_end + 1:])

        return risc_program
        
