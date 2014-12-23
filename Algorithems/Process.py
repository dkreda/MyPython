__author__ = 'dkreda'

###############################################################################
# this prog implements the following problem solving:
#  you have a list of process that the period of each process is known.
#  you have to set each Core/CPU/Machine with the amount of process in such
#  Order which will take minimum Time
#
###############################################################################


def Calculate(NumOfCPU,TimeList):
    UnusedProc=TimeList[:]
    UnusedProc.sort()
    TotalTime=reduce(lambda x,y: x+y,UnusedProc)
    Avg=TotalTime / NumOfCPU
    MaxTime= Avg if Avg > UnusedProc[-1] else UnusedProc[-1]
    Result=[]
    for MachineNum in xrange(NumOfCPU):
        Result.append([])
        Indx=len(UnusedProc) -1
        Total=0
        while Indx:
            if Total+UnusedProc[Indx] <= MaxTime:
                Result[MachineNum].append(UnusedProc[Indx])
                Total += UnusedProc[Indx]
                UnusedProc.remove(UnusedProc[Indx])
            Indx -= 1
    if len(UnusedProc):
        Result[MachineNum].extend(UnusedProc)
    return Result

CPUs=int(raw_input('Enter Number of Machines: '))
ProcList=[]
ProcTime=True
while ProcTime:
    ProcTime=raw_input("Time Period of Process: ")
    if ProcTime:
        ProcList.append(int(ProcTime))

Res=Calculate(CPUs,ProcList)
i=1
for Iter in Res:
   print "Machin %d : %s" % (i," ,".join(["%d" % n for n in Iter]))
   i += 1

