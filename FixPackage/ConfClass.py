__author__ = 'danielk'

from collections import defaultdict as dfdict
import re , sys

class ConfiguartionError(Exception): pass

class CParam(object):
    def __init__(self,Description='No Description',mandatory=False,aliases=None,ValidPattern=None):
        self.Param=dfdict(None)
        self.Param['Descrip']=Description
        self.Param['Must']=mandatory
        self.Param['Alias']= aliases if aliases else []
        self.Param['Pattern']=ValidPattern

    def CheckVal(self,TheVal=None):
        if not TheVal: TheVal=self.Param['Value'] if 'Value' in self.Param else None
        if TheVal:
            if self.Param['Pattern']:
                Pattr=self.Param['Pattern']
                Result=reduce(lambda x , y : x and (True if re.search(Pattr,str(y)) else False),TheVal,True)
                #Result=reduce(lambda x , y : x + y  ,TheVal,True)
            #reduce(lambda x,y : x and (True if re.search(self.Param['Pattern'],str(y)) else False),TheVal,initializer=True)
            #Result=re.search(self.Param['Pattern'],str(TheVal)) if self.Param['Pattern'] else True
            else:
                Result=True
        else:
            Result=not self.is_Requier()
        return True if Result else False

    def is_Alias(self,ChStr):
        return str(ChStr) in self.Param['Alias']

    def Describe(self):
        return self.Param['Descrip']

    def is_Requier(self):
        return self.Param['Must']

    def setAttr(self,Name,Val):
        self.Param[Name]=Val

    def set_Mandatory(self,BoolVal):
        self.setAttr('Must',BoolVal)

    def set_Description(self,Desc):
        self.setAttr('Descrip',Desc)

    def set_Pattern(self,Pattern):
        self.setAttr('Pattern',Pattern)

    def set_Val(self,Val):
        if self.CheckVal(Val):
            self.Param['Value']=Val
        else:
            raise ConfiguartionError("Invalid Value %s - not Match the pattern %s" % (str(Val),self.Param['Pattern']))

    def is_Empty(self):
        return not 'Value' in self.Param

    def get_Val(self):
        return self.Param['Value'] if 'Value' in self.Param else None

class ConfParser(object):
    CLI=1
    ConfFile=2
    XmlFile=4
    def __init__(self,**ParamMap):
        self.Conf=dfdict(CParam)
        for PName,PRec in ParamMap.items():
            #print "Debug - Add %s > %s" % (PName,PRec)
            self.AddParam(PName,**PRec)

    def AddParam(self,Name,**CparamAttr):
        self.Conf[Name]=CParam(**CparamAttr)

    def getAlias(self,Name):
        for PName,Rec in self.Conf.items():
            if Rec.is_Alias(Name):
                return PName
        return None

    def ParseCLI(self):
        print "Debug -- ReadCLi command"
        LastParam=None
        ValList=[]
        for CliStr in sys.argv[1:]:
            TmpMatch=CLIPreffix.match(CliStr)
            if TmpMatch:
                ParamName=TmpMatch.group(1)
                if LastParam:
                    if not LastParam in self.Conf:
                        self.Conf[LastParam]=CParam('Unknown CLI Parameter')
                    self.Conf[LastParam].set_Val(ValList)
                    self.Conf[LastParam].setAttr('InFlag',True)
                TmpStr=self.getAlias(ParamName)
                LastParam=TmpStr if TmpStr else ParamName
                ValList=[]
            else:
                ValList.append(CliStr)
        if LastParam:
            if not LastParam in self.Conf:
                self.Conf[LastParam]=CParam('Unknown CLI Parameter')
            self.Conf[LastParam].set_Val(ValList)
            self.Conf[LastParam].setAttr('InFlag',True)


    def ParseConf(self,FileName): pass

    def ParseXml(self,FileName): pass

    def ReadConfig(self,ParseOrder):
        MapMethod= { ConfParser.CLI : self.ParseCLI ,
                     ConfParser.ConfFile: self.ParseConf ,
                     ConfParser.XmlFile: self.ParseXml }

        for ConfIter in ParseOrder:
            MapMethod[ConfIter]()

    def getConfig(self):
        Result={}
        for Name,Rec in self.Conf.items():
            if not Rec.CheckVal():
                raise ConfiguartionError("Parameter %s is missing or not valid" % Name )
            if 'InFlag' in Rec.Param:
                Result[Name]=Rec.get_Val()
        return Result

    def Usage(self,Description=None):
        PList=[]
        Result=[]
        for Param,PRec in self.Conf.items():
            MainName='|'.join(PRec.Param['Alias'])
            MainName='|'.join(("-%s" % Param,MainName,)) if MainName else "-%s" %  Param
            if 'Pattern' in PRec.Param: MainName += ' Value/s'
            ##Result.append('\n\t'.join((MainName,PRec.Describe(),)))
            #print "\n\nDebug - %s\n\n" % MainName
            if PRec.is_Requier():
                PList.insert(0,MainName)
            else:
                PList.append("[%s]" % MainName )
            Result.append('\n\t'.join((MainName,PRec.Describe(),)))
            #Result.extend((MainName,PRec.Describe(),))
        UsagStr="Usage: %s %s" % (sys.argv[0],' '.join(PList))
        if Description : Result.insert(0,Description)
        Result.insert(0,UsagStr)
        return Result

CLIPreffix=re.compile(r'-+(\S+)')
ConfFilePattern=re.compile(r'(.+?)\s*=\s*(.+)')

if __name__ == "main":
    print "Test Module:"
    MyConf=ConfParser(Stam={'mandatory' : True, 'Description' : "Test Param" ,'ValidPattern': r'\S+' } ,
                  ChkAlias={'Description': "Contains Aliases" , 'aliases' : ['Boom','Yofi','Help']} ,
                  IP={'Description' : "Check Pattern", 'ValidPattern': r'(\d+\.){3}\d+' })
    MyConf.ReadConfig([ConfParser.CLI,])
    print "Input Params:"
    for ii,kk in MyConf.getConfig().items():
        print "%-15s >> %20s" % (ii,kk)
    print "\n\n\n\n===================="
    for Line in MyConf.Usage(): print Line
#print MyConf.Usage()