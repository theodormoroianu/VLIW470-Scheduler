import os
import re
import json
import itertools
import argparse

parser = argparse.ArgumentParser()

parser.add_argument("--loop", required=True, help="The reference JSON using the loop instruction.", type=argparse.FileType("r"))
parser.add_argument("--pip", required=True, help="The reference JSON using the loop.pip instruction.", type=argparse.FileType("r"))
parser.add_argument("--refLoop", required=True, help="The reference JSON.", type=argparse.FileType("r"))
parser.add_argument("--refPip", required=True, help="The reference JSON.", type=argparse.FileType("r"))

RED = '\x1b[31m'
GREEN = '\x1b[36m'
RESET = '\x1b[0m'

ALU0 = 0
ALU1 = 1
MULT = 2
MEM = 3
Branch = 4

slotToStr = ["ALU0", "ALU1", "Mult", "Mem", "Branch"]

def rawInst(inst):
    p = re.compile(r"\s+")
    return re.sub(p, "", inst).lower()

def compareInstructions(resI, refI):
    rawResI = rawInst(resI)
    rawRefI = rawInst(refI)

    return rawResI == rawRefI

def compareBundles(resB, refB, bLoc, typesOnly):
    for iLoc, (resI, refI) in enumerate(itertools.zip_longest(resB, refB)):
        if((resI == None) or (refI == None)):
            return "[" + RED + "Error" + RESET + "] " + \
                "Bundle length does not match."
        
        if(not compareInstructions(resI, refI)):
            return "[" + RED + "Error" + RESET + "] " + \
                "Instruction do not match at bundle " + str(bLoc) + \
                ", instruction slot: " + slotToStr[iLoc] + ": " + \
                resI + " != " + refI

    return ""

def compare(resF, refF, typesOnly):
    for bLoc, (resB, refB) in enumerate(itertools.zip_longest(resF, refF)):
        if((resB == None) or (refB == None)):
            return "[" + RED + "Error" + RESET + "] Schedule length does not match."

        bOks = compareBundles(resB, refB, bLoc, typesOnly)
        if(bOks != ""):
            return bOks

    return GREEN + "PASSED!" + RESET

args = parser.parse_args()

LOOP = json.load(args.loop)
PIP = json.load(args.pip)
REFLOOP = json.load(args.refLoop)
REFPIP = json.load(args.refPip)

simpleFull = compare(LOOP, REFLOOP, False)
pipFull = compare(PIP, REFPIP, False)

print("loop schedule: " + simpleFull)
print("loop.pip schedule: " + pipFull)
print()

