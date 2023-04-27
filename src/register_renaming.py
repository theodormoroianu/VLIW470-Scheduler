from typing import Optional, Dict, Set, Tuple, Callable
import risc_ds
import vliw_ds

class RegisterRename:
    """
    Handles register renaming.
    """
    def __init__(self, risc: risc_ds.RiscProgram, vliw: vliw_ds.VliwProgram):
        self.risc = risc
        self.vliw = vliw

        self.risc_to_vliw_registers = {}
        self.next_free_register = 1


    def rename_dest_registers(self):
        """
        Renames the destination registers of the instructions in the VLIW program
        """
        for bundle in self.vliw.program:
            for instruction in [bundle.alu0, bundle.alu1, bundle.mul, bundle.mem, bundle.branch]:
                if instruction is None or instruction.string_representation == "nop":
                    continue
                


    def rename_loop(self):
        """
        Perform perigter renaming for in the `loop` case (non-rotating registers)
        """
        self.rename_dest_registers() 


    # TODO: do we actually need this function ???
    def string_representation_after_register_rename(self, 
            instruction: vliw_ds.VliwInstructionUnit,
            new_dest_register: Optional[int] = None, 
            rename_fn: Callable[[int], int] = lambda x : x):
        """
        Renames the instruction, respecting the register renaming.
        The idea is to extract registers (starting at 'x') and pass them through rename
        """
        # should not have a new destination register if we didn't have one in the first place.
        # similarely, we should have one if we had a destination register initially.
        assert ((new_dest_register is None) ^ (instruction.dest_register is None)) == False

        ans = instruction.string_representation
        last_x_location = -1
        is_first_iteration = True

        while ans.find('x', last_x_location) != -1:
            # still have a register to rename
            last_x_location = ans.find('x', last_x_location)
            start = last_x_location + 1
            stop = start
            while stop + 1 < len(ans) and ans[stop + 1].isnumeric():
                stop += 1
            reg = int(ans[start:stop+1])

            if is_first_iteration and instruction.dest_registarter is not None:
                # have to rename the destination registarter
                assert reg == instruction.dest_registarter
                ans = ans[:start] + str(new_dest_register) + ans[stop + 1:]
            else:
                dependencies = [d.reg_tag for d in \
                        self.risc[instruction.risc_idx].register_dependencies]
                assert reg in dependencies
                ans = ans[:start] + str(rename_fn(reg)) + ans[stop+1:]

            # no longer the firstart iteration
            is_first_iteration = False

        return ans
