#!/usr/bin/env python
###############################################################################
#
# This Module handles commands and parssing utilities with Blades/Virtual Machines
#
__author__ = 'danielk'
#
# Main Class which should be used is MachineManage
# all drivers should inherit from AbsDriver

import subprocess,re,os
import sys

class AMMError(Exception):pass

class AbsDriver(object):
    def __init__(self,Host,User,Password,**Options):
        self.Host=Host
        self.User=User
        self.Password=Password

    def getMAC(self,Machine,NicNum=0):
        pass

    def getMACs(self,*MachineList):
        pass

    def getName(self,Machine):
        pass

    def setBootSeq(self,Machine):
        pass

    def doShutdown(self,Machine):
        pass

    def doStart(self,Machine):
        pass

    def doRestart(self,Machine):
        pass

## Decorator
class RunnerDecorator(object):
    Mode_Login='Expect'
    Mode_Remote='SSH'
    Mode_Local='Local'
    EncapToken="<<---- %s ---->>"
    StartToken= EncapToken % "Start Command OutPut"
    EndToken =  EncapToken % "End Command OutPut"
    def RunMode(self,Mode):
        self.Mode=Mode

    def __init__(self,Mode,Host,User,Password,Prompt):
        self.RunMode(Mode)
        self.Host=Host
        self.User=User
        self.Password=Password
        self.Prompt=Prompt

    def BuildExpect(self,Cmds):
        #print "Debug Build Expect is not ready yet"
        Result=[r"""#!/usr/local/bin/expect -f
spawn ssh %s@%s
expect {
      "*sword:" {
           send -- "%s\r"
      }
      "*yes/no" {
           send -- "yes\r"
           exp_continue
       }
      timeout {
           puts "Error - Fail to login\n"
	   exit 1
           # puts $expect_out(buffer)
       }
}
""" % (self.User,self.Host,self.Password)]
        for AmmCmd in Cmds:
            AmmCmd=re.sub(r'(^|[^\\])([\[\{\(])',r'\1\\\2',AmmCmd)
            ExpSec=r"""expect {
        -re "%s" {
                puts "%s\n"
                puts "%s\n"
                send "%s\r"
        }
        timeout {
           puts "Error - Fail to run command\n"
           exit 1
       }
}
""" % (self.Prompt,self.EndToken,self.StartToken,AmmCmd)
            Result.append(ExpSec)

        Result.append(r"""expect {
        -re "%s" {
                puts "\n%s\n"
        }
        timeout {
           puts "Error - Fail to run command\n"
           exit 1
       }
}
exit 0""" % (self.Prompt,self.EndToken))
        return Result

    def __call__(self,Func):
        #print "Build Decoration !!!"
        MyInstace=self
        def Decorator_Expect(self,Cmds):
            print "Decorator 1"
            ExpectFile="/tmp/Expt.tcl" ## Todo change it uniqe with thraed Number
            ExpCont=MyInstace.BuildExpect(Cmds)
            ExpFileObj=file(ExpectFile,'w')
            ExpFileObj.writelines(ExpCont)
            ExpFileObj.close()
            os.chmod(ExpectFile,0o777)
            print "Debug - Going to run Expect File %s" % ExpectFile
            Result=Func(self,[ExpectFile])
            Count=0
            for Line in Result:
                Count += 1
                ##print "Debug Type Line %s  Type Result %s" % (type(Line),type(Result))
                if re.search(r"> Error",Line) : return Result
                if not re.search(MyInstace.StartToken,Line): continue
                return Result[Count:]
            return None
        def Decorator_SSH(self,Cmds):
            print "Decorator 2"
            return Func(self,
                        ["ssh -o BatchMode=yes -o ConnectTimeout=20 \"%s\"" % Cmd for Cmd in Cmds])

        DecorarorMapper={ RunnerDecorator.Mode_Login : Decorator_Expect ,
                          RunnerDecorator.Mode_Remote : Decorator_SSH ,
                          RunnerDecorator.Mode_Local : Func }
        if self.Mode in DecorarorMapper:
            return DecorarorMapper[self.Mode]
        else:
            raise AMMError("Mode %s Not supported" % self.Mode)

class RemoteRunner(AbsDriver):
     def __init__(self,Host,User,Password,**Options):
        super(RemoteRunner,self).__init__(Host,User,Password,**Options)
        #print "Debug - in remote Runner Initiator"
        self.Mode=Options['Mode'] if 'Mode' in Options else RunnerDecorator.Mode_Login
        self.Promt=Options['Prompt'] if 'Prompt' in Options else '>'
        @RunnerDecorator(self.Mode,self.Host,self.User,self.Password,self.Promt)
        def RunCmds(self,Cmds):
            print "Debug - RunCmds Function"
            Result=[]
            Counter=1
            for SingleCmd in Cmds:
                Proc=subprocess.Popen(SingleCmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,shell=True)
                (sout,serr)=Proc.communicate()
                Proc.wait()
                if Proc.returncode:
                    Result.append("> Error %d StdErr(%d): " %(Proc.returncode,Counter))
                    Result.extend(str(serr).split(os.linesep))
                    Result.append("\t - StdOut: ")
                    Result.extend(str(sout).split(os.linesep))
                else:
                    Result.append("> O.K %d" % Counter)
                    Result.extend(str(sout).split(os.linesep))
                Counter += 1
            #print "Debug - Going to return %s" % str(Result)
            return Result
        self.RunCmds=RunCmds

class IBMAMMDriver(RemoteRunner):
    def __init__(self,Host,User,Password,**Options):
        Options['Prompt']=r"system>"
        super(IBMAMMDriver,self).__init__(Host,User,Password,**Options)
        print "Info  - Initialize IBM Blade Driver"

    def getMAC(self,Machine,NicNum=0):
        print "Debug - Internal info  %s , %s , %s" % (self.Host,self.User,self.Password)
        Result=None
        NicNum += 1
        StatePattern=(RunnerDecorator.StartToken,r"MAC Address (\d+):\s+(\S.+)",)
        #Flag=0
        RetOut=self.RunCmds(self,["info -T system:blade[%d]" % Machine])
        for Line in RetOut:
            if re.search(RunnerDecorator.EndToken,Line):
                print "Warning / Error - No MAC Address found for Blade %s Nic%d" % (Machine,NicNum)
                print "OutPut from AMM:"
                for i in RetOut:
                    i.rstrip('\n\r')
                    if i: print "\t%s" % i
                return None
            #print "Debug - Flag: %d , Line %s" % (Flag,Line)
            TmpMatch=re.search(r"MAC Address (\d+):\s+(\S+)",Line)
            if not TmpMatch: continue
            if int(TmpMatch.group(1)) == NicNum: return TmpMatch.group(2)
        print "Error:"
        for Line in RetOut: print "\t>%s" % Line
        raise AMMError("Fail to parse Blade %d Info" % Machine)

    def getMACs(self,*MachineList):
        Cmds=[]
        for InputRec in MachineList:
            MachineRec=InputRec if type(InputRec) is tuple else (InputRec,1,)
            Cmds.append("info -T system:blade[%d]" % MachineRec[0])
        OutLines=self.RunCmds(self,Cmds)
        Result=[None for i in xrange(len(Cmds))]
        Counter=0
        NicNum= MachineList[Counter][1] + 1 if type(MachineList[Counter]) is tuple else 1
        SlotNum=MachineList[Counter][0] if type(MachineList[Counter]) is tuple else MachineList[Counter]
        LineNum=0
        for Liney in OutLines:
            LineNum += 1
            Line=Liney.rstrip()
            #print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>%s<<<<<<<<<<<<<" % Line
            if re.search(RunnerDecorator.EndToken,Line):
                if Counter >= len(Result): Result.append(None)
                if not Result[Counter]:
                    print "Warning - Fail to find MAC address of NIC %d at slot %d" % (NicNum,SlotNum)
                    for i in OutLines[LineNum-35:LineNum]:
                        print "\t- %s" % i
                Counter += 1
                if Counter < len(MachineList):
                    NicNum= MachineList[Counter][1] + 1 if type(MachineList[Counter]) is tuple else 1
                    SlotNum=MachineList[Counter][0] if type(MachineList[Counter]) is tuple else MachineList[Counter][0]
                continue
            if Counter < len(Result) and Result[Counter]: continue
            TmpMatch=re.search(r"MAC Address (\d+):\s+(\S+)",Line)
            if not TmpMatch: continue
            #print "Debug  - Line %d has Nic Info : %s" % (LineNum,Line)
            #print " > %s ... %s" %(Line,TmpMatch.group(0))
            if int(TmpMatch.group(1)) == NicNum: Result[Counter]=TmpMatch.group(2)

        if len(Result) < len(MachineList):
            print "Error - Number of Match Result %d is not same as Input request %d " % (len(Result),len(MachineList))
            for Line in OutLines:
                print "\t>> %s" % Line
        return Result

class HPAMMDriver(RemoteRunner):

    def __init__(self,Host,User,Password,**Options):
        ## -re "\r\[^<>]*>"
        Options['Prompt']=r"\r\[^<>]*>"
        super(HPAMMDriver,self).__init__(Host,User,Password,**Options)

    def getMACs(self,*MachineList):
        Cmds=[]
        for InputRec in MachineList:
            MachineRec=InputRec if type(InputRec) is tuple else (InputRec,1,)
            Cmds.append("SHOW SERVER INFO %d" % MachineRec[0])
        OutLines=self.RunCmds(self,Cmds)
        Result=[None for i in xrange(len(Cmds))]
        Counter=0
        NicNum= MachineList[Counter][1] + 1 if type(MachineList[Counter]) is tuple else 1
        SlotNum=MachineList[Counter][0] if type(MachineList[Counter]) is tuple else MachineList[Counter]
        LineNum=0
        for Liney in OutLines:
            LineNum += 1
            Line=Liney.rstrip()
            #print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>%s<<<<<<<<<<<<<" % Line
            if re.search(RunnerDecorator.EndToken,Line):
                if Counter >= len(Result): Result.append(None)
                if not Result[Counter]:
                    print "Warning - Fail to find MAC address of NIC %d at slot %d" % (NicNum,SlotNum)
                    for i in OutLines[LineNum-35:LineNum]:
                        print "\t- %s" % i
                Counter += 1
                if Counter < len(MachineList):
                    NicNum= MachineList[Counter][1] + 1 if type(MachineList[Counter]) is tuple else 1
                    SlotNum=MachineList[Counter][0] if type(MachineList[Counter]) is tuple else MachineList[Counter][0]
                continue
            if Counter < len(Result) and Result[Counter]: continue
            TmpMatch=re.search(r"NIC\s+(\d+).+?\s+((\S+:){5,}\S+)",Line)
            if not TmpMatch: continue
            #print "Debug  - Line %d has Nic Info : %s" % (LineNum,Line)
            #print " > %s ... %s" %(Line,TmpMatch.group(0))
            if int(TmpMatch.group(1)) == NicNum: Result[Counter]=TmpMatch.group(2)

        if len(Result) < len(MachineList):
            print "Error - Number of Match Result %d is not same as Input request %d " % (len(Result),len(MachineList))
            for Line in OutLines:
                print "\t>> %s" % Line
        return Result

    def getMAC(self,Machine,NicNum=0):
        print "Debug - HP getMac parsing procedure"
        NicNum += 1
        RetOut=self.RunCmds(self,["SHOW SERVER INFO %d" % Machine])
        print "Debug - RunCmds return:"
        print RetOut
        print "\n\n\n\n"
        for Line in RetOut:
            if re.search(RunnerDecorator.EndToken,Line): return None
            #print "Debug - Flag: %d , Line %s" % (Flag,Line)
            TmpMatch=re.search(r"NIC\s+(\d+):\s+(\S+)",Line)
            if not TmpMatch: continue
            print "Match Reg:"
            print TmpMatch.group(0)
            if int(TmpMatch.group(1)) == NicNum: return TmpMatch.group(2)
        print "Error:"
        for Line in RetOut: print "\t>%s" % Line
        raise AMMError("Fail to parse HP Blade %d Info" % Machine)

## Decorator
def VsphereChk(Method):
    def Decorator(self,*Args):
        if not self.Server.is_connected():
            self.Connect()
            self.VmRec={}
        return Method(self,*Args)
    return Decorator

class VmWareDriver(AbsDriver):

    def __init__(self,Host,User,Password,**Options):
        super(VmWareDriver,self).__init__(Host,User,Password,**Options)
        self.ServerLog=Options['TmpLog'] if 'TmpLog' in Options else None
        import pysphere as VmWare
        self.Server=VmWare.VIServer()
        self.VmRec={}
        #print "Debug - Finish to Init VmWareDriver ..."
        #print VmWare.MORTypes
        self.Enum1=VmWare.MORTypes
        self.FDict={}
        self.Folder=Options['Folder'] if 'Folder' in Options else 'vm'
        #self.BuildVmList()

    def __del__(self):
        self.Server.disconnect()

    def Connect(self):
        try:
            if self.ServerLog:
                self.Server.connect(self.Host,self.User,self.Password,trace_file=self.Server)
            else:
                self.Server.connect(self.Host,self.User,self.Password)
        except :
            print "Error - Fail to connect to %s with user %s:" % (self.Host,self.User)
            print sys.exc_info()[0]
            raise

    def LoadVms(self,*VmList):
        if len(self.VmRec) <= 0 :
            self.BuildVmList(*VmList)
        Result={}
        PropList=('name','parent','config')
        for VmName in VmList:
            for VmRef in self.VmRec[VmName]:
                Prop=self.Server._get_object_properties(VmRef, property_names=PropList)
                if Prop:
                    Prop={P.Name: P.Val for P in Prop.get_element_propSet() }
                    Name=Prop['name']
                    del Prop['name']
                    if hasattr(Prop['config'],'get_element_files') :
                        TmpProp=Prop['config'].get_element_files()
                        Prop['VmPath']=TmpProp.VmPathName  #['VmPathName']
                        # print "Debug - Add VmPath %s" % TmpProp.VmPathName
                    Result[Name]=Prop
        return Result

    def ReadFolder(self,FolderName,*VmList):
        pass

    def getFolderRef(self,Folder):
        if len(self.FDict) <= 0:
            self._BuildFolderMap()
        print "Debug - getFolderRef(%s)" % Folder
        FList=Folder.split(r'/')
        if len(FList[0]) < 1 : FList.remove(FList[0])
        if not FList[0] == 'vm' : FList.insert(0,'vm')
        MoRefList=[]
        FolderDict={}
        for Name in FList:
            MoRefList.extend(self.FDict[Name])
        for MoRef in MoRefList:
            TmpRec=self.Server._get_object_properties(MoRef,('name','parent',))
            if TmpRec:
                FolderDict[MoRef]={ i.Name : i.Val for i in TmpRec.PropSet }
            else:
                raise Exception("Error  - Failed to retrieve Folder properties Reference %s" % MoRef)
        ### Go Over all the Folder Path till the root
        for Result in self.FDict[FList[-1]]:
            Current=Result
            TmpList=[]
            while Current in FolderDict:
                TmpList.append(FolderDict[Current]['name'])
                if re.search(r'datacenter',FolderDict[Current]['parent']):
                    TmpList.reverse()
                    if '/'.join(TmpList) == '/'.join(FList):
                        return Result
                    else:
                        break
                Current=FolderDict[Current]['parent']
        raise Exception("Folder %s not exists at Vsphere" % Folder)

    @VsphereChk
    def _BuildFolderMap(self):
        FList=self.Server._get_managed_objects(self.Enum1.Folder)
        if not FList:
            raise Exception("Error - Fail to read Folder List")
        self.FDict={}
        for FRef,FName in FList.items():
            if FName in self.FDict:
                self.FDict[FName].append(FRef)
            else:
                self.FDict[FName]=[FRef,]
        return self.FDict

    def ShowObj(self,Obj,DipList=[]):
        SwStr=str(type(Obj))
        if re.search(r'DynamicData',SwStr):
            print "\t\t ... Attribute List:"
            for AttName in dir(Obj):
                if re.match(r'(_|set|new)',AttName): continue
                RunStr='.'.join(("Obj",AttName,))
                try:
                    if eval('callable(%s)' % RunStr): RunStr += "()"
                    print eval(RunStr)
                except AttributeError as e:
                    print "Error - Excute: %s \n\t%s" % (AttName,e.message)
                if AttName in DipList:
                    print "\n--------- Internal Attribute Info %s --------->>" % AttName
                    self.ShowObj(eval(RunStr))
                    print "<<----------------- End of %s --------->>\n" % AttName
        elif re.search(r'ArrayOfString',SwStr):
            TmpStr=" , ".join(Obj.get_element_string())
            print "\t>>>[ %s ]" % TmpStr[:180] if len(TmpStr) > 180 else TmpStr
        elif type(Obj)==type(list()):
            print "\t<<=======   Display List  =======>>"
            for Iter in Obj:
                self.ShowObj(Iter)
            print "\t\t<<=====    End of List .... ======>>"
        else:
            print "  (Default)> " , Obj

    def getMACs(self,*MachineList):
        Fref=self.getFolderRef(self.Folder)
        print "Debug  - Folder %s Reference is %s " % (self.Folder,Fref)
        TmpResult={ Iter[0] : [int(Iter[1])] for Iter in MachineList }
        TmpHostList=[Iter[0] for Iter in MachineList]
        for VmName,VmRec in self.LoadVms(*TmpHostList).items():
            if not VmRec['parent'] == Fref : continue
            Vm1=self.Server.get_vm_by_path(VmRec['VmPath'])    #.get_vm_by_name(VmName)
            #print "\n\n --- %s Properties:" % VmName
            TmpDict=Vm1.get_property('devices')
            if TmpDict:
                for Nic in TmpDict.values():
                    RegTxt=re.search(r'Network.+?(\d+)',Nic['label'],flags=re.IGNORECASE)
                    if not RegTxt : continue
                    #print "  -- Nic %s MAC %s" % (RegTxt.group(1),Nic['macAddress'])
                    if TmpResult[VmName][0] + 1 == int(RegTxt.group(1)) :
                        TmpResult[VmName].append(Nic['macAddress'])
        Result=[ TmpResult[Iter[0]][-1] for Iter in MachineList]
        return Result

    @VsphereChk
    def BuildVmList(self,*VmNames):
        VmRefList=self.Server._get_managed_objects(self.Enum1.VirtualMachine)
        self.VmRec={}
        for VmRef,VmName in VmRefList.items():
            if VmName in VmNames:
                if VmName in self.VmRec:
                    self.VmRec[VmName].append(VmRef)
                else:
                    self.VmRec[VmName]=[VmRef]
        if len(self.VmRec) < len(VmNames):
            print "Warning - amount of request Vms (%d) not match the amount of found Vms (%d)" % (
                len(VmNames),len(self.VmRec) )

class MachineManage(object):
    DriverMap= { 'IBM' : IBMAMMDriver ,
                 'HP'  : HPAMMDriver ,
                 'VmWare' : VmWareDriver }
    def __init__(self,Factory,Host,User,Password,**Options):
        if not Factory in MachineManage.DriverMap:
            raise AMMError("%s Hardware type is not supported" % Factory)
        self.Driver=MachineManage.DriverMap[Factory](Host,User,Password,**Options)
        #self.Driver=AbsDriver(Host,User,Password)

    def getMAC(self,Machine,NicNum=0):
        return self.Driver.getMAC(Machine,NicNum)

    def getMACs(self,*MachineList):
        return self.Driver.getMACs(*MachineList)

    def getName(self,Machine):
        return self.Driver.getName(Machine)

    def setBootSeq(self,Machine):
        return self.Driver.setBootSeq(Machine)

    def doShutdown(self,Machine):
        return self.Driver.doShutdown(Machine)

    def doStart(self,Machine):
        return self.doStart(Machine)

    def doRestart(self,Machine):
        return self.Driver.doStart(Machine)
