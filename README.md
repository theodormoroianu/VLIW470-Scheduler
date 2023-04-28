# VLIW470-Scheduler
Scheduler for a custom VLIW processor.


## Stuff To Consider



### Edge Cases

1. `mul` at the end of BB0: Should we always add nops, or just if it's necessary?

2. empty loop