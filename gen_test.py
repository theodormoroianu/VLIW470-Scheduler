import random
import json

opcodes = ["add", "mulu", "ld", "st"]
reg_no = 5

def gen_testcase(op):
    rd = f"x{random.randrange(reg_no)}"
    rs1 = f"x{random.randrange(reg_no)}"
    rs2 = f"x{random.randrange(reg_no)}"
    imm = random.randrange(4096)

    if op == "add" or op == "mulu":
        return f"{op} {rd}, {rs1}, {rs2}"
    else:
        return f"{op} {rd}, {imm}({rs1})"

BB0 = 10
BB1 = 5
BB2 = 10

ans = ["mov LC, 50"]
ans += [f"mov x{i}, {random.randrange(100, 1000)}" for i in range(reg_no)]

for i in range(BB0):
    op = random.choice(opcodes)
    ans.append(gen_testcase(op))

for i in range(BB1):
    op = random.choice(opcodes)
    ans.append(gen_testcase(op))

ans.append(f"loop {BB0 + reg_no + 1}")

for i in range(BB2):
    op = random.choice(opcodes)
    ans.append(gen_testcase(op))

with open("generated_test.json", "w") as fout:
    fout.write(json.dumps(ans, indent=2))
