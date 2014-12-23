__author__ = 'dkreda'

import Ini,sys,re,platform,os,time
import subprocess,threading
import boto
import boto.ec2,boto.ec2.elb
import httplib
#import paramiko
#import pyssh



def CreateWebInstace(Host,Template):
    Runner=Executer(Template.RunMode,Host=Host,User=Template.User,SSHPath=Conf['[System]SSH'] if '[System]SSH' in Conf else None ,
                 SShKey=Template.KeyFileName)
    InstallFile='mantisbt-1.2.18.zip'
    InstallFullPath=os.sep.join((Conf['[System]Repository'],InstallFile,))
    InstallTarget="/tmp/%s" % InstallFile
    print "Debug - Copy Mantis installation files ..."
    Flag=Runner.Copy((InstallFullPath,InstallTarget))
    if Flag:
        print "\n".join(Runner.LastLog())
        Exception("Fail to copy mantis files to server")
    Flag=Runner.RunCmds(r"perl -n -e '/^[^#]*DocumentRoot/ and print $_' /etc/httpd/conf/httpd.conf")
    if Flag:
        print "\n".join(Runner.LastLog())
        Exception("Fail to parse server configuration")
    Count=0
    for Line in Runner.LastLog():
        Count += 1
        if Count <= 1: continue
        Mobj=re.search('DocumentRoot\s+[\'\"](.+?)[\'\"]',Line)
        if Mobj:
            HttpPath=Mobj.group(1)
            break
    Flag=Runner.RunCmds("bash -c 'cd %s;unzip %s;mv `ls | grep mantisbt` mantisbt'" % (HttpPath,InstallTarget))
    print "\n".join(Runner.LastLog())



class MachineTemplate(object):
    def __init__(self,AwsConnection,Conf,InstaceType='t2.micro'):
        self.__Type=InstaceType
        self.__Conn=AwsConnection
        self.__Conf=Conf
        self.__AMI=self.__getAMI()
        self.ResetZones()


    def ResetZones(self):
        #self.__Conn=boto.ec2.connect_to_region()
        self.__Zones=self.__Conn.get_all_zones()
        self.__ZCounter=0

    @property
    def Zones(self):
        return [Z.name for Z in self.__Zones]

    @property
    def Zone(self):
        self.__ZCounter = (self.__ZCounter +  1) % len(self.__Zones)
        return self.Zones[self.__ZCounter]

    @property
    def RunMode(self): return Executer.Mode_Remote

    @property
    def AwsConnection(self): return self.__Conn

    @property
    def Type(self): return self.__Type

    def __getAMI(self):
        AmiConfPath='[System]AmiName'
        DebugPath='[System]debug'
        if AmiConfPath in self.__Conf:
            return self.__Conn.get_all_images(filters={'name': self.__Conf[AmiConfPath]})[0].id
        else:
            return FindLinuxImage(self.__Conn,self.__Conf[DebugPath])

    @property
    def AMI(self):return self.__AMI

    @property
    def User(self):
        UserPath='[System]User'
        return self.__Conf[UserPath] if UserPath in self.__Conf else 'ec2-user'

    @property
    def KeyFileName(self):
        KeyName=self.__Conf['[System]KeyName']
        if platform.system() == 'Windows':
            return "%s.ppk" % KeyName
        else: ### Linux Platform
            return r'~/.ssh/id_rsa.pub'

    @property
    def Key(self): return self.__getKey()

    def __genKeyFileWin(self):
        KeyName=self.__Conf['[System]KeyName']
        FileName="%s.pem" % KeyName
        if os.path.exists(FileName):
            Cmd='"%s" %s' % (os.sep.join((self.__Conf['[System]SSH'],'puttygen.exe')),FileName)
            Count = 3
            while not os.path.exists(self.KeyFileName) and Count:
                print "Note - please save the private Key File %s.ppk" % KeyName
                print "       in %s" % os.path.abspath()
                print "       and exit from Pygen program"
                Flag=os.system(Cmd)
                if Flag:
                    raise Exception("Fatal - failed to Convert Public key using \"%s\"" % Cmd)
                ## Flag=raw_input("Please save ppk file then press Enter.")
                Count -= 1
            return os.path.exists(self.KeyFileName)
        else:
            raise Exception("Error - missing File %s can not generate ssh Public key file" % FileName)

    def __genKeyFileLinux(self):
        print "Debug - Generation of Key File for Linux not Ready Yet"
        return False

    def __getKey(self):
        ## print "Debug - Create Key ...."
        KeyName=self.__Conf['[System]KeyName']
        if os.path.exists(self.KeyFileName):
            return KeyName
        ### ppk File not exists
        if os.path.exists("%s.pem" % KeyName):
            if platform.system() == 'Windows':
                if self.__genKeyFileWin():
                    return KeyName
                else:
                    raise Exception("Error - Fail to Generate Public Key")
            elif platform.system() == 'Linux':
                if self.__genKeyFileLinux():
                    return KeyName
                else:
                    raise Exception("Error - Fail to generate Public Key file")
            else:
                raise Exception("Error - unsuported platform %s" % platform.system())
        else: ### Need to Create new Key
            self.__Conn.delete_key_pair(KeyName)
            print "Debug - Create New Key ...."
            key_pair=self.__Conn.create_key_pair(KeyName)
            if not key_pair.save('.'):
                raise Exception('Fail to save public key file %s.pem' % KeyName)
            return self.__getKey()


class VmGen(object):
    def Install(self):
        print "-- Install Process not ready yet ..."
        pass

    def Check(self):
        print "--- Check Process Not Ready yet"

    def Status(self):
        print "--- Status not Ready Yet"
        return False

    @property
    def Info(self): return (self.__Conn,self.__Temp)

    def __init__(self,Templ):
        ##Templ=MachineTemplate()
        self.__Conn=Templ.AwsConnection
        self.__Temp=Templ
        self.__Stop=False
        self.__Instance=None

    def Stop(self):
        self.__Stop=True

    @property
    def Instance(self): return self.__Instance

    @property
    def get_Inst_id_List(self):
        return [Inst.id for Inst in self.Instance] if self.__Instance else None


    def LunchMachine(self,StartScript=None,**Tags):
    ##   Todo - add placement parameter (Zone to instance definition ....
        MachineInstance=self.__Conn.run_instances(self.__Temp.AMI,instance_type=self.__Temp.Type,key_name=self.__Temp.Key,
                                          #user_data=base64.b64encode(StartScript) if StartScript else None ,
                                          placement=self.__Temp.Zone ,
                                          user_data=StartScript ,
                                          additional_info='Made automaticly by script ...')
        #print "Debug - Machine created :"
        WaitList=[]
        for Inst in MachineInstance.instances:
            print "Debug - Starting %s" % Inst.id
            Inst.start()
            WaitList.append(Inst.id)
        ### Wait Instance is up
        print "Debug - Wait boot process to finish at %s ..." % MachineInstance.instances[0].id
        ## Just wait all instances go to running mode
        TCount=0
        while len(self.__Conn.get_all_instance_status(WaitList)) < len(WaitList) and not self.__Stop:
            time.sleep(1)
            TCount += 1
        FCount=len(WaitList)
        while not self.__Stop and FCount:
            FCount=len(WaitList)
            TCount += 1
            time.sleep(1)
            #self.__Conn=boto.ec2.EC2Connection()
            for TmpStat in self.__Conn.get_all_instance_status(WaitList):
                if TmpStat.system_status.status == 'ok':
                    FCount -= 1
                elif not TCount % 30:
                    print "\t... Machine %s still booting (%d Sec)" % (TmpStat.id,TCount)
        if self.__Stop:
            print "Warning - Force stop of Boot process Machine(s)! %s" %  MachineInstance.instances
        ### Print Info status
        for TmpStat in self.__Conn.get_all_instance_status(WaitList):
            print "Info - %d sec Intaces %s Status: %s , system status: %s" % (
                TCount,TmpStat.id,TmpStat.state_name,TmpStat.system_status.status
            )
        if not self.__Stop:
            self.__Instance=[]
                #Result=[]
            for Reserved in self.__Conn.get_all_instances(WaitList):
                self.__Instance.extend(Reserved.instances)
                #Result.extend(Reserved.instances)
        return self.__Instance

class DbServer(VmGen):
    def Install(self):
        (Conn,Templ)=self.Info
        MachineList=self.LunchMachine("""#!/bin/bash
        echo DbServer > /etc/INFO""")
        #MachineList=LunchMachine(Templ,300)
        if MachineList:
            InstallSql(MachineList[0].public_dns_name,Templ)


    def Status(self):
        print "This is DataBase Statsus ..."
        return False

class WebServer(VmGen):
    def Install(self):
        (Conn,Templ)=self.Info
        MachineList=self.LunchMachine("""#!/bin/bash
        echo WebServer > /etc/INFO""")
        #MachineList=LunchMachine(Templ,300)
        if MachineList:
            CreateWebInstace(MachineList[0].public_dns_name,Templ)


class System(object):
    def Build(self):
        self.Sys={}
        TreadPool=[]
        print "Debug - Active Threadss Before Running %d" % threading.activeCount()
        for Role,topology in self.__Topology.items():
            for Count in xrange(topology[1]):
                TmpInst=topology[0](self.__Template)
                #TmpInst=VmGen()
                if Role in self.Sys:
                    self.Sys[Role].append(TmpInst)
                else:
                    self.Sys[Role]=[TmpInst,]
                #TmpInst.Install
                Th=threading.Thread(target=TmpInst.Install,name="%s-%d" % (Role,Count+1))
                Th.start()
                TreadPool.append(Th)
        print "Debug - Number of running threads After Start %d" % threading.activeCount()
        TimeOut=450
        Stop=time.time() + TimeOut
        Th.join(TimeOut)
        ## Flag=True
        while time.time() < Stop and threading.activeCount() > 1:
            #Flag=False
            for Thread in TreadPool:
                if Thread.isAlive():
                    Thread.join(1)
                    #Flag=True
                    break
        print "Debug - active threads after wait ... %d" % threading.activeCount()
        if threading.activeCount() > 1:
            for Inst in self.Sys.values():
                for RInst in Inst:
                    RInst.Stop()
            raise Exception("Timout !!!!!   Main Thread should stop all other installation process .....")
        Instances=[]
        for InstList in self.Sys['WebServer']:
            ##InstList=WebServer()
            Instances.extend(InstList.Instance)
        self.Build_LB(*Instances)
        self.ShowBalancer()


    def Build_LB(self,*InstaceList):
        print "\n\nDebug - Start Build Load Balancer ...."
        ##self.__AwsConnection=boto.ec2.connect_to_region()
        print boto.ec2.elb.regions()
        ElbConn=boto.ec2.elb.connect_to_region(self.__AwsConnection.region.name,
                                        aws_access_key_id=self.__AwsConnection.access_key,
                                        aws_secret_access_key=self.__AwsConnection.aws_secret_access_key)
        #ElbConn=boto.ec2.elb.ELBConnection(self.__AwsConnection.access_key,
        #                                      self.__AwsConnection.aws_secret_access_key,
        #                                      region=self.__AwsConnection.region )
        WebPort=int(self.__Conf['[System]IntPort']) if '[System]IntPort' in self.__Conf else 80
        LBPort= int(self.__Conf['[System]ExtPort']) if '[System]ExtPort' in self.__Conf else 80
        ## Build subnet List
        print "Debug - Instance List:"
        print InstaceList
        SubNet=[Inst.subnet_id for Inst in InstaceList]
        print "Debug - Subnets:"
        print SubNet
        try:
            self.__Elb=ElbConn.create_load_balancer("MantisServic",None,[(LBPort,WebPort,'HTTP',),],SubNet)
        except:
            print "Fail to create ELB:"
            print sys.exc_info()
            print ElbConn.get_all_load_balancers()
            #print "available zones:"
            return
        #AccesService=boto.ec2.elb.loadbalancer.LoadBalancer()
        #self.__Elb=boto.ec2.elb.LoadBalancer()
        self.__Elb.register_instances([Inst.id for Inst in InstaceList])
            #create_load_balancer_listeners("MantisService",)
        hcParams={ 'target' : 'TCP:%s' % WebPort }
        if '[System]Health_Check_Interval' in self.__Conf:
            hcParams['interval']=int(self.__Conf['[System]Health_Check_Interval'])
        HealthChk=boto.ec2.elb.HealthCheck(**hcParams)
        self.__Elb.configure_health_check(HealthChk)

    def __ReadSys(self):
        self.Sys={}
        ## get Only instances that are in running state
        for InstStae in self.__AwsConnection.get_all_instance_status():
            if InstStae.system_status.status == 'ok':
                RunningList.append(InstStae.id)
                #print "Debug Instance %s - Status %s" % (InstStae.id,InstStae.state_name)
            else:
                print "Warning - Instance %s system status is %s" % (InstStae.id,InstStae.system_status.status)


    def Monitor(self):
        RunningList=[]
        for InstStae in self.__AwsConnection.get_all_instance_status():
            if InstStae.system_status.status == 'ok':
                RunningList.append(InstStae.id)
                #print "Debug Instance %s - Status %s" % (InstStae.id,InstStae.state_name)
            else:
                print "Warning - Instance %s system status is %s" % (InstStae.id,InstStae.system_status.status)
        if len(RunningList):
            SubNets=[]
            for Inst in self.__AwsConnection.get_only_instances(RunningList):
                Runner=Executer(self.__Template.RunMode,Inst.ip_address,self.__Template.User,
                                SSHPath=Conf['[System]SSH'] if '[System]SSH' in Conf else None ,
                                SShKey=self.__Template.KeyFileName )
                Runner.RunCmds('cat /etc/INFO') #'cat /var/lib/cloud/instance/user-data.txt',
                Mtch=re.search('(\S+)',Runner.LastLog()[-1])
                Role=Mtch.group(1) if Mtch else Runner.LastLog()[-1]
                print "\nInstance - %s Role %s (%s)" % (Inst.id,Role if Role in self.__Topology else "UnKnown",Role)
                print "\tPublic IP %s" % Inst.ip_address
                print "\tPublic DNs %s" % Inst.public_dns_name
                print "\tPrivate IP %s" % Inst.private_ip_address
                print "\tZone      %s"  % Inst.placement
                print "\tStatus    %s" % Inst.state
                print "\tVPC       %s" % Inst.vpc_id
                print "\tSubNet    %s" % Inst.subnet_id
                SubNets.append(Inst.subnet_id)
                print "< ----  End Record ---->"
        else:
            print "- No Running Instances found ..."

        print "ELB Section ....."

        print self.__AwsConnection.region.name
        ElbConn=boto.ec2.elb.connect_to_region(self.__AwsConnection.region.name,
                                        aws_access_key_id=self.__AwsConnection.access_key,
                                        aws_secret_access_key=self.__AwsConnection.aws_secret_access_key)
        print "Debug - Connection Info"
        #print ElbConn
        #ttt=ElbConn.get_all_load_balancers()
        #print "Debug - get all balancers pass"
        #print ttt
        print ElbConn.get_all_load_balancers()
        WebPort=int(self.__Conf['[System]IntPort']) if '[System]IntPort' in self.__Conf else 80
        LBPort= int(self.__Conf['[System]ExtPort']) if '[System]ExtPort' in self.__Conf else 80
        #self.__Elb=ElbConn.create_load_balancer("MantisServic",None,[(LBPort,WebPort,'HTTP',),],SubNets)
        #print self.__Elb
        for Elb in ElbConn.get_all_load_balancers():
            #Elb=ElbConn.create_load_balancer()
            #Elb=boto.ec2.elb.LoadBalancer()
            print "Balncer %s Info:" % Elb.name
            print "\tInstances: %s" % Elb.instances
            print "\tZones:     %s" % Elb.availability_zones
            print "\tConnect URL:%s" % Elb.dns_name
            print "\tListieners:%s"  % Elb.listeners
            print "<======= END Balancer Record ============>"





    def Clear(self):
        RunningList=[Inst.id for Inst in self.__AwsConnection.get_all_instance_status()]
        Retry=5
        while len(RunningList) and Retry:
            StopedList=self.__AwsConnection.terminate_instances(RunningList)
            for Inst in StopedList:
                RunningList.remove(Inst.id)
            if len(RunningList):
                time.sleep(3)
            Retry -= 1
        if len(RunningList):
            print "Error - Fail to terminate the following Instances:"
            print "\t%s" % "\n\t".join(RunningList)
            raise Exception("Faile to terminate some instances")
        ### Verify all Instances Terminated
        print "Info - all Running Instances stoped. Verifying Termination"
        for Reserv in self.__AwsConnection.get_all_instances():
            for Inst in Reserv.instances:
                if not Inst.state == 'terminated':
                    print "Warning - Instance %s have not finish terminated !" % Inst.id
                    Inst.terminate()
        PrintInstance(self.__AwsConnection)
        print "Delete Balancer Resources ..."
        ElbConn=boto.ec2.elb.connect_to_region(self.__AwsConnection.region.name,
                                        aws_access_key_id=self.__AwsConnection.access_key,
                                        aws_secret_access_key=self.__AwsConnection.aws_secret_access_key)
        #ElbConn=boto.ec2.elb.ELBConnection()
        for Elb in ElbConn.get_all_load_balancers():
            ElbConn.delete_load_balancer(Elb.name)

    __Topology= { 'DbServer'  : [DbServer,1] ,
                  'WebServer' : [WebServer,2] ,
                  'Management' : [VmGen,1]}

    def CheckRegion(self,RegName):
        ## Checkk Avaolable EC2 Regions
        try:
            RegInfo=boto.ec2.get_region(RegName,aws_access_key_id=self.__Conf['[System]aws_access_key_id'],
                                        aws_secret_access_key=self.__Conf['[System]aws_secret_access_key'])
            for RegInfo in boto.ec2.elb.regions():
                if RegName == RegInfo.name:
                    return True
            print "Error - There is no available Balancer recource at region %s" % RegName
            return False
        except:
            print sys.exc_info()
            Avilable=[Reg.name for Reg in boto.ec2.regions(aws_access_key_id=self.__Conf['[System]aws_access_key_id'],
                                        aws_secret_access_key=self.__Conf['[System]aws_secret_access_key'])]
            print "Error - Region %s is not Available. List of available Regions:\n%s" % (RegName,"\n".join(Avilable))
            return False

    def __init__(self,Conf):
        self.__Conf=Conf
        Region=Conf['[System]region']
        if not self.CheckRegion(Region):
            raise Exception('Unavailable Region: "%s"' % Region)
        self.__AwsConnection=boto.ec2.connect_to_region(Region,
                                        aws_access_key_id=Conf['[System]aws_access_key_id'],
                                        aws_secret_access_key=Conf['[System]aws_secret_access_key'])
        self.__Template=MachineTemplate(self.__AwsConnection,self.__Conf)

    def ShowBalancer(self):
        ELb=getattr(self,'__Elb')
        if ELb:
            print "Balancer %s Configuration: ...." % ELb.name
            ELb=self.__Elb=boto.ec2.elb.LoadBalancer()
            print ELb.created_time
            print "Balancer Acces Url: %s" % ELb.dns_name
            print ELb.instances
            print ELb.health_check
            print ELb.listeners
            print ELb.policies
            print ELb.scheme
            print ELb.vpc_id
            print "==============================="





#def LunchMachine(AwsConn,Template):
def LunchMachine(Template,TimeOut=300,StartScript=None,**Tags):
    #AwsConn=boto.ec2.connect_to_region()
    ##Template=MacineTempl()
    #Template=MachineTemplate()
    AwsConn=Template.AwsConnection
    ##   Todo - add placement parameter (Zone to instance definition ....
    MachineInstance=AwsConn.run_instances(Template.AMI,instance_type=Template.Type,key_name=Template.Key,
                                          #user_data=base64.b64encode(StartScript) if StartScript else None ,
                                          user_data=StartScript ,
                                          additional_info='Made automaticly by script ...')
    print "Debug - Machine created :"
    WaitList=[]
    for Inst in MachineInstance.instances:
        print "Debug - Starting %s" % Inst.id
        Inst.start()
        WaitList.append(Inst.id)
    ### Wait Instance is up
    print "Debug - Wait boot process to finish ..."
    ## Just wait all instances go to running mode
    TimeCount=TimeOut
    while len(AwsConn.get_all_instance_status(WaitList)) < len(WaitList) and TimeCount:
        time.sleep(1)
        TimeCount -= 1
    ## Instances running wait boot process terminate
    if TimeCount:
        Flag=True
        while Flag and TimeCount > 0:
            Gap=TimeCount % 3 if TimeCount % 3 else 3
            time.sleep(Gap)
            TimeCount -= Gap
            Flag=len(WaitList)
            for TmpStat in AwsConn.get_all_instance_status(WaitList):
                if re.search('ok',TmpStat.system_status.status):
                    Flag -= 1
                elif not TimeCount % 30:
                    print "\t... Machine %s still booting (%d Sec)" % (TmpStat.id,TimeOut-TimeCount)
        if not Flag:
            ## All Instancess Finished to boot
            Result=[]
            for Reserved in AwsConn.get_all_instances(WaitList):
                Result.extend(Reserved.instances)
            print "Debug - system boot Took %d Sec" % (TimeOut-TimeCount)
            return Result
        else:
            print "Error - TimeOut waiting Boot Finish:"
            for TmpStat in AwsConn.get_all_instance_status(WaitList):
                print "\t- %s Machine Status: %s , System Status: %s" % (TmpStat.id,TmpStat.state_name,
                                            TmpStat.system_status.status)
                print "\t\t > %s" % TmpStat.system_status.details
            raise Exception("TimeOut - waiting too mach for boot process")
    else:
        print "Error - TimeOut waiting Boot Finish:"
        for TmpStat in AwsConn.get_all_instance_status(WaitList):
            print "\t- %s Machine Status: %s , System Status: %s" % (TmpStat.id,TmpStat.state_name,
                                            TmpStat.system_status.status)
            print "\t\t > %s" % TmpStat.system_status.details
        raise Exception("TimeOut - waiting too mach for boot process")


def Clear(AwsConn):
    RunningList=[Inst.id for Inst in AwsConn.get_all_instance_status()]
    Count=5
    while len(RunningList) and Count:
        StopedList=AwsConn.terminate_instances(RunningList)
        for Inst in StopedList:
            RunningList.remove(Inst.id)
        if len(RunningList):
            time.sleep(3)
        Count -= 1
    if len(RunningList):
        print "Error - Fail to terminate the following Instances:"
        print "\t%s" % "\n\t".join(RunningList)
        raise Exception("Faile to terminate some instances")
    ### Verify all Instances Terminated
    for Reserv in AwsConn.get_all_instances():
        for Inst in Reserv.instances:
            if not Inst.state == 'terminated':
                print "Warning - Instance %s have not terminated !" % Inst.id
                Inst.terminate()

    PrintInstance(AwsConn)




#def InstallSql(Host,Conf,KeyFile):
def InstallSql(Host,Template):
    VerMap={ "Linux/el6" : 'mysql-community-release-el6-5.noarch.rpm' ,
             "Windows/7" : 'mysql-community-release-el6-5.noarch.rpm' }
    ## Verify which Platform to install
    RpmFile=None
    for OsPlatfrom,RpmName in VerMap.items():
        OsChk=OsPlatfrom.split('/')
        if not platform.system() == OsChk[0]:
            print "Debug - %s Not Match to %s" % (OsChk[0],platform.system())
            continue
        if re.search(OsChk[1],platform.release()):
            RpmFile=RpmName
            print "Debug - Seting Rpm File !"
            break
        print "Debug - %s ... %s" % (OsChk[1],platform.release())
    if not RpmFile:
        raise Exception("Error - No matching SQL installation kit for Host %s" % Host)
    #Template=MachineTemplate()
    Tmp=Executer(Template.RunMode,Host=Host,User=Template.User,SSHPath=Conf['[System]SSH'] if '[System]SSH' in Conf else None ,
                 SShKey=Template.KeyFileName)
    #Tmp=Executer(Executer.Mode_Remote,Host=Host,User='ec2-user',SSHPath=Conf['[System]SSH'] if '[System]SSH' in Conf else None ,
    #             SShKey=KeyFile)
    ## Copy File RpmFile
    RpmFullPath=os.sep.join((Conf['[System]Repository'],RpmFile,))
    RpmTarget="/tmp/%s" % RpmFile
    Flag=Tmp.Copy((RpmFullPath,RpmTarget),
                  (os.sep.join((Conf['[System]Repository'],'UserDef.sql')),"/tmp/"),
                  (os.sep.join((Conf['[System]Repository'],'FixDbGratnts.sh')),"/tmp/"))
    if Flag:
        print "Error - Copy Failed"
        print "\n".join(Tmp.LastLog())
    ## Run rpm -iv RpmFile

    Flag=Tmp.RunCmds("rpm -iv %s" % RpmTarget,
                     "yum install mysql-community-server",
                     r'chmod +x /tmp/FixDbGratnts.sh || echo Fail to Change Mode' ,
                     r'sleep 10 && echo Finish to sleep start Execut' ,
                     r'cp -p /tmp/FixDbGratnts.sh /tmp/FixDbGratnts.sh.tmp' ,
                     r'cat -v /tmp/FixDbGratnts.sh.tmp | cut -f 1 -d^  > /tmp/FixDbGratnts.sh' ,
                     #r'echo Debug - After dos2unix' ,
                     #'cat /tmp/FixDbGratnts.sh' ,
                     "/tmp/FixDbGratnts.sh" ,
                     #'echo About To Run sql file ....' ,
                     "mysql -uroot -proot < /tmp/UserDef.sql" ,
                     "service mysqld status || echo FATAL Failed to start")
    print "Debug - Last Run %d" % Flag
    print "\n".join(Tmp.LastLog())
    Count=0
    for Line in Tmp.LastLog():
        if re.search('FATAL Failed',Line) and Count:
            Flag += Count
            print "Error Find at Line %d" % (Count + 1)
            break
        Count += 1
    if Flag :
        print "\n\nError - Last Command Failed"
        print "\n".join(Tmp.LastLog())
    ## Run sudo yum install mysql-community-server
    ## for more details: http://dev.mysql.com/doc/mysql-yum-repo-quick-guide/en/

class Executer(object):
    Mode_Login='Expect'
    Mode_Remote='SSH'
    Mode_Local='Local'
    __CmdMap= { 'Windows' : ['plink.exe','pscp.exe',] ,
                'Linux'   : ['ssh','scp',]}


    def __init__(self,Mode,Host=None,User=None,Password=None,Prompt=">",SSHPath=None,SShKey=None):
        self.__LastLog=[]
        self.__Host=Host
        self.__User=User
        self.__Password=Password
        self.__Prompt=Prompt
        Func= { self.Mode_Login: self.__RunExpect ,
                self.Mode_Remote: self.__RunSSH ,
                self.Mode_Local: self.__Excute }
        if Mode in Func:
           self.__Func=Func[Mode]
           if Mode == self.Mode_Login:
                self.ExpectPath=subprocess.Popen(['which', 'expect'], stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()[0]
                self.ExpectPath=self.ExpectPath.rstrip(os.linesep)
           elif Mode == self.Mode_Remote:
               ParamList=platform.system()
               if ParamList in self.__CmdMap:
                   ParamList=self.__CmdMap[ParamList]
                   self.__SSH="/".join((SSHPath if SSHPath else self.Which(ParamList[0]),ParamList[0]))
                   self.__SCpCmd=os.sep.join((SSHPath if SSHPath else self.Which(ParamList[1]),ParamList[1]))
                   if platform.system() == 'Windows':
                       self.__SCpCmd='echo y | "%s"' % self.__SCpCmd
                       self.__SSH='echo y | "%s"' % self.__SSH
                   self.__SSHParams='-i %s' % SShKey
        else:
            raise Exception("Error - Unknown Mode Operation \"%s\"\n\tSuported Modes are: %s" % (Mode,",".join(Func.keys())))


    def RunCmds(self,*CmdsList):
        return self.__Func(CmdsList)

    def __Excute(self,Cmds):
        self.__LastLog=[]
        Counter=1
        Result=0
        for SingleCmd in Cmds:
            Proc=subprocess.Popen(SingleCmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,shell=True)
            (sout,serr)=Proc.communicate()
            Proc.wait()
            if Proc.returncode:
                self.__LastLog.append("Command %d Failed (%s):" % (Counter,SingleCmd))
                self.__LastLog.append("\tError Log:")
                self.__LastLog.extend(["\t%s" % Line for Line in str(serr).split(os.linesep)])
                self.__LastLog.append("\t- Standard Out:")
                self.__LastLog.extend(["\t%s" % Line for Line in str(sout).split(os.linesep)])
            else:
                self.__LastLog.append("Command %d pass (%s):" % (Counter,SingleCmd))
                self.__LastLog.extend(["\t%s" % Line for Line in str(sout).split(os.linesep)])
            Counter += 1
            Result += Proc.returncode
            #print "Debug - Going to return %s" % str(Result)
        return Result

    def LastLog(self):
        return self.__LastLog

    def __RunExpect(self,Cmds):
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

    def __RunSSH(self,Cmds):
        SShCmds=[r'sudo %s' % Line for Line in Cmds]
        Cmd='%s %s %s@%s "%s"' % (self.__SSH,self.__SSHParams,self.__User,self.__Host,";".join(SShCmds))
        print "Debug - About to run: %s" % Cmd
        return self.__Excute([Cmd])

    def Copy(self,*SorceTarget):
        return self.__Scp(SorceTarget)

    def __Scp(self,FileList):
        Cmds=[r'%s %s %s %s@%s:%s' % (self.__SCpCmd,self.__SSHParams,File[0],self.__User,self.__Host,File[1]) for File in FileList]
        print "Debug About to run:\n\t%s" % "\n\t".join(Cmds)
        return self.__Excute(Cmds)

    def __SearchLinux(self,File):
        return

    def Which(self,File):
        PNam='PATH' if platform.system()=='Windows' else 'path'
        if PNam in os.environ:
            for Folder in os.environ[PNam].split(os.pathsep):
                if os.path.isfile(os.sep.join(Folder,File)):
                    return Folder
        return '.'


def PrintInstance(AwsConn):
    AttributeList=['id','owner_id','groups','instances']
    AtList=['ami_launch_index', 'architecture', 'groups','instance_type','dns_name', 'kernel', 'key_name','state',
        'subnet_id','vpc_id','private_ip_address','ip_address','platform','state_reason','interfaces',
        'instance_profile','public_dns_name' ]
    for EcInstance in AwsConn.get_all_instances():
        for Attr in AttributeList:
            print "%-25s - %s" % (Attr,getattr(EcInstance,Attr,"Not Exists !"))
        if re.search(r'Reserv',str(EcInstance),re.IGNORECASE):
            print "%s is Reserved Instance" % str(EcInstance)
            NameList=[]
            for Ins in EcInstance.instances:
                #print dir(Ins)
                MOb=re.search(r':(\S+)',str(Ins))
                if MOb:
                    NameList.append(MOb.group(1))

                if Ins.state == 'running':
                    #print 'Warning - Instance Machine %s in state "%s"' % (Ins.id,Ins.state)
                    print "Info - Instance %s is running" % Ins.id
                    print '\tInstatnce Info:'
                    for AName in AtList:
                        print "%s  - %s" % (AName,getattr(Ins,AName,"Not Exists !"))
                else:
                    print 'Warning - Instance Machine %s in state "%s"' % (Ins.id,Ins.state)

            print NameList
            print "<<======>>\n\n\n"
        else:
            print "> virtualization_type %s" % EcInstance.virtualization_type
            print "> Instance type %s" % EcInstance.instance_type

def FindLinuxImage(AwsCon,Debug=False):
    Count=0
    ImageList=[]
    if Debug:print "List of available Images:"
    for AMiIter in AwsCon.get_all_images(filters={'image-type' : 'machine' , 'virtualization-type' : 'hvm' ,
                                               'state' : 'available' , 'architecture' : 'x86_64' }):
        Count +=1
        if not AMiIter.name:
            continue
        if re.search(r'Linux',AMiIter.name,re.IGNORECASE) and re.search('Redhat',AMiIter.name,re.IGNORECASE):
            if not Debug:
                return AMiIter
            ImageList.append(AMiIter)
            print AMiIter
            print "> AMI Name:      %s" % AMiIter.name
            print "> AMI  Platform: %s" % AMiIter.platform
            print "> type         : %s" % AMiIter.type
            print "> Vitualization Type : %s" % AMiIter.virtualization_type
            print "> architecture:  %s" % AMiIter.architecture
            print "> is public:     %s" % AMiIter.is_public
            print "> hypervisor:    %s" % AMiIter.hypervisor
            print "> state          %s" % AMiIter.state
            print "> tags           %s" % AMiIter.tags
        ##RedCount += 1
        #ImageList[AMiIter.id]=AMiIter.name
    print "\n\nprint Toal Images %d\nMatch Images %d\n\n" % (Count,len(ImageList))
    return ImageList[0]

def Build(AwsConn,Conf):
    ## Templ=MacineTempl('WebServer',[],AMIid=BaseAMI.id,KeyName=KeyName)
    Templ=MachineTemplate(AwsConn,Conf)
    ## Create Web instances
    WebMa=LunchMachine(Templ)
    DbMa=LunchMachine(Templ)
    print "\n\n\n<<====   After Creation !!!!  =====>>>>\n"
    PrintInstance(AwsConn)
    AttrList=['id','state','public_dns_name','launch_time','placement','virtualization_type']
    for Attr in AttrList:
        print "%-15s: %s" % (Attr,getattr(WebMa[0],Attr,"No Attribute !"))
    print "<< ---- E N D ---- >>\n\n"

    #InstallSql(WebMa[0].public_dns_name,Conf,"./%s.pem" % KeyName)
    InstallSql(DbMa[0].public_dns_name,Templ)
    CreateWebInstace(WebMa[0].public_dns_name,Templ)
    #PrintInstance(AwsConn)
    print "\n\nFinish to create Machines:"
    print "DataBase:   ssh - %s" % DbMa[0].public_dns_name
    print "Web Server: ssh - %s" % WebMa[0].public_dns_name
    print "Install Mantis: http://%s/mantisbt/admin/install.php" % WebMa[0].public_dns_name
    print "tcpdump ...."

def CheckInstall(AwsConn,Conf):
    ##AwsConn=boto.ec2.connect_to_region()
    ### Go Over all instances
    for Inst in AwsConn.get_all_instance_status():
        if not Inst.system_status.status == 'ok':
            continue
        Machine=AwsConn.get_all_instances([Inst.id])[0].instances[0]
        print "Check - Configuration of Instance %s" % Machine.id
        IntUrl="http://%s/mantisbt/admin/install.php" % Machine.public_dns_name
        print "Debug - Check connection to %s" % IntUrl
        HttpConn=httplib.HTTPConnection(Machine.public_dns_name,timeout=5)
        Req=HttpConn.request("GET",IntUrl)
        print "Debug - Request Retun :"
        print Req
        Res=HttpConn.getresponse()
        if Res and Res.status == 200:
            print "Debug Return Responce 200 from %s" % Machine.id
            print "Headers - "
            print Res.msg
            print "-------"
            print Res.read()
            print "-------"
        else:
            print "Info Intance %s is not Mantis" % Machine.id

###############################################################################
#
#  M A I N
#
###############################################################################


ConfFileName=sys.argv[1] if len(sys.argv) > 1 else "config.txt"
Conf=Ini.INIFile(ConfFileName)

###############################################################################
#
#  Builder
#
###############################################################################
## Create Balancer

MainSys=System(Conf)
print "Debug ----- Terminate initialization"

if len(sys.argv) > 2:
    if sys.argv[2] == 'Cleaner':
        MainSys.Clear()
        #Clear(AwsConn)
    elif sys.argv[2] == 'Builder':
        MainSys.Build()
        #Build(AwsConn,Conf)
    elif sys.argv[2] == 'Monitor':
        print "Test - Not Ready yet ..."
        MainSys.Monitor()
        #CheckInstall(AwsConn,Conf)
    else:
        print "Unsuported command %s" % sys.argv[2]
else:
    print "missing command ...."

exit()

Region=Conf['[System]region']
JustName=re.compile('Info:(.+)')
RegNames=[]
for Reg in boto.ec2.elb.regions():
    Chk=JustName.search(str(Reg))
    if Chk :
         RegNames.append(Chk.group(1))
if not Region in RegNames:
    raise Exception("there is no Balancer resources at region %s. available regoines: %s" % \
                        (Region,"\n\t".join(RegNames)))


hcParams={}
if '[System]IntPort' in Conf:
    hcParams['target']='TCP:%s' % Conf['[System]IntPort']
if '[System]Health_Check_Interval' in Conf:
    hcParams['interval']=int(Conf['[System]Health_Check_Interval'])

HealthChk=boto.ec2.elb.HealthCheck(**hcParams)

print "Debug - Check HealthCheck :"
print hcParams

AwsConn=boto.ec2.connect_to_region(Region,aws_access_key_id=Conf['[System]aws_access_key_id'],
                                        aws_secret_access_key=Conf['[System]aws_secret_access_key'])

##print "Debug - Connection Finished"
##print AwsConn
if len(sys.argv) > 2:
    if sys.argv[2] == 'Cleaner':
        Clear(AwsConn)
    elif sys.argv[2] == 'Builder':
        Build(AwsConn,Conf)
    elif sys.argv[2] == 'Test':
        CheckInstall(AwsConn,Conf)
    else:
        print "Unsuported command %s" % sys.argv[2]
else:
    print "missing command ...."

##Stam=pyssh.test()

## Create DataBase

## Create Managemnt

### Start intsllations on instances ...
