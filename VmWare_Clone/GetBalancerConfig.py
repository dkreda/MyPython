#!/usr/bin/env python

import sys,re,subprocess
import datetime,time
import os
import zipfile
import xml.etree.ElementTree as LibXML


class ParseError(Exception):
    pass


G_CLIArgs={'LogFile' : '-' ,
           'ADCIP'   : '10.140.8.171' ,
           'ADCLogin' : 'root/root' }
G_FileHandle=[]

def WrLog(*Lines):
    if not len(G_FileHandle):
        #print "Debug - First time in log ...."
        for FileName in CmdParams.GetCLIParam("LogFile").split(","):
            #print "Debug- open file handle for %s" % FileName
            if FileName == "-":
                G_FileHandle.append(sys.stdout)
            else:
                G_FileHandle.append(open(FileName,"a"))
        MyName=__file__
        if len(MyName) > 70:
            MyName= "..." + MyName[-65:]
        PrnTitle(re.sub("\.\d+","","%s" % datetime.datetime.now()),
                 "Run: %s" % MyName)
    for Line in Lines:
        for f in G_FileHandle:
            f.write( str(Line) + "\n")
        
def PrnTitle(*Lines):
    Fram_Ch='*'
    FramSize=80
    Frame="{0:{fill}<{Size}s}".format(Fram_Ch,fill=Fram_Ch,Size=FramSize - 2 )
    BigList=[Frame]
    BigList.extend(Lines)
    BigList.extend([Frame])
    for Iter in BigList:
        WrLog("{1:s}{0: ^{Size}s}{1:s}".format(Iter,Fram_Ch,Size=FramSize - 2 ))

def RunCmds(*Cmds):
    Result=0
    for ExecCmd in Cmds:
        WrLog("Execute: %s" % ExecCmd)
        try:
            Proc=subprocess.Popen(ExecCmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,shell=True)
            (sout,serr)=Proc.communicate()
            ##print "Debug - type of sout is %s" % type(sout)
            Proc.wait()
            WrLog( *[ "\t" + LineStr for LineStr in str(sout,"ASCII").split(os.linesep) ] )
            if ( Proc.returncode ) :
                WrLog("- Error Last Command \"%s\" Finish with exit code %d" % (ExecCmd,Proc.returncode))
            Result += Proc.returncode
        except Exception as e:
            WrLog(type(e),"Error - Executing ...(%s)" % ExecCmd,"Message:",e.message)
            Result += 1
    return Result
    
class CLIParams(object):
    Pattern=re.compile('-(\S+)')
    def ParseCLI(self,InputList=sys.argv):
        ParamIndx=None
        for InWord in InputList:
            if InWord == __file__ :
                continue
            Parse=CLIParams.Pattern.match(InWord)
            if Parse is not None:
                ParamIndx=Parse.group(1)
                self.ParaList[ParamIndx]=None
                next
            else:
                if self.ParaList[ParamIndx] is None:
                    self.ParaList[ParamIndx]=InWord
                else:
                    self.ParaList[ParamIndx] += ",%s" % InWord
    
    def __init__(self,InputList=sys.argv,**Defaults):
        self.ParaList={}
        self.ParseCLI(InputList)
        for Iter in Defaults:
            if Iter not in self.ParaList:
                self.ParaList[Iter]=Defaults[Iter]
        
    def GetCLIParam(self,Name):
        return self.ParaList[Name]
    
    def Defined(self,Name):
        return self.ParaList.has_key(Name)
    
    def GetAllParams(self):
        return self.ParaList
    
class _AdcParser(object):
    def __init__(self,PoolIPs,Lines=None):
        self.PoolIPs=PoolIPs
        self.PoolListByIP={}        ## Dict = IP : (List of PoolNames)
        self.PoolListByName={}      ## Dict = PoolName : (List of IPs)
        self.RuleList={}            ## Dict = RuleName : (List of PoolName ) (only irulrs that redirect traffic to relevant pool)
        self.VirtaulServer={}       ## Dict = VsName :  {PoolList : ... iRules: ... Vlans : ....}
        self.Clients={}             ## Dict = DatGrp : PoolName
        if Lines:
            self.Parse(Lines)
        else:
            self.content=Lines
            
    def BalancerConfig(self):
        # Return Blancer Record:
        # { Client : { ClientName: {set of pools} } ,
        #   PoolList: {set of pools}
        #   VsList: {  VS Name: {set of VLANS} }
        #                         }
        Result={}
        for CName,Pools in self.Clients.items():
            ## WrLog("DEBUG ------  Parssing Results of Client: %s" % CName)
            for PoolName in Pools:
                Tmp=set(self.PoolListByName[PoolName])
                if not 'Client' in Result:
                    Result['Client']={CName : Tmp }
                if CName in Result['Client']:
                    Result['Client'][CName].union(Tmp)# set(Tmp) #| set(self.PoolListByName[PoolName])
                else:
                    Result['Client'][CName] = Tmp
        Result['PoolList']=self.PoolListByName.keys()
        for VsName,VsContent in self.VirtaulServer.items():
            if VsContent.keys().__len__():
                Tmp=set(VsContent['Vlans'])
                if Result.has_key('VsList'):
                    Result['VsList'][VsName]=Tmp
                else:
                    Result['VsList']={ VsName : Tmp }
        return Result
    
    def Parse(self,Lines):
        self.content=Lines
        self.CurrentName=None
        print "\nDebug --- in Base (interface Parser ....)"
            
    
class F5Parser(_AdcParser):
    NewRecPattern=re.compile(r'ltm\s+(\S+).+?(\S+)\s+\{')
    def __init__(self,PoolIPs,Lines=None):
        super(F5Parser,self).__init__(PoolIPs,Lines)
        ## self.Parse(Lines)
        
    def PoolParser(self,LineNo):
        AddrMatch=re.search("address\s+(%s)" % '|'.join(self.PoolIPs),self.content[LineNo])
        if AddrMatch:
            if self.PoolListByIP.has_key(AddrMatch.group(1)):
                self.PoolListByIP[AddrMatch.group(1)].append(self.CurrentName)
            else:
                self.PoolListByIP[AddrMatch.group(1)]=[self.CurrentName,]
            if self.PoolListByName.has_key(self.CurrentName):
                self.PoolListByName[self.CurrentName].append(AddrMatch.group(1))
            else:
                self.PoolListByName[self.CurrentName]=[AddrMatch.group(1),]
            # WrLog("Debug - %s added to Pool List ....." % self.CurrentName )
        return 1
    
    def VsParser(self,LineNo):
        Match=re.search(r"pool\s+(\S+)",self.content[LineNo])
        Count=0
        if Match and self.PoolListByName.has_key(Match.group(1)):
            if not self.CurrentName in self.VirtaulServer:
                self.VirtaulServer[self.CurrentName]={}
            if not self.VirtaulServer[self.CurrentName].has_key('PoolList'):
                self.VirtaulServer[self.CurrentName]['PoolList']=[Match.group(1),]
            else:
                self.VirtaulServer[self.CurrentName]['PoolList'].append(Match.group(1))
            Count += 1
        Match=re.search('rules.+\{',self.content[LineNo])
        if Match:
            if not self.CurrentName in self.VirtaulServer:
                self.VirtaulServer[self.CurrentName]={}
            while not re.search(r'\}',self.content[LineNo+Count]):
                Match=re.search(r'(\S+)',self.content[LineNo+Count])
                Count += 1
                if not Match:
                    continue
                if self.RuleList.has_key(Match.group(1)):
                    if self.VirtaulServer[self.CurrentName].has_key('iRules'):
                        self.VirtaulServer[self.CurrentName]['iRules'].append(Match.group(1))
                    else:
                        self.VirtaulServer[self.CurrentName]['iRules']=[Match.group(1),]
        if LineNo + Count < self.content.__len__():
            Match=re.search(r'vlans.+\{',self.content[LineNo + Count ])
            Count += 1
        else:
            Match=None
            WrLog("Warning - No Vlans found for %s" % self.CurrentName)
        if Match and self.VirtaulServer.has_key(self.CurrentName) and self.VirtaulServer[self.CurrentName].keys().__len__():
            # print "Debug - Parssing Vlans of %s ...." % self.CurrentName
            while not re.search(r'\}',self.content[LineNo+Count]):
                Match=re.search(r'(\S+)',self.content[LineNo+Count])
                Count += 1
                if not Match: continue
                if self.VirtaulServer[self.CurrentName].has_key('Vlans'):
                    self.VirtaulServer[self.CurrentName]['Vlans'].append(Match.group(1))
                else:
                    self.VirtaulServer[self.CurrentName]['Vlans']=[Match.group(1),]
        return Count
    
    def RuleParser(self,LineNo):
        if re.match(r'\}',self.content[LineNo]):
            return 1
        Pattern=re.compile("\s(%s)[\s\]].+?equals\s+(\S+?)[\s\]\}\)]" % '|'.join(self.PoolListByName.keys()))
        Count=0
        #WrLog("Debug  ---- (%d) Pattern : %s" % (LineNo,Pattern.pattern))
        while ( LineNo+Count + 1 <  self.content.__len__() and not re.match(r'(else|ltm)\s',self.content[LineNo+Count]) ):
            Match=Pattern.search(self.content[LineNo+Count])
            if Match:
                ## WrLog("Debug - Matcching line at Rule: %s" % self.content[LineNo+Count],Match.groups())
                if self.Clients.has_key(Match.group(2)):
                    self.Clients[Match.group(2)].append(Match.group(1))
                else:
                    self.Clients[Match.group(2)]=[Match.group(1),]
                self.RuleList[self.CurrentName]=Match.group(1)
                # WrLog("Debug  --  Add Rule to rule list : %s" % self.CurrentName)
            Count += 1
        if re.match('ltm',self.content[LineNo+Count]):
            Count -= 1
        if CmdParams.Defined('D'):
            WrLog("Debug - Rule %s ends at line %d (%s)" % (self.CurrentName,LineNo+Count,self.content[LineNo+Count]))
        return Count + 1
    
    def DataGrp(self,LineNo):
        return 1
    
    ParseMap= { 'pool'      : PoolParser ,
                'virtual'   : VsParser ,
                'data-group' : DataGrp ,
                'rule'      : RuleParser  }
    
    def Parse(self,Lines):
        self.content=Lines
        self.CurrentName=None
        print "\n\nDebug - in F5 Parser Function\n"
        Iter=0;
        PType=None
        LastType=None
        while Iter<Lines.__len__():
            LineType=self.NewRecPattern.search(self.content[Iter])
            if LineType:
                PType=LineType.group(1)
                self.CurrentName=LineType.group(2)
                Iter += 1
                if LastType != PType and CmdParams.Defined('D'):
                    WrLog("Debug - Line %d Change Table type to %s" % (Iter,PType) )
                LastType=PType
                continue
            elif not PType:
                Iter += 1
                continue
            ## WrLog("Debug  - Line No is %d > %s" % (Iter,Lines[Iter]))
            Iter += self.ParseMap[PType](self,Iter)
        if not self.CurrentName:
            WrLog("Error - Fail to parse Input ADC Config")
            raise Exception
        if not self.PoolListByIP.keys().__len__():
            WrLog("Warning - No Relevant pools found for IPs: %s" % ','.join(self.PoolIPs))
                
class A10Parser(_AdcParser):
    
    def __init__(self,PoolIPs,Lines=None):
        print "Debug --------- Rununin Init from A10 ...."
        super(A10Parser,self).__init__(PoolIPs,Lines)
        
    NamePattern=re.compile(r'\*(\S+)')
    StartPattern=re.compile(r'(-{15,}|Content:)')
    IpPattern=re.compile(r'((\d+\.){3}\d+)')
    TablePattern=re.compile(r'show\s+(\S+)\s+(\S+)')
    
    def PoolParser(self,LineNo):
        Count=0
        PoolName=None
        if CmdParams.Defined('D'):
                WrLog("Debug --- A10 Pool Parser Start Parssing ")
        Match=self.TablePattern.search(self.content[LineNo])
        while ( not Match and Count+LineNo < self.content.__len__()):
            Match=self.NamePattern.match(self.content[LineNo+Count])
            if Match:
                PoolName=Match.group(1)
                #Count += 1
                if CmdParams.Defined('D'):
                    WrLog("Debug --- Pool %s Start Parse configuration" % PoolName )
                #continue
            Match=self.IpPattern.search(self.content[LineNo+Count])
            if Match:
                if self.PoolListByIP.has_key(Match.group(1)):
                    self.PoolListByIP[Match.group(1)].append(PoolName)
                else:
                    self.PoolListByIP[Match.group(1)]=[PoolName,]
                if self.PoolListByName.has_key(PoolName):
                    self.PoolListByName[PoolName].append(Match.group(1))
                else:
                    self.PoolListByName[PoolName]=[Match.group(1),]
                if CmdParams.Defined('D'):
                    WrLog("Debug: adding IP %s to Pool %s" % (Match.group(1),PoolName))
            else:
                WrLog("DEBUG ---- %s NOT CONTAINS IP" % self.content[LineNo+Count] )
            Count += 1
            if CmdParams.Defined('D'):
                WrLog("Debug: Check if \"%s\" is end of table" % self.content[LineNo + Count ])
            Match=self.TablePattern.search(self.content[LineNo + Count ])
        WrLog("Debug - Stop Parrsing Pool at Line %d" % Count)
        return Count - 1
    
    def VsParser(self,LineNo):
        Count=0
        VsServer=None
        Match=self.TablePattern.search(self.content[LineNo])
        while ( not Match and Count+LineNo < self.content.__len__()):
            Match=self.NamePattern.match(self.content[LineNo+Count])
            if Match:
                VsServer=Match.group(1)
                # Count += 1
                # continue
            Match=re.match(r'(\S+)',self.content[LineNo+Count])
            if Match:
                if Match and self.PoolListByName.has_key(Match.group(1)):
                    if not VsServer in self.VirtaulServer:
                        self.VirtaulServer[VsServer]={ 'Vlans' : ["Not Ready Yet ...",]}
                    if not self.VirtaulServer[VsServer].has_key('PoolList'):
                        self.VirtaulServer[VsServer]['PoolList']=[Match.group(1),]
                    else:
                        self.VirtaulServer[VsServer]['PoolList'].append(Match.group(1))
            Count += 1
            Match=self.TablePattern.search(self.content[LineNo+Count])
        return Count - 1
    
    def RuleParser(self,LineNo):
        Count=0
        Pattern=re.compile("\s(%s)[\s\]].+?equals\s+(\S+?)[\s\]\}\)]" % '|'.join(self.PoolListByName.keys()))
        Match=self.TablePattern.search(self.content[LineNo])
        while ( not Match and Count+LineNo < self.content.__len__() - 1):
            Match=Pattern.search(self.content[LineNo+Count])
            if Match:
                if self.Clients.has_key(Match.group(2)):
                    self.Clients[Match.group(2)].append(Match.group(1))
                else:
                    self.Clients[Match.group(2)]=[Match.group(1),]
                self.RuleList[self.CurrentName]=Match.group(1)
            Count += 1
            Match=self.TablePattern.search(self.content[LineNo + Count])
        return Count -1 
            
    
    ParseMap= { 'service-group'      : PoolParser ,
                'virtual-server'   : VsParser ,
                'aflex'      : RuleParser  }
    def Parse(self,Lines):
        print "Debug - in A10 Parse ...."
        self.content=Lines
        self.CurrentName=None
        Iter=0;
        PType=None
        LastType=None
        while Iter<Lines.__len__():
            LineType=self.TablePattern.search(self.content[Iter])
            if LineType:
                if LineType.group(1) == 'slb':
                    PType=LineType.group(2)
                elif LineType.group(1) == 'aflex':
                    PType='aflex'
                    self.CurrentName=LineType.group(2)
                else :
                    raise ParseError("Unknown show command: \"%s\" Line %d" % (self.content[Iter],Iter) )
                Iter += 1
                WrLog("Debug - A10 Parsser Change Table to %s at Line %d" % (PType,Iter))
                continue
            LineType=self.StartPattern.match(self.content[Iter])
            if LineType:
                Iter += 1
                Iter += self.ParseMap[PType](self,Iter)
            Iter += 1
                ### Check how we parse each 
    
    

def SetTable(Title,Cont):
    Line=re.sub("\s",'=', "%65s" % ' ')
    Result=[ "%-30s | %-30s" % (Title[0],Title[1]) , Line , ]
    for KName,Kval in Cont.items():
        if type(set([])) == type(Kval):
            Result.append("%-30s | %-30s" % (KName,','.join(Kval)) )
            ###print "Debug --- Set ...."
        else:
            ##print "Type Kval: %s %s" % (type(Kval),Kval)
            Result.append("%-30s | %-30s" % (KName,Kval) )
    return Result

def PoolIps():
    if CmdParams.Defined('IPs'):
        return re.split(',',CmdParams.GetCLIParam('IPs'))
    FileName=CmdParams.GetCLIParam('Pkg')
    MetaMember="META/src.xml"
    if not os.path.isfile(FileName):
        FileName += ".package"
    PkgObj=zipfile.ZipFile(FileName,'r')
    MainObj=PkgObj.open(MetaMember,'r')
    ##ggg=LibXML.ElementTree()
    MainXml=LibXML.fromstring(MainObj.read())
    NodeList=MainXml.findall(r'.//Blade[server_role="MSP"]')
    #NodeList=MainXml.findall(r'.//Blade')
    Result=[]
    # WrLog("Debug - Go Over MSPs")
    for BladeNode in NodeList:
        Result.append(BladeNode.findtext(r'.//data_ip'))
        for Iter in BladeNode.findall(r'.//XmlIPAddress'):
            Result.append(Iter.findtext('.'))
            #WrLog("Debug - update IPs" , Result)
    return Result

def ReadFile(FileName):
    FileObj=file(FileName,'r')
    Cont=FileObj.read()
    return re.split('\n',Cont)

def ReadADC(AdcIP,LoginInfo):
    LoginStr=re.sub(r'[\/\\]',' ',LoginInfo)
    if CmdParams.Defined('D'):
        WrLog("Debug - LoginStr: %s ... Orig String: %s" % (LoginStr,LoginInfo))
    ExcStr="expect AdcTest.tcl %s %s" % (AdcIP,LoginStr) 
    Proc=subprocess.Popen(ExcStr,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,shell=True)
    (sout,serr)=Proc.communicate()
    Proc.wait()
    if Proc.returncode:
        WrLog("Error - Fail to read ADC Info from %s" % AdcIP,
              "\tOutPut Info:",serr,sout)
        return []
    if sout:
        Result=re.split(r'[\n\r]',sout)
    else:
        Result=[]
    if serr:
        Result.append(re.split('\n',serr))
    return Result
    
#################################################################################
#
#    M A I N
#
##################################################################################

CmdParams=CLIParams(**G_CLIArgs)
WrLog("Input Parameters:")
for (Name,PVal) in CmdParams.GetAllParams().items():
    WrLog("INFO  - %s : %s" % (Name,PVal))

if CmdParams.Defined('File'):
    Lines=ReadFile(CmdParams.GetCLIParam('File'))
else:
    Lines=ReadADC(CmdParams.GetCLIParam("ADCIP"),CmdParams.GetCLIParam("ADCLogin"))

if CmdParams.Defined('D'):
    WrLog("Debug: F5 Parssing Result:",Lines[:15])
#LoginStr=CmdParams.GetCLIParam("ADCLogin")
#LoginStr=re.sub(r'[\/\\]',' ',CmdParams.GetCLIParam("ADCLogin"))
#WrLog("","Debug - LoginStr: %s ... Orig String: %s" % (LoginStr,CmdParams.GetCLIParam("ADCLogin")))

#F5Entity=file(CmdParams.GetCLIParam('File'),'r')

#Cont=F5Entity.read()
#Lines=re.split('\n',Cont)
#CmdParams.GetCLIParam('IPs'))
PoolList=','.join(PoolIps())
WrLog("Debug - IPs: %s" % PoolList)
if CmdParams.Defined('A10'):
    Stam=A10Parser(re.split(',',PoolList),Lines)
else:
    Stam=F5Parser(re.split(',',PoolList),Lines)
## Stam=Parser(re.split(',',PoolList),Lines)
Chk=Stam.BalancerConfig() ##   .F5Config()

if CmdParams.Defined('D'):
    WrLog("Debug - Formal Record:",Chk,"","")
### Print Results:
if Chk.has_key('Client'):
    WrLog("Client Data-Group used:")
    LL=SetTable(("Data-Group Name","HPIs IPs",),Chk['Client'])
    for i in LL: WrLog(i)
else:
    WrLog("Warning - No Clients defined for these Pools")

#WrLog([i for i in LL ],"")
WrLog("","Pool Name List: %s" % ",".join(Chk['PoolList']))
LL=SetTable(("VS Name","VS VLANs"),Chk['VsList']) 
WrLog("","Virtual Servers:")
for i in LL: WrLog(i)
   




