from typing import Optional, Dict, Set, Tuple 
import risc_ds
import vliw_ds

class RegisterRename:
    """
    Handles register renaming.
    """
    def __init__(self, risc: risc_ds.RiscProgram, vliw: vliw_ds.VliwProgram):
        self.risc = risc
        self.vliw = vliw

        self.next_free_non_rotating_register = 1
        self.next_free_rotating_register = 32


    def get_vliw_instruction(self, risc_instr_idx: int) -> vliw_ds.VliwInstructionUnit:
        """
        Returns the corresponding VLIW instruction unit of a RISC instruction
        """
        risc_instr = self.risc.program[risc_instr_idx]
        bundle = self.vliw.program[self.vliw.risc_pos_to_vliw_pos[risc_instr]]
        
        flatten_bundle = [bundle.alu0, bundle.alu1, bundle.mul, bundle.mem, bundle.branch]
        ans_list = [x for x in flatten_bundle if x.risc_idx == risc_instr_idx]
        assert(len(ans_list)) == 1
        return ans_list[0]

    def rename_dest_registers(self, vliw_start: int, vliw_stop: int, is_roatating: bool = False):
        """
        Renames the destination registers of the instructions in the VLIW program
        Only takes into consideration instructions between risc_start and risc_stop
        """
        for bundle_idx in range(vliw_start, vliw_stop):
            bundle = self.vliw.program[bundle_idx]
            for instruction in [bundle.alu0, bundle.alu1, bundle.mul, bundle.mem, bundle.branch]:
                if instruction is None or instruction.dest_register is None:
                    continue 
               
                new_dest_register = self.next_free_rotating_register if is_roatating \
                                    else self.next_free_non_rotating_register 

                assert self.risc.program[instruction.risc_idx].renamed_dest_register is None
                self.risc.program[instruction.risc_idx].renamed_dest_register = new_dest_register

                if is_roatating:
                    self.next_free_rotating_register += self.vliw.no_stages + 1
                else:
                    self.next_free_non_rotating_register += 1


    def rename_loop(self):
        """
        Performs register renaming for in the `loop` case (non-rotating registers)
        """
        # rename destination registers in the whole program
        self.rename_dest_registers(0, len(self.vliw.program)) 

        # rename register dependencies
        final_movs = set()

        for bundle_idx, bundle in enumerate(self.vliw.program):
            for instruction in [bundle.alu0, bundle.alu1, bundle.mul, bundle.mem, bundle.branch]:
                rename_dict = {}
                risc_instr = self.risc.program[instruction.risc_idx]
                
                for dep in risc_instr.register_dependencies:
                    # if there are no dependencies allocate a new dummy register
                    if dep.producers_idx == []:
                        rename_dict[dep.reg_tag] = self.next_free_non_rotating_register
                        self.next_free_non_rotating_register += 1
                    else:
                        new_register = self.risc.program[dep.producers_idx[-1]].renamed_dest_register 
                        rename_dict[dep.reg_tag] = new_register

                        # account for interloop dependencies with a producer in BB0
                        if len(dep.producers_idx) == 2:
                            producer_bundle_idx = self.vliw.risc_pos_to_vliw_pos[dep.producers_idx[0]]
                            earliest_slot = producer_bundle_idx + self.risc.program[dep.producers_idx[0]].latency
                            earliest_slot = max(earliest_slot, self.vliw.end_loop - 1)

                            renamed_BB0_reg = rename_dict[dep.reg_tag]
                            renamed_BB1_reg = self.risc.program[dep.producers_idx[0]].renamed_dest_register 

                            final_movs.add((earliest_slot, renamed_BB0_reg, renamed_BB1_reg))
        
                # rename the instruction
                if len(rename_dict) > 0:
                    instruction.string_representation = \
                        self.string_representation_after_register_rename(
                                instruction,
                                risc_instr.renamed_dest_register,
                                rename_dict
                                )

        moves_pos = self.vliw.end_loop
        final_movs = list(final_movs)
        final_movs.sort(key=lambda x : x[1]) # sort after BB0_reg

        for earliest_slot, renamed_BB0_reg, renamed_BB1_reg in final_movs:
            line = earliest_slot
            while True:
                while line >= self.vliw.end_loop:
                    self.vliw.program = self.vliw.program[:self.vliw.end_loop] + [vliw_ds.VliwInstruction()] + \
                                        self.vliw.program[self.vliw.end_loop:]

                    self.vliw.program[self.vliw.end_loop].branch = self.vliw.program[self.vliw.end_loop - 1]
                    self.vliw.program[self.vliw.end_loop - 1] = None
                    self.vliw.end_loop += 1

                if self.vliw.program[line].alu0 is None:
                    self.vliw.program[line].alu0 = vliw_ds.


    def rename_loop_pip(self):
        """
        Performs register renaming for in the `loop-pip` case (rotating registers)
        """
        # rename destination registers in BB1 
        self.rename_dest_registers(self.risc.BB1_start, self.risc.BB2_start, True)

        # allocate non-rotating registers for loop invariant dependencies
        for instr_idx in range(self.risc.BB1_start, self.risc.BB2_start):
            risc_instr = self.risc.program[instr_idx]
            vliw_instr = self.get_vliw_instruction(instr_idx)
            rename_dict = {}
            
            for dep in risc_instr.register_dependencies:
                if dep.is_loop_invariant:
                    rename_dict[dep.reg_tag] = self.next_free_non_rotating_register
                    self.next_free_rotating_register += 1

            # rename the instruction and keep the destination register unchanged
            if len(rename_dict) > 0:
                vliw_instr.string_representation = \
                    self.string_representation_after_register_rename(
                            vliw_instr,
                            vliw_instr.dest_register,
                            rename_dict
                            )
        
        # rename register dependencies
        # TODO: finish this
        for instr_idx in range(self.risc.BB1_start, self.risc.BB2_start):
            risc_instr = self.risc.program[instr_idx]
            vliw_instr = self.get_vliw_instruction(instr_idx)
            rename_dict = {}
            
            for dep in risc_instr.register_dependencies:
                producer_idx = dep.producers_idx[0]
                producer = self.get_vliw_instruction(producer_idx)
                
                if dep.is_loop_invariant:
                    producer_rename_dict = {}
                    producer_rename_dict[producer.dest_registers] = risc_instr.dest_registers 
                    producer.string_representation = \
                        self.string_representation_after_register_rename(
                                producer,
                                producer.dest_register,
                                producer_rename_dict
                                )
                else:
                    # TODO: not sure about this
                    assert dep.is_local or dep.is_interloop
                    producer_stage = self.vliw.get_stage(self.vliw.risc_pos_to_vliw_pos(producer_idx))
                    consumer_stage = self.vliw.get_stage(self.vliw.risc_pos_to_vliw_pos(instr_idx))
                    new_register = producer.dest_register + (consumer_stage - producer_stage)

                    if dep.is_interloop:
                        new_register += 1

                    
                    # rename the instruction and keep the destination register unchanged
                    rename_dict = {dep.reg_tag: new_register}
                    vliw_instr.string_representation = \
                        self.string_representation_after_register_rename(
                                vliw_instr,
                                vliw_instr.dest_register,
                                rename_dict
                                )

        # TODO
        # rename destination registers in BB0 and BB1

    

    def string_representation_after_register_rename(self, 
            instruction: vliw_ds.VliwInstructionUnit,
            new_dest_register: Optional[int] = None, 
            rename_dict: Optional[Dict[int, int]] = None):
        """
        Renames the instruction, respecting the register renaming.
        The idea is to extract registers (starting at 'x') and pass them through rename
        """
        # should not have a new destination register if we didn't have one in the first place.
        # similarely, we should have one if we had a destination register initially.
        assert ((new_dest_register is None) ^ (instruction.dest_register is None)) == False
       
        if rename_dict is None:
            rename_dict = {}

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
                ans = ans[:start] + str(rename_dict.get(reg, default=reg)) + ans[stop+1:]

            # no longer the firstart iteration
            is_first_iteration = False

        return ans
