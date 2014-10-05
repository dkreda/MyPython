__author__ = 'danielk'

import zipfile
import xml.etree.ElementTree as LibXML
import re,os,copy
from xml.dom import minidom

#import xml.dom

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

    def __contains__(self, item):
        return item in self.Content

    def __getitem__(self, item):
        return self.Content[item] if item in self.Content else None

    def Get(self,KName):
        return self.Content[KName] if KName in self.Content else None

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

    def __getitem__(self, item):
        if re.match(r'^\d+$',str(item)):
            for Node in self.Cage.values():
                if ('SlotNum' in Node) and Node['SlotNum']  == item:
                    return Node
        elif item in self.Cage:
            return self.Cage[item]
        raise KeyError("%s not exists at this topology instance" % item)

    def __contains__(self, item):
        print "Debug - in __contains method of Topology class item is %s (%s)....." % (item,type(item))
        print "Debug - %s " % str(item in self.Cage)
        return item in self.Cage

    def GetNode(self,Name):
        return self.Cage[Name]

    def __str__(self):
        Table={}
        Left=5
        for NodeName,NodeRec in self.Cage.items():
            if len(NodeName) > Left : Left = len(NodeName)
            for Colum,CVal in NodeRec:
                #print "Debug - Table is %s olum is %s" % (type(Table),type(Colum))
                if not Colum in Table: Table[Colum] = 5
                if len(CVal) > Table[Colum] : Table[Colum] = len(CVal)
                if len(Colum) > Table[Colum] : Table[Colum] = len(Colum)
        ItemOrder=Table.keys()
        Fstr=reduce( lambda x,y: x + "%*s " ,range(len(Table) +  1) , "")
        TmpList=[Left,""]
        for Name in ItemOrder : TmpList.extend((-1 * Table[Name],Name,) )
        #print TmpList
        Result=[ Fstr % tuple(TmpList)]
        for NodeName,NodeRec in self.Cage.items():
            TmpList=[-1 * Left,NodeName]
            ## ItemOrder[0]=NodeName
            for Name in ItemOrder : TmpList.extend((-1 * Table[Name],NodeRec.Get(Name),) )
            Result.append(Fstr % tuple(TmpList))
        return '\n'.join(Result)

class InfoObj(object):
    ParamLine=re.compile(r'([^#]+?)=\s*[\'\"](.+)[\'\"]')

    def __init__(self,FileName=None):
        self.Params={}
        self.ChFlag=False
        self.Name=FileName
        if FileName: self.ParseFile(FileName)

    def ParseFile(self,FileName):
        self.Name=FileName
        TmpFile=file(FileName,'r')
        self.Content=TmpFile.readlines()
        TmpFile.close()
        self.ParseString()

    def ParseString(self,*Lines):
        if len(Lines) > 0:
            self.Content=list(Lines)
        for Indx in xrange(len(self.Content)):
            MatchLine=self.ParamLine.match(self.Content[Indx])
            if not MatchLine: continue
            self.Params[MatchLine.group(1)]=Indx #MatchLine.group(2)

    def __getitem__(self, item):
        if item in self.Params:
            return  self.Params[item]
        else:
            raise KeyError("%s Not exists at INFO %s" % (item,self.Name if self.Name else "N/A"))

    def __contains__(self, item):
        return item in self.Params

    def isChanged(self):
        return self.ChFlag

    def Save(self,FileName=None):
        if FileName: self.Name=FileName
        if self.Name:
            TmpFile=file(self.Name,'w')
            TmpFile.writelines(*self.Content)
            TmpFile.close()
            self.ChFlag=False
        else:
            raise IOError("No File Name defined to Info Object - can not save the INFO File")

    def __setitem__(self, key, value):
        if key in self.Params:
            #self.Params[key]=value
            self.Content[self.Params[key]]="%s='%s'\n" % (key,value)
        else:
            self.Content.append(r"%s='%s'" % (key,value))
            self.Params[key]=len(self.Content)
        self.ChFlag=True

    def GetParam(self):
        Result={}
        for KName,LineNum in self.Params:
            TmpMatch=self.ParamLine.match(self.Content[LineNum])
            if not TmpMatch:
                raise Exception("Internal Error Line %d at INFO File not Contains Parameter:\n%s" % (LineNum,self.Content[LineNum]))
            Result[TmpMatch.group(1)]=TmpMatch.group(2)
        return Result


class PkgHarmony(object):
    MainMem="META/src.xml"
    CnfMap={'MAC': (".//mgmt_mac" ,"mgmt_mac",) ,
            'Role': (".//server_role" , ) ,
            'DataIP': (".//data_ip",)}

    ChassMap= { 'Host' : ('.//HostName' ,) ,
                'IP'   : ('.//IPAddress' ,) ,
                'HwType' : ('.//Type',) ,
                'User'  : ('//chassisUserName' ,'root',) ,
                'Password' : ('//chassisPassword','f1@shr00t',)
    }

    def __init__(self,PkgName,**AdditionalParamsMap):
        self.PkgPath=PkgName
        for PName,PXpath in AdditionalParamsMap.items():
            self.CnfMap[PName]=(PXpath,)
        self.Load()

    def Name(self):
        Name=re.search(r'([^\/\\]+?)$',self.PkgPath)
        return Name.group(1)

    def Load(self):
        self.PkgContent=zipfile.ZipFile(self.PkgPath,'r')
        TmpText=self.PkgContent.read(PkgHarmony.MainMem)
        self.PkgConf=LibXML.fromstring(TmpText)

    def FindSlot(self,BladName,Chassi):
        ChPath=str(Chassi) if re.match(r'^\d$',str(Chassi)) else r'Name="%s"' % Chassi
        for Indx in xrange(1,20):
            SearchXpath='.//Chassis/Chassi[%s]/Slots/Blade[%d]/Name' % (ChPath,Indx)
            TmpNode = self.PkgConf.find(SearchXpath)
            if TmpNode is None: continue
            if TmpNode.text == BladName : return Indx
        return -1

    def GetINFO(self,BladeName):
        Index=str(BladeName) if re.match(r'^\d+$',BladeName) else "Name=\"%s\"" % BladeName
        Xpath='.//Slots/Blade[%s]/IPAddress' % Index
        NodeList=self.PkgConf.findall(Xpath)
        if NodeList is None or len(NodeList) <= 0:
            raise KeyError("%s not exists at package" % str(BladeName))
        if len(NodeList) > 1 :
            raise KeyError("there are more than one Blades \"%s\" at Packge %s" % (str(BladeName,self.Name())))
        return "_".join(("INFO",NodeList[0].text))

    def _HwWA(self):
        TmpNodeList=self.PkgConf.findall('.//additional_Parameters/string')
        if TmpNodeList and len(TmpNodeList) > 0:
            for Iter in TmpNodeList:
                TmpMatch=re.match(r'VsphereFolder\$(.+?)\$',Iter.text)
                if TmpMatch:
                    print "Debug - Hardware is Virtual system Folder is %s" % TmpMatch.group(1)
                    return TmpMatch.group(1)
        return None


    def GetChassi(self):
        ## Return List of Chassis
        Result={}
        for ChasNode in self.PkgConf.findall('.//Chassi'):
            KeyName=ChasNode.find('.//Name').text
            TmpDict={}
            for PName,XmlNode in self.ChassMap.items():
                TmpNode=ChasNode.find(XmlNode[0]) if re.match('\.',XmlNode[0]) else self.PkgConf.find('.' + XmlNode[0])
                if TmpNode is None:
                    if len(XmlNode) > 1:
                        TmpDict[PName]=XmlNode[1]
                        print "Warning - Missing parameter %s at Package %s using default %s" % (PName,self.Name(),XmlNode[1])
                    else:
                        print "Warning - %s has missing Parameter %s (%s) at Package %s" % (KeyName,PName,XmlNode[0],self.Name())
                else:
                    TmpDict[PName]=TmpNode.text
                #TmpDict[PName]=ChasNode.find(XmlNode).text if re.match('\.',XmlNode) else self.PkgConf.find('.' + XmlNode).text
            Tmp=self._HwWA()
            if Tmp:
                TmpDict['HwType']="VmWare %s" % Tmp
                TmpDict['Folder']=Tmp
            #TmpDict['HwType']="VmWare:%s" % Tmp if Tmp else TmpDict['HwType']
            Result[KeyName]=TmpDict
            print "Hardware Type is %s" % TmpDict['HwType']
        return Result

    def GetTopology(self,Chassi=None,SlotNum=None):
        # BladeIndx=str(SlotNum) if SlotNum else "Name"
        if SlotNum:
            BladeIndx= str(SlotNum) if re.match(r'^\d+$',str(SlotNum)) else r'Name="%s"' % SlotNum
        else:
            BladeIndx="Name"
        if Chassi:
            ChIndx= str(Chassi) if re.match(r'^\d$',str(Chassi)) else 'Name="%s"' % Chassi
            SearchXpath=r'.//Chassis/Chassi[%s]/Slots/Blade[%s]' % (ChIndx,BladeIndx)
        else:
            SearchXpath='.//Blade[%s]' % BladeIndx
        Result=Topology()
        for XmlNode in self.PkgConf.findall(SearchXpath):
            Name=XmlNode.find(".//Name").text
            Result.AddNode(Name,BladeNode(XmlNode.find(".//HostName").text,
                                XmlNode.find(".//IPAddress").text ))
            for PName,Xpath in self.CnfMap.items():
                MyNode=XmlNode.find(Xpath[0])
                ##print "Debug - Looking for %s (%s)" % (PName,Xpath)
                if MyNode is None:
                    print "Warning - Parameter %s is missing for %s at Chassi %s Slot %s (Xpath %s)" % (PName,Name,str(Chassi),str(SlotNum),Xpath)
                else:
                    Result.SetNode(Name,PName,MyNode.text)
        return Result

    def Update_Topology(self,NewTopology,Chassi=None):
        # Go over all Nodes of NewTopolgy - and update the
        # relevant Info file and src.xml - if NewTopology contains Node that
        # not exists at the package Exception is raised
        MemberList={ }
        for Name,Rec in NewTopology:
            Slot=Rec['SlotNum'] if 'SlotNum' in Rec else self.FindSlot(Name,Chassi)
            Xpath=".//Blade[Name=\"%s\"]" % Name
            InfoFile=self.GetINFO(Name)
            Node=self.PkgConf.findall(Xpath)
            if Node is None or len(Node) <= 0:
                raise KeyError("Faile to find Blade/Host %s at Package %s (xpath: %s)" % (Name,self.Name(),Xpath))
            FileObj=self.PkgContent.open("blades/%s" % InfoFile,'r')
            InfoContent=FileObj.readlines()
            FileObj.close()
            MemberInfo=InfoObj()
            MemberInfo.ParseString(*list(InfoContent))
            #print "Debug - Info Content:" , MemberInfo.Content
            # Go over all attributes of theNodes and update the relevant Node attributes
            for Attr,AttVal in Rec:
                if not Attr in self.CnfMap: continue
                Xpath=self.CnfMap[Attr][0]
                EditNode= Node[0].find(Xpath) if re.match(r'^\.',Xpath) else self.PkgConf.find('.%s' % Xpath)
                EditNode.text=AttVal
                for InfoParam in self.CnfMap[Attr][1:]:
                    MemberInfo[InfoParam]=AttVal
            if MemberInfo.isChanged():
                MemberList["blades/%s" % InfoFile ]=MemberInfo    # copy.deepcopy(MemberInfo)
        self.PkgContent.close()
        if len(MemberList):
            ExceStr="zip -d %s %s" % (self.PkgPath," ".join(MemberList.keys()))
            print "Debug  - Execute: %s" % ExceStr
            Rc=os.system(ExceStr)
            if Rc : raise OSError("Fail to delete member at package")
        Tmp=LibXML.tostring(self.PkgConf)
        Tmp=minidom.parseString(re.sub(r">\s+<","><",Tmp))
        Buf=Tmp.toprettyxml(indent="  ")
        MemberList={ self.MainMem   : Buf }
        self.PkgContent=self.PkgContent=zipfile.ZipFile(self.PkgPath,'a')
        for MemberName,MemberObj in MemberList.items():
            self.PkgContent.writestr(MemberName,
                    "".join(MemberObj) if MemberName == self.MainMem else "".join(MemberObj.Content))
        self.PkgContent.close()
        self.Load()
