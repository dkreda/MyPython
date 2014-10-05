#!/usr/bin/env python

__author__ = 'danielk'

import Adapters,ConfClass,zipfile
import re,os,datetime,time,signal
import threading,operator,subprocess

#############################################
# GLobal Definitions
#############################################
ParamLine=re.compile(r'([^#]+?)=\s*[\'\"](.+)[\'\"]')
Adapters.ConnMode=Adapters.RunnerDecorator.Mode_Remote
Defaults={
    'batch'     : {
            'Description' : 'Indicates This script run via external Batch file - means less check to do (should run faster)'
                  } ,
    'log'       : {
            'Description' : 'optional indicates to which log file output the log messages' ,
            'ValidPattern' : r'\S+' ,
            'aliases' : ['l','L']
                  } ,
    'new_info_dir' : {
            'Description' : 'Determines the location of the INFO Files' ,
            'ValidPattern' : r'\S+' ,
            'aliases' : ['nid']
                     } ,
    'user'      : {
            'ValidPattern' : r'\S+' ,
            'aliases' : ['u']
                  } ,
    'password'  : {
            'ValidPattern' : r'\S+' ,
            'aliases' : ['p']
                  },
    'amm'       : {
            'ValidPattern' : r'\S+' ,
            'aliases' : ['a']
                  } ,
    'info'      : {
            'ValidPattern' : r'\S+' ,
            'aliases' : ['i']
                  } ,
    'ip'        : {
            'ValidPattern' : r'(\d+\.){3}\d+' ,
            'aliases' : ['i']
                  } ,
    'role'      : {
            'ValidPattern' : r'\S+' ,
            'aliases' : ['r']
                  } ,
    'hostname'  : {
            'ValidPattern' : r'\S+' ,
            'aliases' : ['hn']
                  } ,
    'slot'      : {
            'ValidPattern' : r'\d+' ,
            'aliases' : ['s']
                  } ,
    'ems'       : {
            'ValidPattern' : r'(\d+\.){3}\d+' ,
            'aliases' : ['e']
                  } ,
    'other_ems_server' : {
            'ValidPattern' : r'\d+' ,
            'aliases' : ['oes']

                    } ,
    'install_primary' : {  } ,
    'check'     : {
            'aliases' : ['c']
                  } ,
    'custom'    : {} ,
    'status_log': {
            'ValidPattern' : r'\S+'
                  }
         }

def VerifyUser(User):
    print "Debug  - VerifyUser(%s) Not Ready yet ..." % User
    return True

def VerifySingleTone():
    print "Debug - VerifySingleTone Not ready Yet"
    Tmp=re.search(r'([^\/]+)$',__file__)
    BaseName=Tmp.group(1) if Tmp else None
    Single=subprocess.check_output(["bash",'-c',r"ps -ef | grep %s | grep -v 'grep' | wc -l" % BaseName])
    return int(Single) <= 1

def Validation(Conf):
    print "Debug - Validation is not ready yet ....."
    Adapters.ConnMode=Adapters.RunnerDecorator.Mode_Remote if 'batch' in Conf else Adapters.RunnerDecorator.Mode_Login
    if not 'Debug' in Conf:
        print "Debug - Check Active EMS ..."
        InfoCfg=ParseInfoFile("/etc/FlashNetworks/INFO")
        Active=False if subprocess.call([r'ifconfig',r'-a | grep %s' % InfoCfg['ems_ip']]) else True
    return True

class InfoCollector(object):
    InfoPattern=re.compile(r'INFO_(\d+\.){3}\d+')
    def __init__(self,InfoPath):
        self.Path=InfoPath
        self.BuildLists()

    def BuildLists(self):
        FileList=os.listdir(self.Path)
        self._BaseName=[FName for FName in FileList if self.InfoPattern.search(FName)]
        self._InfoList=["/".join((self.Path,FName,)) for FName in self._BaseName]

    def ReadInfo(self,Name):
        if Name in self:
           FObj=file(self.getFullName(Name),'r')
           Buffer=FObj.readlines()
           FObj.close()
           return ParseInfo(*Buffer)
        else:
            raise Exception("Error %s not exists at Info collection" % Name)

    def getFullName(self,Name):
        if Name in self._BaseName:
            for item in self._InfoList:
                if re.search("%s$" % Name,item):
                    return item
            ## return "/".join((self.Path,Name,))
        elif Name in self._InfoList:
            return Name
        raise Exception("Error %s not exists at Info collection" % Name)

    def __contains__(self, item):
        return item in self._BaseName or self._InfoList

    def __getitem__(self, item):
        return self.ReadInfo(item)

    def __iter__(self):
        for item in self._BaseName:
            yield item

class InfoPkgCollector(InfoCollector):
    def __init__(self,InfoPath):
        self.Pkg=zipfile.ZipFile(InfoPath)
        super(InfoPkgCollector,self).__init__(InfoPath)

    def BuildLists(self):
        self._InfoList=[MemName for MemName in self.Pkg.namelist() if self.InfoPattern.search(MemName) ]
        self._BaseName=[]
        for MemName in self._InfoList:
            Match=re.search(r'([^\/\\]+)$',MemName)
            self._BaseName.append(Match.group(1))

    def ReadInfo(self,Name):
        if Name in self:
            InfoFile=self.Pkg.open(self.getFullName(Name),'r')
            Conntent=InfoFile.readlines()
            InfoFile.close()
            return ParseInfo(*Conntent)
        raise Exception("Error %s is not part of info collection (at Package %s)" % (Name,self.Pkg.filename))


def BuildHostList(Conf):
                       ## Map content
                       ## Key  : [Info Param, identifier]
    HostSelectorMap = { 'ip'   : ['mgmt_ip','mgmt_ip'] ,
                        'role' : ['server_role','mgmt_ip'] ,
                        'hostname' : ['server_name','server_name'] ,
                        'slot' : ['chassis_slot_number','mgmt_ip'] }
    Result={}
    print "Build HostList not ready yet ...."
    InfoDir=Conf['new_info_dir'][-1] if 'new_info_dir' in Conf else "/tftpboot/INFO_FILES"
    Infos= InfoCollector(InfoDir) if os.path.isdir(InfoDir) else InfoPkgCollector(InfoDir)
    ### Go Over all the Info Files and save only the relevant
    for InfoName in Infos:
        TmpInfoConf=Infos[InfoName]
        ## Go Over all the CLI Selection parameter to verify if the Machine should do boot
        for ConfParam,Rec in HostSelectorMap.items():
            if ConfParam in Conf and Rec[0] in TmpInfoConf:
                if TmpInfoConf[Rec[0]] in Conf[ConfParam]:
                    ## Verify Chassi Record already exists
                    ChIP=TmpInfoConf['chassis_ip']
                    if not ChIP in Result:
                        Result[ChIP]=Infos['_'.join(("INFO",ChIP,))]
                    TmpInfoConf['Identifier']=TmpInfoConf[Rec[1]]
                    Result[ChIP][TmpInfoConf['mgmt_ip']]=TmpInfoConf
    ## Just for Debug or user interface:
    HostList=[]
    for ChassiRec in Result.values():
        for KeyName,Rec in ChassiRec.items():
            if re.match(r'(\d+\.){3}\d+',KeyName):
                HostList.append(Rec['Identifier'])
    print "\nThe following servers will be reboot:\n\t%s" % " ".join(HostList)
    return Result


def ParseInfo(*Content):
    Result={}
    for Line in Content:
        MatchObj=ParamLine.search(Line)
        if MatchObj:
            Result[MatchObj.group(1)]=MatchObj.group(2)
    return Result

def ParseInfoFile(FileName):
    FObj=file(FileName,'r')
    Buffer=FObj.readlines()
    FObj.close()
    return ParseInfo(*Buffer)

def WrLog(FileName,*Messages):
    FObj=file(FileName,'a')
    FObj.writelines([ "%s\n" % Line for Line in Messages])
    FObj.close()

def ClearSSHFingerPrint(Ip):
    SShFile="/root/.ssh/known_hosts"
    FObj=file(SShFile,'r')
    Lines=FObj.readlines()
    FObj.close()
    NewLines=[]
    for Line in Lines:
        if re.match(r"%s\s" % Ip,Line): continue
        NewLines.append(Line)
    FObj=file(SShFile,'w')
    FObj.writelines(NewLines)
    FObj.close()

def CheckConnection(IP,TimeOut=3):
        return not os.system("ping -c 2 -W %d %s 2>&1 > /dev/nul" % (TimeOut,IP))

def WaitResetStart(Blade):
    TimeOut=datetime.datetime.now().time()
    TimeOut=datetime.timedelta(hours=TimeOut.hour,seconds=TimeOut.second,minutes=TimeOut.minute)
    TimeOut=datetime.timedelta(seconds=TimeOut.seconds + 30)
    IP=Blade['mgmt_ip']
    ConnState = CheckConnection(IP)
    ## Verify offline or wait period time
    print "Debug - Verify offline at Blade %s (slot %s) Connection State is %s" % (IP,Blade['chassis_slot_number'],ConnState)
    while ( not Blade['Driver'].is_PowerOff(Blade['chassis_slot_number']) and not operator.xor(ConnState,CheckConnection(IP))):
        Perioud=datetime.datetime.now().time()
        Perioud=datetime.timedelta(hours=Perioud.hour,seconds=Perioud.second,minutes=Perioud.minute)
        if Perioud > TimeOut:
            print "Debug - offLine Verification timeout Blade %s (slot %s)" % (IP,Blade['chassis_slot_number'])
            print "Debug - Blade offline Verification Results:\n\tPower off State %s\n\tConnectivity %s\n\tConnection State %s" % \
                    (Blade['Driver'].is_PowerOff(Blade['chassis_slot_number']),CheckConnection(IP),ConnState)
            break
        time.sleep(1)
    print "Debug - Assume offline at Blade %s (slot %s)" % (IP,Blade['chassis_slot_number'])
    ### Verify the Blade is up again
    while ( Blade['Driver'].is_PowerOff(Blade['chassis_slot_number']) or not CheckConnection(IP) ):
        time.sleep(1)

def CheckAnaconda(Blade):
    ClearSSHFingerPrint(Blade['mgmt_ip'])
    ChkObj=Adapters.RemoteRunner(Blade['mgmt_ip'],"root","flashnetworks",Mode=Adapters.RunnerDecorator.Mode_Login,Prompt=r'#')
    Lines=ChkObj.RunCmds(ChkObj,["tail -3 /tmp/anaconda.log"])
    Count=0
    for Line in Lines:
        if re.search("Connection refused",Line) : return False
        if re.match(r'[\d:,]+\s+\S+\s+:',Line): Count +=1
    if not Count:
        print "Debug - Anaconda Check of Blade %s:" % Blade['mgmt_ip']
        print Lines
    return True if Count else False

class BaseState(object):
    def __init__(self,Blade):
        self.Blade=Blade

    def getNext(self,Input):
        pass

    def State(self):
        return "Base"

    def RunState(self):
        pass

class LastReboot(BaseState):
    """ This is the Last in the PXE Installation it waits till the Machine is avialable
        after reboot.
    """
    def __init__(self,Blade):
        super(LastReboot,self).__init__(Blade)
        self._State="Last Reset"

    def State(self):
        return self._State

    def RunState(self):
        WaitResetStart(self.Blade)
        while not CheckConnection(self.Blade['mgmt_ip']):
            time.sleep(5)
        self._State="Finshed O.K"
        return self._State


class SingleBlade(object):
    _StateMap={}
    def __init__(self,BladeRec,Conf,State="Init"):
        self.Blade=BladeRec
        self.Conf=Conf
        self.Log="/var/tmp/.pxe_status_log.%s.log" % BladeRec['mgmt_ip']
        self.State=State

    def _ChkBootSeq(self,Boot):
        if 'status_log' in self.Conf:
            WrLog(self.Log,"Executing bootlist change to %s" % Boot)
        TmpChk=self.Blade['Driver'].setBootSeq(Boot,self.Blade['chassis_slot_number'])
        if TmpChk:
            ### TO DO Change this to interactive request ...
            print "Error - Failed to change Boot sequence Slot %s" % self.Blade['chassis_slot_number']
            print "\t %s" % TmpChk
            print " do you want to continue ???????????"
            return False
        return True

    def _Restart(self):
        if 'status_log' in self.Conf:
            WrLog(self.Log,"Executing power cycle on the server")
        self.Blade['Driver'].doRestart(self.Blade['chassis_slot_number'])
        self.State="Reset - send"
        time.sleep(30)
        if 'status_log' in self.Conf:
            WrLog(self.Log,"Wait Blade to start On")
        ### Check on state
        ChkFlag=self.Blade['Driver'].is_PowerOff(self.Blade['chassis_slot_number'])
        while ChkFlag:
            if type(True) == type(ChkFlag):
                time.sleep(1)
            else:
                raise Exception("Blade State return incorrect slot ot unknown state %s" % ChkFlag)
            ChkFlag=self.Blade['Driver'].is_PowerOff(self.Blade['chassis_slot_number'])
        self.State="Power On"

    def _ChkAnaconda(self):
        #print "Debug - Check Anaconda installation Status at %s" % self.Blade['mgmt_ip']
        ClearSSHFingerPrint(self.Blade['mgmt_ip'])
        ChkObj=Adapters.RemoteRunner(self.Blade['mgmt_ip'],"root","flashnetworks",Mode=Adapters.RunnerDecorator.Mode_Login,Prompt=r'#')
        Lines=ChkObj.RunCmds(ChkObj,["tail -3 /tmp/anaconda.log"])
        #print "Debug - Anaconda Check:"
        Count=0
        for Line in Lines:
            if re.search("Connection refused",Line) : return False
            if re.match(r'[\d:,]+\s+\S+\s+:',Line): Count +=1
            #if Count > 1 :
            #    print "Debug - Anaconda installation is still running .... :"
            #    print Line
        if not Count:
            print Lines
        else:
            #print "Debug - Anaconda Installation is still running ..."
            pass
        return True if Count else False

    def _CheckConnection(self,IP):
        return not os.system("ping -c 2 -W 3 %s 2>&1 > /dev/nul" % IP)

    def getState(self):
        return self.State

    def RunPXEProcess(self):
        if not self._ChkBootSeq(Adapters.Boot_PXE):
            raise Exception("Fail to change Boot sequence to %s at slot %s" % (self.Blade['mgmt_ip'],self.Blade['chassis_slot_number']))
        self._Restart()

        if 'status_log' in self.Conf:
            WrLog(self.Log,"Blade is power on wait Anaconda installation to start")
        time.sleep(20)
        ### Verify Anaconda installation start
        while self.Blade['Driver'].is_PowerOff(self.Blade['chassis_slot_number']):
            time.sleep(5)

        print "Debug - Check connectivity to %s" % self.Blade['mgmt_ip']
        while not self._CheckConnection(self.Blade['mgmt_ip']) : time.sleep(2)
        Count=150
        CGap=3
        print "Debug - Wait Anaconda installation to start at %s (Slot %s)" % (self.Blade['mgmt_ip'],self.Blade['chassis_slot_number'])
        while not self._ChkAnaconda():
            if Count:
                if not ((CGap * Count) % 60) :
                    print "Debug - Anaconda have not been started yet ... waiting more %d Minutes" % int(CGap*Count/60)
                Count -= 1
                time.sleep(CGap)
            else :
                raise Exception("Error - Anaconda installation have not started after restart at %s (Slot %s)" %
                                (self.Blade['mgmt_ip'],self.Blade['chassis_slot_number'],))
        ### Anaconda installation have been start .....
        if not self._ChkBootSeq(Adapters.Boot_HD):
            raise Exception("Fail to change Boot sequence to %s at slot %s" % (self.Blade['mgmt_ip'],self.Blade['chassis_slot_number']))
        self.State="Anaconda installation"
        if 'status_log' in self.Conf:
            WrLog(self.Log,"Anaconda installation started")
        time.sleep(30)
        Count=0
        while self._ChkAnaconda():
            Count += 1
            if not Count % 6 : print "Debug - Anaconda installation still running ..."
            time.sleep(5)
        if 'status_log' in self.Conf:
            WrLog(self.Log,"Anaconda installation Finished")
        print "Debug - Anaconda installation Finished"
        Count=15
        while not self.Blade['Driver'].is_PowerOff(self.Blade['chassis_slot_number']):
            Count -= 1
            if not Count: break
            time.sleep(1)
        ##time.sleep(3)
        if Count: print "Debug - restart (power off) detected ...."
        print "Debug - Check connectivity to %s" % self.Blade['mgmt_ip']
        while not self._CheckConnection(self.Blade['mgmt_ip']) : time.sleep(2)
        self.Blade['Driver'].Clean()
        if 'status_log' in self.Conf:
            WrLog(self.Log,"Finished, OK")
        return 0

class AnacondaInstall(BaseState):
    def __init__(self,Blade):
        super(AnacondaInstall,self).__init__(Blade)
        self._State="Wait Anaconda Installation"

    def RunState(self):
        Count=3
        while  Count:
            LastTry=self.Blade['Driver'].setBootSeq(Adapters.Boot_HD,self.Blade['chassis_slot_number'])
            if LastTry:
                time.sleep(1)
                Count -= 1
            else :
                Count=0
        if LastTry:
            print "Debug - Fail to change Boot sequence to HD at slot %d" % self.Blade['chassis_slot_number']
            raise Exception("Error - Fail to change Boot sequence to HD at slot %d" % self.Blade['chassis_slot_number'])
        Count=0
        while CheckAnaconda(self.Blade):
            Count += 1
            if not Count % 13 : print "Debug - Anaconda installation is still running on Blade %15s (Slot %2s)..." % \
                                      (self.Blade['mgmt_ip'],self.Blade['chassis_slot_number'])
            time.sleep(5)
        #if 'status_log' in self.Conf:
        #    WrLog(self.Log,"Anaconda installation Finished")
        self._State="Last Reset"
        print "Debug - Anaconda installation Finished at Blade %s" % self.Blade['mgmt_ip']
        return self._State

class ResetFirst(BaseState):
    def __init__(self,Blade):
        super(ResetFirst,self).__init__(Blade)
        self._State="BootStart First"

    def RunState(self):
        self.Blade['Driver'].doRestart(self.Blade['chassis_slot_number'])
        print "Debug - Reset is done to Blade %15s (Slot %s)" % (self.Blade['mgmt_ip'],self.Blade['chassis_slot_number'])
        WaitResetStart(self.Blade)
        print "Debug - %s Reset done check connectivity" % self.Blade['chassis_slot_number']
        while not CheckConnection(self.Blade['mgmt_ip']):
            time.sleep(10)
        print "Debug - %s IP is up check Anaconda" % self.Blade['chassis_slot_number']
        while not CheckAnaconda(self.Blade):
            time.sleep(10)
        print "Debug - %s Anaconda installation started" % self.Blade['chassis_slot_number']
        self._State='Wait Anaconda Installation'
        return self._State

class ChBootSeq(BaseState):
    pass

def Th_Blade(State,Blade):
    StateMap={ 'Change Boot PXE ' : ChBootSeq ,
               'BootStart First' : ResetFirst,
               'Wait Anaconda Installation' : AnacondaInstall ,
               'Last Reset' : LastReboot
             }
    if not State in StateMap:
        raise Exception("Error - Unknown State %s" % State)
    while not State ==  "Finshed O.K":
        MyBlade=StateMap[State](Blade)
        State = MyBlade.RunState()
        print "Debug - Blade %s Change state to %s" % (Blade['mgmt_ip'],State,)
        Blade['State']=State

def Th_ChangeBootSeq(BootSeq,Driver,*BladeRec):
    ##SlotList={"Dummy" : 1 , "Dummy1" : 2} ## This are just Dummy to ensure
    SlotList={}
    for Blade in BladeRec:
        #print "Debug - Assign Slot %s at Chassi %s" %
        SlotList[Blade['chassis_slot_number']]=Blade
        Blade['Driver']=Driver
    #SlotList=[Blade['chassis_slot_number'] for Blade in BladeRec]
    #Driver=Adapters.MachineManage()
    Results=Driver.setBootSeq(BootSeq,*SlotList.keys())
    ThreadPool=[]
    if len(SlotList) < 2 : Results={ BladeRec[0]['chassis_slot_number'] : Results }
    for Slot,Status in Results.items():
        if not Status:
            ThreadPool.append(threading.Thread(target=Th_Blade,
                                               name="ThBlade_%s_Slot_%s" % (SlotList[Slot]['mgmt_ip'],SlotList[Slot]['chassis_slot_number']) ,
                                               args=('BootStart First',SlotList[Slot],)
            ))
            TmpTime=datetime.datetime.now().time()
            print "Debug %s - Start Thread %s" % (TmpTime,ThreadPool[-1].getName())
            ThreadPool[-1].start()
            #TmpTime=datetime.datetime.now().time()
            #print "Debug %s - Chassi Envelop Thread Return from slot %s" % (TmpTime,Slot)
        else :
           print "Error - Blade %s at slot %s Failed to change Boot sequence (at beggining ...) Status %s" % (SlotList[Slot]['mgmt_ip'],SlotList[Slot]['chassis_slot_number'],Status)

    TimeOut=1500
    Flag=len(ThreadPool)
    while Flag and TimeOut:
        TimeOut -= 1
        Flag=0
        time.sleep(1)
        for Thx in ThreadPool:
            if Thx.isAlive():
                Flag += 1
        if not TimeOut % 180 :
            print "Debug - Chassi Thread %s waits %d threads to finish" % (threading.currentThread().getName(),Flag)

    print "\nDebug - Chassi Thread %s Finished.\n\tNumber of active Thread is %d" % (threading.currentThread().getName(),threading.activeCount())

def ChassiOp(ChRec):
    #ChRec=
    HwType=Adapters.CheckHardware(ChRec['chassis_ip'],ChRec['user_name'],ChRec['password'])
    if HwType:
        ##ChRec['HW']=HwType
        Driver=Adapters.MachineManage(HwType,ChRec['chassis_ip'],ChRec['user_name'],ChRec['password'])
        print "Debug - Chassi %s is type %s" % (ChRec['server_name'],HwType)
        Th_ChangeBootSeq(Adapters.Boot_PXE,Driver,*[BladeRec for Blade,BladeRec in ChRec.items() if re.match(r'(\d+\.){3}\d+',Blade)])

def SingleBladeOp(BladeRec):
    ## print "Debug  - should fork ...."
    PID= os.fork()
    if PID : return PID
    CurrentBlade=SingleBlade(BladeRec,FullConfig)
    if CurrentBlade.RunPXEProcess():
        exit(7)
    else:
        exit(0)

def DtToInt(DatTime):
    Res=DatTime.hour * 3600 + DatTime.minute * 60 + DatTime.second
    return Res

def WaitProcess(TimeOut,PidList):
    NowTime=datetime.datetime.now().time()
    print "Debug - in WaitProcess %s" % NowTime
    Result={}
    for Pid in PidList.keys():
        Result[Pid]="Running"
    RunningFlag=len(Result)
    while RunningFlag:
        for Pid,Rec in Result.items():
            if not Rec == "Running": continue
            Status=os.waitpid(Pid,os.P_NOWAIT)
            if Status and Status[0]:
                print "Debug - Process %d (%d , %d)" % (Pid,Status[0],Status[1])
                #os.kill(Pid,-9)
                Result[Pid]="Error %d" % Status[1] if Status[1] else "O.K"
                ## print "Debug -- Number of runing Process %d" % RunningFlag
                RunningFlag -= 1
        if RunningFlag:
            if DtToInt(datetime.datetime.now().time()) < DtToInt(NowTime) + TimeOut:
                time.sleep(1)
            else: break
        ## print "\n\nDebug -- Total Number of runing Process %d" % RunningFlag
    if RunningFlag:
        for Pid,Rec in Result.items():
            if Rec == "Running":
                Result[Pid]="TimeOut"
                os.kill(Pid,signal.SIGTERM)
    ### Just Validate all is clear
    for Pid in Result.keys():
        try:
            Status=os.waitpid(Pid,os.P_NOWAIT)
            print "Debug - After Finish PID %d still exist ..." % Status[0]
        except OSError as e:
            #print "Debug - Clean PID %d (%s)" % (pid,type(e))
            pass

    return Result

############################################
#  M A I N
############################################

Conf=ConfClass.ConfParser(**Defaults)
Conf.ReadConfig([ConfClass.ConfParser.CLI,])
FullConfig=Conf.getConfig()
print "Debug - Input Configuration:"
for CKey,CVal in FullConfig.items():
    print "%-15s : %s" %(CKey,', '.join(CVal))

if not VerifyUser('root'):
    print "Error  - This script can run only as root user"
    exit(1)

if not VerifySingleTone():
    print "Error - another instance of %s is runnig" % __name__
    exit(1)

if not Validation(FullConfig):
    print "Error - Validation failed"
    exit (1)



#InfoDir=FullConfig['new_info_dir'][-1] if 'new_info_dir' in FullConfig else "/tftpboot/INFO_FILES"
#ChassiRec={}
ChassiRec=BuildHostList(FullConfig)
#for Blade_IP in FullConfig['ip']:
#    InfoName="%s/INFO_%s" % (InfoDir,Blade_IP)
#    TmpHash=ParseInfo(InfoName)
#    if not 'chassis_ip' in TmpHash:
#        print "Warning - missing chassis_ip Parameter at INFO %s" % InfoName
#        continue
#    if not TmpHash['chassis_ip'] in ChassiRec :
#        ChassiRec[TmpHash['chassis_ip']]=ParseInfo("%s/INFO_%s" % (InfoDir,TmpHash['chassis_ip']))
#    ChassiRec[TmpHash['chassis_ip']][Blade_IP]=TmpHash
    #print "Debug  - Add %s key to Chassi %s" % (Blade_IP,TmpHash['chassis_ip'])

#print "Debug - Chassi configuration:"
#print ChassiRec


#print "\n\nStart to change Boot sequence:"
PIdList={}
SlotList=[]
for ChNode,ChRec in ChassiRec.items():
    PIdList[ChNode]=threading.Thread(target=ChassiOp,
                                     name=ChNode,
                                     args=(ChRec,)
    )
    PIdList[ChNode].start()

Flag=1
TimeOut=3000
print "DEBUG - !!!!  Start Loop at the MAIN CORE Thread !!!!!!!!!!!!!!!!"
while Flag and TimeOut:
    Flag=0
    TimeOut -= 1
    for Pid in PIdList.values():
        #Pid=threading.Thread()
        if Pid.isAlive():
            Flag += 1
            if not TimeOut % 210:
                print "Debug -- MAIN MAIN Process Detected that %s still Running" % Pid.getName()
    if Flag:
        time.sleep(1)


if not TimeOut:
    raise Exception("Error    -    Program TimeOut !!!!!")
