#!/usr/bin/env python

import sys,re,subprocess
import datetime,time
import os
import zipfile
import xml.etree.ElementTree as LibXML
import collections

G_CLIArgs={'LogFile'    : '-' ,
           'ServerIP'   : 'qavcenter.qaflashnetworks.local' ,
           'User'       :     "administrator" ,
           'Password'   : "1q2w3e4R" }

G_FileHandle=[]

def WrLog(*Lines):
    if not len(G_FileHandle):
        #print "Debug - First time in log ...."
        for FileName in G_CLIArgs["LogFile"].split(","):
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
    
    def GetAllParams(self):
        return self.ParaList
    

class HNode(object):
    __MustParams=set(('IP','MAC','HostName',))
    def __init__(self,**IniParams):
        self.__Node=IniParams
#        if 'IP' in IniParams:
#            self.IP=IniParams["IP"]
#        if 'MAC' in IniParams:
#            self.MAC=IniParams['MAC']
#        if 'HostName' in IniParams:
#            self.HostName=IniParams['HostName']
        #print "Debug - %s" % ",".join(IniParams.keys())
        #for (VKey,VVal) in IniParams.items():
            #print "\t - %s : %s" % (VKey,VVal)
        ## print " oooof : IP = %s  ... %s " % (IniParams["IP"],getattr(IniParams,'IP',"Fatal !"))
        
    def __str__(self):
        #print "Debug - %s" % dir(self)

        return ", ".join(["%s : %s" % (HKey,HVal) for HKey,HVal in self.__Node.items()] )
        #return ",".join((getattr(self,'IP','No IP'),
        #                 getattr(self,'HostName','Empty Host Name'),
        #                 getattr(self,'MAC','No MAC')))
    
    def Set(self,Param,Val):
        if Param in self:
            raise  Exception("%s is already Initiate" % Param)
        else:
            self.__Node[Param]=Val
#        ErrFlag=getattr(self,Param,"O.K")
#        if ErrFlag=="O.K":
#            setattr(self,Param,Val)
#        else:
#            raise  Exception("%s is already Initiate" % Param)
    def __setitem__(self, key, value):
        if key in self:
            raise  Exception("%s is already Initiate" % key)
        else:
            self.__Node[key]=value

    def __contains__(self, item):
        return item in self.__Node

    def __getitem__(self, item):
        return self.__Node[item] if item in self else None
    


class Topology(object):
    def __init__(self,SystemName="Default"):
        self.SystemName=SystemName
        self.__Topology={}
    def __str__(self):
        Result=[]
        return "{%s}" % ','.join([ "%s : {%s}" % (NName,NVal) for NName,NVal in self.__Topology.items()])

    def AddNode(self,Name,Node):
        self.__Topology[Name]=Node
        
    #def GetNode(self,Name):
    #    return self.Topology[Name]
    
    def EachNode(self):
        for (Name,Rec) in self.__Topology.items():
            yield (Name,Rec)
            
    def ModifyNode(self,Name,**Params):
        for (ParamName,ParamVal) in Params.items():
            self.__Topology[Name].Set(ParamName,ParamVal)

    def __contains__(self, item):
        return item in self.__Topology

    def __getitem__(self, item):
        return item if item in self else None

    def __iter__(self):
        for Iter in self.__Topology:
            yield Iter

  
  
class PkgHandler(object):
    MetaFile="META/src.xml"
    def __init__(self,PkgName):
        self.Name=PkgName
        self.ZipObj=None
        
    def Load(self):
        self.ZipObj=zipfile.ZipFile(self.Name,'r')
        Member=self.ZipObj.open(self.MetaFile,'r')
        self.XmlRoot=LibXML.fromstring(Member.read())
        self.ZipObj.close()
        
    def GetTopology(self):
        MapParam= { "Role"	: ".//server_role" ,
		    "IP"	: ".//IPAddress" ,
		    "MAC"	: ".//mgmt_mac" ,
		    "data_ip"	: ".//data_ip" ,
		    "HostName"	: ".//HostName" }
        Result=Topology(self.Name)
        for Blad in self.XmlRoot.findall('.//Blade[mgmt_mac]'):
            KeyName=Blad.findtext(r'.//Name')
            NewNode=HNode()
            for HKey,Xpath in MapParam.items():
                NewNode.Set(HKey,Blad.findtext(Xpath))
            Result.AddNode(KeyName,NewNode)
        return Result

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
        self.__FByMoRef=self.__Server._get_managed_objects(pysphere.MORTypes.Folder)
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

    
def BuildFolderTree(VimServer):
    StartTime=time.time()
    print "%s Debug - Start Retreive all folders ...." % time.ctime()
    TmpDict=VimServer._get_managed_objects(pysphere.MORTypes.Folder)
    FolderTree={}
    for Mo_Ref,FName in TmpDict.items():
        Tmp=VimServer._get_object_properties(Mo_Ref, property_names=('name','parent',))
        TmpDict[Mo_Ref]={}
        for Iter in Tmp.PropSet:
            TmpDict[Mo_Ref][Iter.Name]=Iter.Val
    print "%s Debug - Finish to reteive folders. Start indexing" % time.ctime()
    for Mo_Ref,FRec in TmpDict.items():
        Tree=[FRec['name'],]
        DirRec=FRec
        while 'parent' in DirRec:
            if DirRec['parent'] in TmpDict:
                DirRec=TmpDict[DirRec['parent']]
                Tree.append(DirRec['name'])
            else:
                break
        if 'parent' in FRec:
            Tree.pop()
            Tree.reverse()
            DirKey='/' + '/'.join(Tree)
            FolderTree[DirKey]={'name' : FRec['name'] ,
                                'Ref'  : Mo_Ref ,
                                'Parent' : FRec['parent']}
        else:
            print "Debug - skip update of %s (%s)" % (FRec['name'],Mo_Ref)
    ttt=time.gmtime(time.time()-StartTime)
    print "%s Debug - retreival took %02d:%02d " % (time.ctime(),ttt[4],ttt[5])
    return FolderTree


    
##################################################################################
#
#    M A I N
#
##################################################################################

CmdParams=CLIParams(**G_CLIArgs)



WrLog("Input Values")
for (Name,PVal) in CmdParams.GetAllParams().items():
    WrLog("Debug - %s : %s" % (Name,PVal))

if os.path.isdir(CmdParams.GetCLIParam('Pkg')):
    print "List all Packages Topology in %s:" % CmdParams.GetCLIParam('Pkg')
    for PkgName in os.listdir( CmdParams.GetCLIParam('Pkg')):
        FullPath="%s/%s" % (CmdParams.GetCLIParam('Pkg'),PkgName)
        if not os.path.isfile(FullPath): continue
        DestPackage=PkgHandler(FullPath)
        DestPackage.Load()
        print PkgName
        print "\t-%s\n" % "\n\t-".join(DestPackage.GetTopology())
    exit(0)
elif os.path.exists(CmdParams.GetCLIParam('Pkg')):
    DestPackage=PkgHandler(CmdParams.GetCLIParam('Pkg'))
    DestPackage.Load()
    print DestPackage.GetTopology()
else:
    print "Error - %s is not Pacakge or file" % CmdParams.GetCLIParam('Pkg')
    exit(1)

##############################
#
#   Test section
############################
print "Start SDK Test ....."
import pysphere

MainServer=pysphere.VIServer()
print "Debug - Login to VsPhere ..."
MainServer.connect(CmdParams.GetCLIParam('ServerIP'),
                   CmdParams.GetCLIParam('User'),
                   CmdParams.GetCLIParam('Password'),
                   trace_file="/tmp/MyChk.txt")


VmObjList={}
StartTime=time.time()
print "%s Debug - Start retreive all Virtual machines ....." % time.ctime()
TmpDict=MainServer._get_managed_objects(pysphere.MORTypes.VirtualMachine)
ttt=time.gmtime(time.time()-StartTime)
print "%s Debug - retreival took %02d:%02d " % (time.ctime(),ttt[4],ttt[5])
#print "Debug ---   TmpDict:"
#print TmpDict
for MoRef,ObjName in TmpDict.items():
    VmObjList[ObjName]=MoRef

print "-D- connection State:"
print MainServer.is_connected()

Folders=FolderTree(MainServer)

#FolderTree=BuildFolderTree(MainServer)

#print "Debug - Folder Tree:"
#print FolderTree

##############################################
# List of attributes - needed for VM:
# name - String
# network - ArrayOfManagedObjectReference_Holder
# parent - String  (Reference to folder )
# rootSnapshot - .ArrayOfManagedObjectReference_Holder
# storage - DynamicData_Holder



for VmName,Node in DestPackage.GetTopology().EachNode():
    WrLog("Debug - Retrieve %s" % VmName )
    try:
        #VmList=MainServer.get_vm_by_name(VmName)
        #print "Debug - Retreive by Name (%s):" % VmName
        #print VmList.get_properties()
        VmList=MainServer.get_registered_vms(advanced_filters={ 'name' : VmName})
        print "-DDDD:   ------------------------------------------------------"
        print VmList
        print "Retrieve - View ..... of %s" % VmName
        ## VmList=MainServer._get_object_properties(VmObjList[VmName], get_all=True)
        VmList=MainServer._get_object_properties(VmObjList[VmName], property_names=('name','parent','network',))
        #print VmList
        #print VmList.PropSet
        #print dir(VmList)
    # print VmList.PropSet
        print "\n================================================================================"
        #print "PropSet:"
        #print dir(VmList.PropSet)
        #print ">  Obj :"
        #print dir(VmList.Obj)
        #print ">  DynamicProperty"
        #print dir(VmList.DynamicProperty)
        #VmList.PropSet.count
        for Iter in VmList.PropSet:
            # print "Debug - Iterate %s" % Iter
            if 'VmView' in Node:
                Node['VmView'][Iter.Name]=Iter.Val
            else:
                Node['VmView']={ Iter.Name : Iter.Val }
            print "%s - %s" % (Iter.Name,Iter.Val)
        if 'parent' in Node['VmView']:
            if Node['VmView']['parent'] in Folders:
                print "Debug - Machine %s under %s" % (VmName,Folders[Node['VmView']['parent']]['FullPath'])
        else:
            raise Exception("No Valid Folder for %s" % VmName)

        #Test=
        #break
    except Exception as e:
        print "Hey Vi Exception for %s ..." % VmName
        print "Exception message: %s" % e.message
        print e
        continue
        raise
    
    print "(-------------------------------)"
    print "\n\n"
    
    
    

print "\n\nTopology (From Package %s):" % DestPackage.Name
print "\t%s\n" % "\n\t-".join(DestPackage.GetTopology())
#TmpDict=DestPackage.GetTopology()
#for Host,Rec in TmpDict.EachNode():
#    print "%s :" % Host
#    print "\t\t%s" %Rec

##print DestPackage.GetTopology()
MainServer.disconnect()


#  _retrieve_properties_traversal(property_names=['name'],
#                                                      from_node=from_mor,
#                                                      obj_type=mo_type)
#    Retrieve List

#def _retrieve_properties_traversal(self, property_names=[],
#                                      from_node=None, obj_type='ManagedEntity'):
#        """Uses VI API's property collector to retrieve the properties defined
#        in @property_names of Managed Objects of type @obj_type ('ManagedEntity'
#        by default). Starts the search from the managed object reference
#        @from_node (RootFolder by default). Returns the corresponding
#        objectContent data object."""

###def _get_object_properties(self, mor, property_names=[], get_all=False):
#        """Returns the properties defined in property_names (or all if get_all
#        is set to True) of the managed object reference given in @mor.
#        Returns the corresponding objectContent data object."""



#ReadCLI()
#WrLog("","","Perl Input Values")
#for (Name,PVal) in G_CLIArgs.items():
#    WrLog("Debug - %s : %s" % (Name,PVal))



    
