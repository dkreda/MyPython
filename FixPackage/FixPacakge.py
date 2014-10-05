__author__ = 'danielk'

import PkgUtil,Adapters
import ConfClass,re,sys
from datetime import datetime

print '>>>>> Start Main script !'

ConfDef= { 'Pkg' : { 'ValidPattern' : '\D\S+' , 'Description' : "Path to Relevant Package" , 'mandatory' : True} }

MainConfig=ConfClass.ConfParser(**ConfDef)
try:
    MainConfig.ReadConfig([ConfClass.ConfParser.CLI])
    Conf=MainConfig.getConfig()
except ConfClass.ConfiguartionError as ConfErr:
    print "\n\n"
    for Line in  MainConfig.Usage(): print Line
    print "\n\n"
    raise ConfErr

#print "Debug - Start reading Pacakge \"%s\"" % Conf['Pkg']

PkgObj=PkgUtil.PkgHarmony(Conf['Pkg'][0],MngPort='.//mgmt_nics')


st=datetime.now().time()

print "%02d:%02d:%02d - Start Checking One connection" % (st.hour,st.minute,st.second)
## Go Over each chassi and check the topology of each chassi
for ChassiName,ChassiRec in PkgObj.GetChassi().items():
    #print "Start Checking Chassi %s:" % ChassiName
    TmpTopolgy=PkgObj.GetTopology(ChassiName)
    print "Debug - Chassi \"%s\" Topology (%s):" % (ChassiName,ChassiRec['HwType'],)
    print TmpTopolgy
    TmpMatch=re.match('(\S+)(\s+(\S.+))?',ChassiRec['HwType'])
    if TmpMatch:
        HwType=TmpMatch.group(1)
        VmFolder=TmpMatch.group(3)
    else:
        raise Exception("missing Chassi hardware type at Package %s" % PkgObj.Name())
    Cage=Adapters.MachineManage(HwType,ChassiRec['IP'],ChassiRec['User'],ChassiRec['Password'],Folder= VmFolder)
    TmpList=[]
    ## Go Over each Node at the Topolgy - and set tuple of (Slot,NicNum)
    for VmName,VmRec in TmpTopolgy:
        # print "Debug - Checking Machine %s" % VmName
        SlotNum=VmName if re.match(r'VmWare',HwType) else PkgObj.FindSlot(VmName,ChassiName)
        #print "Debug - %s is located at slote %d" % (VmName,SlotNum)
        if not 'MngPort' in VmRec :
            print "Warning - missing Configuration of Managed Nics for %s" % VmName
            NicNum=0
        else:
            TmpMatch=re.search('(\d+)',VmRec['MngPort'])
            NicNum=int(TmpMatch.group(1))
        TmpList.append((SlotNum,NicNum,))

    Count=0
    FixedTopology=PkgUtil.Topology()
    #print "Debug TmpList is %s" % type(TmpList)
    #print "Debug - TmpList size is %d" % len(TmpList)
    if len(TmpList) <= 0:
        print "Warning - Chassi %s has no relevant Cards at Package %s" % (ChassiName,PkgObj.Name())
    MacList=Cage.getMACs(*TmpList)
    if MacList is None or len(MacList)<=0:
        raise Exception("Error Fail to retreive MAC Address from \"%s\" %s/%s" % (HwType,ChassiRec['IP'],ChassiRec['User']))
    #Ttt=Cage.getMACs(*TmpList)
    #print "Debug - Return from GetMACs type: %s" % type(Ttt)
    for VmMac in MacList:
        #VmMAC=Cage.getMAC(SlotNum,NicNum)
        if type(TmpList[Count]) is tuple:
            SlotNum=TmpList[Count][0]
            NicNum=TmpList[Count][1]
        else:
            SlotNum=TmpList[Count]
            NicNum=1

        Count += 1
        if not VmMac :
            print "Error   - Blade/Vm at slot %s has No MAC address at Nic %d" % (str(SlotNum),NicNum)
            continue
        for VmName,VmRec in PkgObj.GetTopology(ChassiName,SlotNum): break
        #VmRec=PkgObj.FindSlot(SlotNum,ChassiName)
        if not VmRec['MAC'] :
            print "Error  - Host %s at Package %s has No MAC address" % (str(SlotNum),PkgObj.Name())
            continue
        if VmMac.upper() == VmRec['MAC'].upper():
            print "Info - %s MAC address Match the Package MAC" % VmName
        else:
            print "Error - %s MAC address is not the same as the package MAC" % VmName
            print "%-20s %-20s" % ("Pacakge MAC","Machine MAC")
            print "%-20s %-20s" % (VmRec['MAC'].upper(),VmMac.upper())
            print "Do you wish to Fix it ? (yes|no):"
            Answer=sys.stdin.readline()
            print "Answer: %s" % Answer
            VmRec.Set('MAC',VmMac)
            FixedTopology.AddNode(VmName,VmRec)
    print "Going to Fix Package:"
    PkgObj.Update_Topology(FixedTopology,ChassiName)


st=datetime.now().time()

print "%2d:%2d:%2d - Finish Checking One connection" % (st.hour,st.minute,st.second)

st=datetime.now().time()
print "%2d:%2d:%2d - Finish Checking Many connection" % (st.hour,st.minute,st.second)
