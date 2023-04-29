import json


f1 = "cycles_pip.json" 
f2 = "cycles_lool.json"

d1 = json.load(open(f1, "r"))
d2 = json.load(open(f2, "r"))

last_rf_1 = set(d1[-1]["PhysicalRegisterFile"])
last_rf_2 = set(d2[-1]["PhysicalRegisterFile"])

if last_rf_1.intersection(last_rf_2) == last_rf_2:
    print("OK!!!!")
else:
    print("WRONG!!!")

print("\n\PhysicalRegisterFile:\n\n")
print(last_rf_1)



print("\n\PhysicalRegisterFile:\n\n")
print(last_rf_2)

