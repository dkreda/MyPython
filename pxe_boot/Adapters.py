#!/usr/bin/env python
###############################################################################
#
# This Module handles commands and parssing utilities with Blades/Virtual Machines
#
__author__ = 'danielk'
#
# Main Class which should be used is MachineManage
# all drivers should inherit from AbsDriver

import subprocess,re,os,datetime
import sys,subprocess,threading
import pysphere as VmWare
## to support python 2.6.6
# ExpectPath=subprocess.check_output('which expect')
#print "Debug: ...."
print os.name
if not os.name =="nt":
    ExpectPath=subprocess.Popen(['which', 'expect'], stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()[0]
    ExpectPath=ExpectPath.rstrip(os.linesep)
else:
    ExpectPath='.'

Boot_PXE='PXE'
Boot_CD='CD'
Boot_HD='HD'
BootSequence=enumerate((Boot_PXE,Boot_HD,Boot_CD,))
TempFolder="/tmp"

class AMMError(Exception):pass

class AbsDriver(object):

    _BootSeqMap={}

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

    def setBootSeq(self,BootSeq,*MachineList):
        pass

    def doShutdown(self,Machine):
        pass

    def doStart(self,Machine):
        pass

    def doRestart(self,Machine):
        pass

    def CheckConnection(self):
        return False

    def is_PowerOff(self,*MachineList):
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
        #print "Debug - Decoratore Init Prompt is %s" % self.Prompt

    def BuildExpect(self,Cmds):
        #print "Debug Build Expect is not ready yet"
        Result=[r"""#!%s -f
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
""" % (ExpectPath,self.User,self.Host,self.Password)]
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
        #print "Debug - Decoratore Expect Prompt is %s" % self.Prompt
        return Result

    def BuildSSH(self,Cmds):
        return ["ssh -o BatchMode=yes -o ConnectTimeout=20 %s@%s \"%s\"" % (self.User,self.Host,Cmd) for Cmd in Cmds]

    def __call__(self,Func):
        #print "Build Decoration !!!"
        MyInstace=self
        def Decorator_Expect(self,Cmds):
            # print "Decorator 1"
            #tmpTime=datetime.datetime.now().time()
            ExpectFile="/".join((TempFolder,"Expect_%s.tcl" % threading.currentThread().getName() ,))
             #   "/tmp/Expt.tcl" ## Todo change it uniqe with thraed Number
            if not ExpectFile in self._DelList:
                self._DelList.append(ExpectFile)
            ExpCont=MyInstace.BuildExpect(Cmds)
            ExpFileObj=file(ExpectFile,'w')
            ExpFileObj.writelines(ExpCont)
            ExpFileObj.close()
            os.chmod(ExpectFile,0o777)
            # print "Debug - Going to run Expect File %s" % ExpectFile
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
            ## MyInstace=self
            return Func(self,MyInstace.BuildSSH(Cmds))
                        ## ["ssh -o BatchMode=yes -o ConnectTimeout=20 %s \"%s\"" % (MyInstace.host,Cmd) for Cmd in Cmds])

        DecorarorMapper={ RunnerDecorator.Mode_Login : Decorator_Expect ,
                          RunnerDecorator.Mode_Remote : Decorator_SSH ,
                          RunnerDecorator.Mode_Local : Func }
        if self.Mode in DecorarorMapper:
            return DecorarorMapper[self.Mode]
        else:
            raise AMMError("Mode %s Not supported" % self.Mode)

class RemoteRunner(AbsDriver):
    #######################################################
    # This class implement driver using cli commands

     def __init__(self,Host,User,Password,**Options):
        super(RemoteRunner,self).__init__(Host,User,Password,**Options)
        #print "Debug - in remote Runner Initiator"
        self.Mode=Options['Mode'] if 'Mode' in Options else RunnerDecorator.Mode_Login
        self.Promt=Options['Prompt'] if 'Prompt' in Options else '>'
        self._DelList=[]
        self.__InfoList=[]
        self.__StatusList=[]
        self.__Cash={}
        @RunnerDecorator(self.Mode,self.Host,self.User,self.Password,self.Promt)
        def RunCmds(self,Cmds):
            #print "Debug - RunCmds Function"
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

     def __getInfo(self):
         for Iter in xrange(15):
             Mac=["%02x" % random.randint(0,255) for Oct in xrang(6)]
             self.__Cash[Iter]={ 'MAC' : Mac}
             self.__Cash[Iter]['Name']="Slot%02d" % Iter

     def getMAC(self,Machine,NicNum=0):
         if not len(self.__Cash):
             self.__getInfo()
         if not Machine in self.__Cash:
            print "Error - No MAC Address found for Blade %s Nic%d" % (Machine,NicNum)
            return None
         else:
             return self.__Cash[Machine]['MAC']

     def CleanTmpFiles(self):
         print "Debug - Running CleanTmpFiles from %s" % self.__class__
         for File in self._DelList:
             os.remove(File)
         self._DelList=[]

     def setBootSeq(self,BootSeq,*MachineList):
         return { i : 0 for i in MachineList} if len(MachineList) >  1 else 0


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

    def CheckConnection(self):
        OutLines=self.RunCmds(self,['info'])
        if OutLines and len(OutLines) > 0:
            for Line in OutLines:
                if re.search(r'Manufacturer.+IBM',Line,re.IGNORECASE): return True
        return False


class HPAMMDriver(RemoteRunner):

    _BootSeqMap = { Boot_PXE : 'PXE' ,
                    Boot_CD : 'CD' ,
                    Boot_HD : 'HDD'}

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

    def CheckConnection(self):
        OutLines=self.RunCmds(self,['show ENCLOSURE INFO',])
        if OutLines and len(OutLines) > 0:
            for Line in OutLines:
                if re.search(r'Enclosure.+BladeSystem c\d+',Line,re.IGNORECASE): return True
                #print "DD %s" % Line
        return False

    def setBootSeq(self,BootSeq,*MachineList):
        ### SET SERVER BOOT ONCE <BootSeq> <Slot>
        if not BootSeq in self._BootSeqMap:
            raise AMMError("Boot Sequence request \"%s\" not supported. supported options are: %s" % (BootSeq,', '.join(self._BootSeqMap.keys())))
        #StrList=re.split(r'\s+',BootSeq)
        #StrList="PXE" if re.match('Net|PXE|DHCP|nw',StrList[0],re.IGNORECASE) else StrList[0]
        Cmds=[]
        Results={}
        for Slot in MachineList:
            Cmds.append("SET SERVER BOOT FIRST %s %s" % (self._BootSeqMap[BootSeq],Slot))
            Results[Slot]="Error"
        Lines=self.RunCmds(self,Cmds)
        print "Debug - HP Output:"
        for Line in Lines:
            Match=re.search(r'Blade #(\d+)',Line)
            if not Match: continue
            Slot=Match.group(1)
            if not Slot in Results:
                print "Warning - got Info of slot %s which is not part of configuration" % Slot
                print "Debug   - Full Line: %s" % Line
                continue
            Match=re.search(r'boot order changed to (\S+)',Line)
            if Match: # and Match.group(1) == self._BootSeqMap[BootSeq]:
                Results[Slot]=0
                print "Debug - Boot Sequence of Blade at slot %s Change to %s" % (Slot,Match.group(1))
            else:
                Results[Slot]="Error: %s" % Line
        return Results if len(MachineList) > 1 else Results[MachineList[0]]

    def _Reset(self,Machine,Retry):
        Cmnd="POWERON SERVER %s" if self.is_PowerOff(Machine) else "REBOOT SERVER %s"
        Cmnd=[ Cmnd % str(Machine)]
        Error=True
        Lines=self.RunCmds(self,Cmnd)
        for Line in Lines:
            if re.search(r'(Power|Reboot)ing.+%s' % Machine,Line) :
                Error=False
                break
        if Error and Retry: self._Reset(Machine,Retry-1)
        #print "Debug - send %s to Machine" % Cmnd[0]
        #Powering on blade 7.
        if Error:
            print "Debug- \"%s\" Return answer:" % Cmnd[0]
            print Lines

    def doRestart(self,Machine):
        ### REBOOT SERVER { ALL | <bay number> [{ , | - } <bay number>]} [FORCE] [{ NORMAL | PXE | HDD | RBSU | CD | FLOPPY | USB }]
        self._Reset(Machine,3)
#        Cmnd="POWERON SERVER %s" if self.is_PowerOff(Machine) else "REBOOT SERVER %s"
#        Cmnd=[ Cmnd % str(Machine)]
#        Error=True
#        if type(Retry) == type(None): Retry=3
#        Lines=self.RunCmds(self,Cmnd)
#        for Line in Lines:
#            if re.search(r'(Power|Reboot)ing.+%s' % Machine,Line) :
#                Error=False
#                break
#        if Error and Retry: self.doRestart(Machine,Retry-1)
        #print "Debug - send %s to Machine" % Cmnd[0]
        #Powering on blade 7.
#        if Error:
#            print "Debug- \"%s\" Return answer:" % Cmnd[0]
#            print Lines

    def is_PowerOff(self,*MachineList):
        Pattern_Title=re.compile(r'Blade #(\d+) Status:')
        Pattern_State=re.compile(r'Power:\s+(\S+)')
        CmdTemplate="SHOW SERVER STATUS %s"
        Cmds=[CmdTemplate % str(Slot) for Slot in MachineList]
        Lines=self.RunCmds(self,Cmds)
        Result={}
        for Slot in MachineList:
            Result[Slot]="Unknown"
        CurrentSlot="Init - No Slot found"
        for Line in Lines:
            MatchObj=Pattern_Title.search(Line)
            if MatchObj:
                CurrentSlot=MatchObj.group(1)
                continue
            MatchObj=Pattern_State.search(Line)
            if MatchObj:
                Result[CurrentSlot]=False if MatchObj.group(1).upper() == "ON" else True
        return Result if len(MachineList) > 1 else Result[MachineList[0]]




## Decorator
def VsphereChk(Method):
    def Decorator(self,*Args):
        if not self.Server.is_connected():
            self.Connect()
            self.VmRec={}
        return Method(self,*Args)
    return Decorator

class FolderTree(object):
    def __init__(self,VimServer):
        self.__Server=VimServer
        ##self.__Server=pysphere.VIServer()
        ##self.__FByPath={}
        #self.__FByMoRef={}
        self.RefreshTree()

    def RefreshTree(self):
        if not self.__Server.is_connected():
            raise Exception("VimServer EsXI not Connected")
        print "Debug - Read Folders from Machine"
        self.__FByMoRef=self.__Server._get_managed_objects(VmWare.MORTypes.Folder)
        print "Debug - Start analyze ..."
        if not self.__FByMoRef:
            self.__FByMoRef={}
            self.__FByPath={}
            return
        print "Debug - Read Folder Objects ..."
        for Mo_Ref in self.__FByMoRef.keys():
            VmRec=self.__Server._get_object_properties(Mo_Ref,property_names=('name','parent',))
            self.__FByMoRef[Mo_Ref]={Prop.Name : Prop.Val for Prop in VmRec.PropSet }
            self.__FByMoRef[Mo_Ref]['Ref']=Mo_Ref
        print "Debug - Sync Indexes"
        self.__SyncIndex()
        print "Debug - Folder List:"
        print "\n".join(self.__FByPath.keys())

    def getFullPath(self,Ref):
        #print "-D- Recursive call %s" % Ref
        Tmp=self.__FByMoRef[Ref]['parent']  if 'parent' in self.__FByMoRef[Ref] else None
        if Tmp and Tmp in self.__FByMoRef:
            #print "Debug - Obj (%s -(%s)) has Parent (%s -(%s))" % (Ref,self.__FByMoRef[Ref]['name'],Tmp,self.__FByMoRef[Tmp]['name'])
            return "" if Tmp == Ref else \
                "%s/%s" % (self.getFullPath(self.__FByMoRef[Ref]['parent']),self.__FByMoRef[Ref]['name'])
        else:
            return ""

    def __SyncIndex(self):
        self.__FByPath={}
        for Ref,VmRec in self.__FByMoRef.items():
            FullPath=self.getFullPath(Ref)
            VmRec['FullPath']=FullPath
            self.__FByPath[FullPath]=VmRec

    def __contains__(self, item):
        return item in self.__FByMoRef or item in self.__FByPath

    def __getitem__(self, item):
        if item in self.__FByMoRef:
            return self.__FByMoRef[item]
        elif item in self.__FByPath:
            return self.__FByPath[item]
        return None

class VmWareDriver(AbsDriver):

    def __init__(self,Host,User,Password,**Options):
        super(VmWareDriver,self).__init__(Host,User,Password,**Options)
        self.ServerLog=Options['TmpLog'] if 'TmpLog' in Options else None
        self.__Options=Options
        #import pysphere as VmWare
        self.Server=VmWare.VIServer()
        self.VmRec={}
        #print "Debug - Finish to Init VmWareDriver ..."
        #print VmWare.MORTypes
        self.Enum1=VmWare.MORTypes
        self.FDict={}
        self.Folder=Options['Folder'] if 'Folder' in Options else 'vm'
        self.ViException=VmWare.resources.vi_exception.VIException
        #self.BuildVmList()

    def __BuildTopology(self):
        print "Debug - Read Vm Machines ...."
        print "Debug - Read Folder ...."
        if not self.Server.is_connected():
            self.Connect()
        self.Dir=FolderTree(self.Server)
        TmpObjList=self.Server._get_managed_objects(VmWare.MORTypes.VirtualMachine)
        for VmView in TmpObjList.keys():
            TmpObj=self.Server._get_object_properties(VmView, property_names=('name','parent','network',))
            for KeyName in TmpObj.PropSet:
                if not TmpObjList[VmView] in self.FDict :
                    self.FDict[TmpObjList[VmView]]={}
                self.FDict[TmpObjList[VmView]][KeyName.Name]=KeyName.Val
        print "Debug - Topology :"
        for tt,pp in self.FDict.items():
            print "%s:" % tt
            for gg,ll in pp.items():
                print "\t - %s = %s" % (gg,ll)

        print "\n\n\n\n"
        for Vm in self.FDict.values():
            try:
                print "%s/%s" % (self.Dir.getFullPath(Vm['parent']),Vm['name'])
            except KeyError as e:
                print "\n"
                print e.message
                print Vm
                print "\n"



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
            print "\t\t(%s)" % self.Password
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
                    ### Change to support Python 2.6.6 ....
                    #Prop={P.Name: P.Val for P in Prop.get_element_propSet() }
                    Prop={}
                    for P in Prop.get_element_propSet():
                        Prop[P.Name]=P.Val
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
                ## Change to support Python 2.6.6
                #FolderDict[MoRef]={ i.Name : i.Val for i in TmpRec.PropSet }
                TmpDict={}
                for i in TmpRec.PropSet:
                    TmpDict[i.Name]=i.Val
                FolderDict[MoRef]=TmpDict
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
        ### Change to support Python 2.6.6
        #TmpResult={ Iter[0] : [int(Iter[1])] for Iter in MachineList }
        TmpResult={}
        for Iter in MachineList:
            TmpResult[Iter[0]]=[ int(Iter[1])]

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

    def CheckConnection(self):
        try:
            if not self.Server.is_connected():
                self.Connect()
                self.VmRec={}
            return self.Server.is_connected()
        #except socket.error:
        except Exception as ViExce:
            #print "Debug - Vsphere connection failed"
            #print ViExce
            #print "Type of self %s Type of Exception %s" % (type(self.ViException),type(ViExce))
            ExcepTypes=('socket','VIApiException')
            if re.search('|'.join(ExcepTypes),str(type(ViExce))):
                return False
            raise

    def CleanTmpFiles(self): pass

    def setBootSeq(self,BootSeq,*MachineList):
        print "Debug - Setting Boot Sequence at VmWare ...."
        if not len(self.FDict):
            self.__BuildTopology()
        for Machin in MachineList:
            if not Machin in self.FDict:
                print "Warning - Machine %s not part of system" % Machin
                continue
            VmView=self.Server.get_vm_by_name(self.FDict[Machin]['name'])
            TaskObj=VmView.set_extra_config({'bios.bootOrder' : Boot_PXE })
            print TaskObj
            print "========="
            print dir(TaskObj)

    def doRestart(self,Machine):
        print "Debug - Restart %s ...." % Machine
        if not len(self.FDict):
            self.__BuildTopology()
        #for Machin in MachineList:
        #    if not Machin in self.FDict:
        #        print "Warning - Machine %s not part of system" % Machin
        #        continue
        VmView=self.Server.get_vm_by_name(self.FDict[Machine]['name'])
        return VmView.reset()




class MachineManage(object):
    DriverMap= { 'IBM' : IBMAMMDriver ,
                 'HP'  : HPAMMDriver ,
                 'VmWare' : VmWareDriver ,
                 "TestRunner" : RemoteRunner}
    def __init__(self,Factory,Host,User,Password,**Options):
        if not Factory in MachineManage.DriverMap:
            raise AMMError("%s Hardware type is not supported" % Factory)
        if not 'Mode' in Options: Options['Mode']=ConnMode
        self.Driver=MachineManage.DriverMap[Factory](Host,User,Password,**Options)
        #self.Driver=AbsDriver(Host,User,Password)

    def getMAC(self,Machine,NicNum=0):
        return self.Driver.getMAC(Machine,NicNum)

    def getMACs(self,*MachineList):
        return self.Driver.getMACs(*MachineList)

    def getName(self,Machine):
        return self.Driver.getName(Machine)

    def setBootSeq(self,BootSeq,*MachineList):
        return self.Driver.setBootSeq(BootSeq,*MachineList)

    def doShutdown(self,Machine):
        return self.Driver.doShutdown(Machine)

    def doStart(self,Machine):
        return self.doStart(Machine)

    def doRestart(self,Machine):
        return self.Driver.doRestart(Machine)

    def is_PowerOff(self,*MachineList):
        return self.Driver.is_PowerOff(*MachineList)

    def Clean(self):
        print "Debug - Running Clean from %s" % self.__class__
        if hasattr(self.Driver,'CleanTmpFiles'):
            self.Driver.CleanTmpFiles()

    @property
    def Hardware(self):
        CName=re.compile(r'[\'\"](.+?)[\'\"]')
        for Str,StrType in self.DriverMap.items():
            Match = CName.search("%s" % StrType)
            if re.search(Match.group(1),"%s" % self.Driver):
                return Str
            # print "Debug -- %s Not Match" % StrType
        raise Exception("Fail to find %s" % self.Driver)
        return self.Driver

def CheckHardware(Ip,User,Password):
    ##print "Not Ready yet ...."
    ##print "\nDebug - CheckHardware(%s,%s,%s)" % (Ip,User,Password)
    ## if os.name == 'nt' and
    for HwName,Driver in MachineManage.DriverMap.items():
        try:
            Tmp=Driver(Ip,User,Password,Mode=ConnMode)
            if Tmp.CheckConnection():
                Tmp.CleanTmpFiles()
                return HwName
        except AMMError:
            print "Debug - %s is not %s" % (Ip,HwName)
    return None

ConnMode=RunnerDecorator.Mode_Login