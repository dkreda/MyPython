#!/usr/bin/python
######################
##  Check Remarks
#  Template script
###############

#import sys,re,subprocess,StringIO,datetime,time
import sys,re,subprocess,datetime
import PkgUtil
import zipfile
import xml.etree.ElementTree as LibXML

##############################################
#  Global parameters
##############################################

G_CLIArgs={'LogFile' : '-'}
G_FileHandle=[]
G_ErrorParams={}

def WrLog(*Lines):
    if not len(G_FileHandle):
        for FileName in G_CLIArgs["LogFile"].split(","):
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
            f.write(Line + "\n")
        
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
            Proc.wait()
            WrLog("\t" + re.sub("\n","\t",sout))
            if ( Proc.returncode ) :
                WrLog("- Error Last Command \"%s\" Finish with exit code %d" % (ExecCmd,Proc.returncode))
            Result += Proc.returncode
        except Exception as e:
            WrLog(type(e),"Error - Exceutng ...(%s)" % ExecCmd,"Message:",e.message)
            Result += 1
    return Result
    
def ReadCLI():
    global G_CLIArgs
    Pattern=re.compile("-(\S+)")
    Last=None
    ArgList=[]
    for Index in xrange(1,sys.argv.__len__()):
        ## WrLog("Debug - Parsing " + CliArg + " Parameter")
        Param=Pattern.match(sys.argv[Index])
        #WrLog(dir(Param))
        if Param is not None:
            if Last is not None:
                G_CLIArgs[Last]=','.join(ArgList)
            Last =  Param.groups()[0]
            ArgList=[]
        else:
            ArgList.append(sys.argv[Index])
            
    G_CLIArgs[Last]=','.join(ArgList)
    

class BladeNode(object):
    def __init__(self,Name,IP,**KeyArgs):
        self.Content={ "Host" : Name , "IP" : IP }
        for KeyName,ArgVal in KeyArgs.items():
            self.Content[KeyName]=ArgVal
    def __str__(self):
        return "%s" % self.Content

    def GetParams(self):
        return self.Content

    def __iter__(self):
        for AttrName,AttrVal in self.Content.items():
            yield (AttrName,AttrVal)

    def Get(self,KName):
        return self.Content[KName]

    def Modify(self,ParamName,ParamVal):
        if ParamName in self.Content:
            self.Content[ParamName]=ParamVal
        else:
            raise Exception("Unknown Key %s - use one of %s" % (ParamName,','.join(self.GetParams().keys()) ))

    def Set(self,ParamName,ParamVal):
        self.Content[ParamName]=ParamVal

class Topology(object):
    def __init__(self):
        self.Cage={}
        
    def AddNode(self,Name,Node):
        if ( Name not in self.Cage ):
            self.Cage[Name]=Node
        else:
            raise Exception("%s already exists at Topology" % Name)
    def SetNode(self,Name,Parameter,Val):
        if Name in self.Cage:
            self.Cage[Name].Set(Parameter,Val)
        else:
            raise Exception("%s not exists at at topology instance (%s)" % (Name,self.__class__))

    def __iter__(self):
        for Name,DictRec in self.Cage.items():
           yield (Name,DictRec)

    def __contains__(self, item):
        print "Debug - in __contains method of Topology class item is %s (%s)....." % (item,type(item))
        return item in self.Cage

    def GetNode(self,Name):
        return self.Cage[Name]
            

    
class PkgHarmony(object):
    MainMem="META/src.xml"
    CnfMap={'MAC': ".//mgmt_mac" ,
            'Role': ".//server_role" ,
            'DataIP': ".//data_ip"}

    def __init__(self,PkgName):
        self.PkgPath=PkgName
        self.MainTopology=Topology()
        self.Load()
        
    def Name(self):
        Name=re.search(r'([^\/\\]+?)$',self.PkgPath)
        return Name.group(1)
        
    def Load(self):
        self.PkgContent=zipfile.ZipFile(self.PkgPath,'r')
        self.PkgConf=LibXML.fromstring(self.PkgContent.read(PkgHarmony.MainMem))
        self._ReadTopology()
        # print "Debug - List of members:"
        # print self.PkgContent.namelist()
        
    def _ReadTopology(self):
        for XmlNode in self.PkgConf.findall('.//Blade[Name]'):
            Name=XmlNode.find(".//Name").text
            self.MainTopology.AddNode(Name,BladeNode(XmlNode.find(".//HostName").text,
                                                     XmlNode.find(".//IPAddress").text ))
            for Param,Xpath in PkgHarmony.CnfMap.items():
                self.MainTopology.SetNode(Name,Param,XmlNode.find(Xpath).text)

    def GetINFO(self,BladeName):
        if BladeName in self.MainTopology:
            Tmp=self.MainTopology.GetNode(BladeName).Get('IP')
            return '_'.join(("INFO",Tmp,))
        else:
            raise Exception("%s not exists at %s topology" % (BladeName,self.PkgPath))

    def GetTopology(self):
        return self.MainTopology


###############################################################################
#
#   M A I N  
#
###############################################################################

ReadCLI()
for i in G_CLIArgs:
    WrLog("Debug - %s => %s" % (i, G_CLIArgs[i]))

if 'Test' in G_CLIArgs:
    print "Debug - Test is defined ..."
    
ForTest=PkgHarmony(G_CLIArgs['Pkg'])
print "Name of %s is %s" % (ForTest.PkgPath,ForTest.Name())

for (dd,ff) in ForTest.MainTopology.Cage.items():
    print "%s - %s" % (dd , ff.GetParams())
    for AtName,AtVal in ff:
        print "Debug Test: %s - %s" % (AtName,AtVal)


for a1,a2 in ForTest.GetTopology():
    print "Info File of %s is %s" % (a1,ForTest.GetINFO(a1))
print "\n\n\n"
#rint dir(ForTest)
#print "\n\n"
#print dir(PkgHarmony)

if hasattr(ForTest,'Load'):
    print "Load is attribute ..."
    
if hasattr(ForTest,'TestFunc'):
    print "TestFunc  exists at ForTest ....."