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
                if instruction is None or instruction.dest_register is None or instruction.dest_register == -1:
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

        for bundle in self.vliw.program:
            for instruction in [bundle.alu0, bundle.alu1, bundle.mul, bundle.mem]:
                rename_dict = {}
                if instruction is None:
                    continue
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
                # if len(rename_dict) > 0:
                instruction.string_representation = \
                    self.string_representation_after_register_rename(
                            instruction,
                            risc_instr.renamed_dest_register,
                            rename_dict
                            )

        final_movs = list(final_movs)
        final_movs.sort(key=lambda x : x[1]) # sort after BB0_reg

        for earliest_slot, renamed_BB0_reg, renamed_BB1_reg in final_movs:
            line = earliest_slot
            while True:
                while line >= self.vliw.end_loop:
                    self.vliw.program = self.vliw.program[:self.vliw.end_loop] + [vliw_ds.VliwInstruction()] + \
                                        self.vliw.program[self.vliw.end_loop:]

                    self.vliw.program[self.vliw.end_loop].branch =  \
                            self.vliw.program[self.vliw.end_loop - 1].branch
                    self.vliw.program[self.vliw.end_loop - 1].branch = None
                    self.vliw.end_loop += 1

                if self.vliw.program[line].alu0 is None:
                    self.vliw.program[line].alu0 = vliw_ds.VliwInstructionUnit(
                        -1,
                        f"mov x{renamed_BB0_reg}, x{renamed_BB1_reg}",
                        -1
                    )
                    break
                if self.vliw.program[line].alu1 is None:
                    self.vliw.program[line].alu1 = vliw_ds.VliwInstructionUnit(
                        -1,
                        f"mov x{renamed_BB0_reg}, x{renamed_BB1_reg}",
                        -1
                    )
                    break


    def rename_loop_pip(self):
        """
        Performs register renaming for in the `loop-pip` case (rotating registers)
        """
        # rename destination registers in BB1 
        self.rename_dest_registers(self.vliw.start_loop, self.vliw.end_loop, True)

        # allocate non-rotating registers for loop invariant dependencies
        for bundle in self.vliw.program[self.vliw.start_loop:]:
            for instruction in [bundle.alu0, bundle.alu1, bundle.mul, bundle.mem]:
                # ignore empty instructions
                if instruction is None:
                    continue
                
                # we want to check if it has any loop invariant dep, and if so, and it
                # is not set, to set it
                risc_instr = self.risc.program[instruction.risc_idx]
                
                for dep in risc_instr.register_dependencies:
                    if dep.is_loop_invariant:
                        risc_bb0_idx = dep.producers_idx[0]
                        assert len(dep.producers_idx) == 1

                        risc_instruction = self.risc.program[risc_bb0_idx]
                        assert risc_instruction.dest_register is not None

                        if risc_instruction.renamed_dest_register is None:
                            risc_instruction.renamed_dest_register = \
                                self.next_free_non_rotating_register
                            self.next_free_non_rotating_register += 1

        # # allocate non-rotating registers for loop invariant dependencies
        # for bundle in self.vliw.program[:self.vliw.start_loop]:
        #     for instruction in [bundle.alu0, bundle.alu1, bundle.mul, bundle.mem]:
        #         # ignore empty instructions
        #         if instruction is None:
        #             continue

        #         risc_instr = self.risc.program[instruction.risc_idx]
                
        #         if risc_instr.dest_register is None or risc_instr.dest_register == -1:
        #             continue

        #         is_loop_invariant_dep = False
                
        #         # loop over all loop instructions to check if any of them is loop inv with us
        #         for loop_risc_instr in self.risc.program[self.risc.BB1_start:]:
        #             for dep in loop_risc_instr.register_dependencies:
        #                 if instruction.risc_idx in dep.producers_idx and dep.is_loop_invariant:
        #                     # found an instruction that has us as interloop dep
        #                     is_loop_invariant_dep = True
        #                     break

        #         if is_loop_invariant_dep:
        #             # assign a new non-rotating register
        #             risc_instr.renamed_dest_register = self.next_free_non_rotating_register
        #             self.next_free_non_rotating_register += 1
                
        # rename destination registers in BB0 (interloop and local)
        for bundle in self.vliw.program[:self.vliw.start_loop]:
            for instruction in [bundle.alu0, bundle.alu1, bundle.mul, bundle.mem]:
                # ignore empty instructions
                if instruction is None:
                    continue
                risc_instr = self.risc.program[instruction.risc_idx]

                # already renamed
                if risc_instr.renamed_dest_register is not None:
                    continue

                # don't want to rename
                if risc_instr.dest_register is None or risc_instr.dest_register == -1:
                    continue

                is_interloop_dep = False
                other_interloop_producer_risc_idx = None

                # loop over all loop instructions to check if any of them has an interloop dep with us
                for loop_risc_instr in self.risc.program[self.risc.BB1_start:self.risc.BB2_start]:
                    for dep in loop_risc_instr.register_dependencies:
                        if instruction.risc_idx in dep.producers_idx:
                            # found an instruction that has us as interloop dep
                            # loop invariant instructions were already renamed, so this
                            # has to be an interloop dep
                            is_interloop_dep = True
                            other_interloop_producer_risc_idx = dep.producers_idx[0]
                
                # not interloop dep, just assign standard register
                if not is_interloop_dep:
                    risc_instr.renamed_dest_register = self.next_free_non_rotating_register
                    self.next_free_non_rotating_register += 1
                elif risc_instr.dest_register is not None and risc_instr.dest_register != -1:
                    # interloop dep, have to assign same register as the interloop one
                    risc_instr.renamed_dest_register = \
                        self.risc.program[other_interloop_producer_risc_idx].renamed_dest_register

                    stage_other_producer = self.vliw.get_stage(self.vliw.risc_pos_to_vliw_pos[dep.producers_idx[0]])
                    risc_instr.renamed_dest_register += (1 - stage_other_producer)
                    # TODO Tifui: compute offset to add to register
                
        
        # rename destination registers in BB2 (local)
        for bundle in self.vliw.program[self.vliw.end_loop:]:
            for instruction in [bundle.alu0, bundle.alu1, bundle.mul, bundle.mem]:
                # ignore empty instructions
                if instruction is None:
                    continue
                risc_instr = self.risc.program[instruction.risc_idx]

                # should not be already renamed
                assert risc_instr.renamed_dest_register is None

                # ignore instructions which don't produce a register
                if risc_instr.dest_register is None or risc_instr.dest_register == -1:
                    continue

                risc_instr.renamed_dest_register = self.next_free_non_rotating_register
                self.next_free_non_rotating_register += 1

        # rename 
        for bundle_idx, bundle in enumerate(self.vliw.program):
            for instruction in [bundle.alu0, bundle.alu1, bundle.mul, bundle.mem]:
                # ignore empty instructions
                if instruction is None:
                    continue

                risc_instr = self.risc.program[instruction.risc_idx]
                rename_dict = {}
                
                for dep in risc_instr.register_dependencies:
                    if dep.is_loop_invariant:
                        new_dest_register = self.risc.program[dep.producers_idx[0]].renamed_dest_register
                        rename_dict[dep.reg_tag] = new_dest_register
                        
                    elif dep.is_local or dep.is_interloop:
                        # not in loop
                        if self.vliw.start_loop > bundle_idx or self.vliw.end_loop <= bundle_idx:
                            assert dep.is_local
                            new_dest_register = self.risc.program[dep.producers_idx[0]].renamed_dest_register
                            rename_dict[dep.reg_tag] = new_dest_register
                        else:
                            producer_idx = dep.producers_idx[0]
                            consumer_idx = instruction.risc_idx

                            producer_stage = self.vliw.get_stage(self.vliw.risc_pos_to_vliw_pos[producer_idx])
                            consumer_stage = self.vliw.get_stage(self.vliw.risc_pos_to_vliw_pos[consumer_idx])
                            new_register = self.risc.program[producer_idx].renamed_dest_register + (consumer_stage - producer_stage)

                            if dep.is_interloop:
                                new_register += 1
                            rename_dict[dep.reg_tag] = new_register
                    elif dep.is_post_loop:
                        producer_idx = dep.producers_idx[0]
                        # consumer_idx = instruction.risc_idx

                        producer_stage = self.vliw.get_stage(self.vliw.risc_pos_to_vliw_pos[producer_idx])
                        consumer_stage = self.vliw.no_stages
                        new_register = self.risc.program[producer_idx].renamed_dest_register + (consumer_stage - producer_stage)
                        rename_dict[dep.reg_tag] = new_register
                    else:
                        # add dummy register
                        assert dep.producers_idx == []
                        rename_dict[dep.reg_tag] = self.next_free_non_rotating_register
                        self.next_free_non_rotating_register += 1
                        
                # rename the instruction and keep the destination register unchanged
                instruction.string_representation = \
                    self.string_representation_after_register_rename(
                            instruction,
                            risc_instr.renamed_dest_register,
                            rename_dict
                            )
            

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
        # print(f"Instruction: {instruction.risc_idx}, new_dest_register: {new_dest_register}, str: {instruction.string_representation}")
        if instruction.dest_register == -1:
            assert new_dest_register is None
        else:
            assert ((new_dest_register is None) ^ (instruction.dest_register is None)) == False
       
        if rename_dict is None:
            rename_dict = {}

        ans = instruction.string_representation
        last_x_location = 0
        is_first_iteration = True

        while ans.find('x', last_x_location + 1) != -1:
            # still have a register to rename
            last_x_location = ans.find('x', last_x_location + 1)
            start = last_x_location + 1
            stop = start

            while stop + 1 < len(ans) and ans[stop + 1].isnumeric():
                stop += 1

            if ans[start - 2] == '0':
                # Retarded case with 0x
                ans = ans[:start - 2] + str(int(ans[start:stop+1], 16)) + ans[stop+1:]
                continue

            reg = int(ans[start:stop+1])

            if is_first_iteration and instruction.dest_register is not None:
                # have to rename the destination registarter
                assert reg == instruction.dest_register
                ans = ans[:start] + str(new_dest_register) + ans[stop + 1:]
            else:
                # print(f"Reg: {reg}, rename_dict: {rename_dict}, dest_register: {instruction.dest_register}")
                assert reg in rename_dict
                ans = ans[:start] + str(rename_dict[reg]) + ans[stop+1:]

            # no longer the firstart iteration
            is_first_iteration = False

        return ans
