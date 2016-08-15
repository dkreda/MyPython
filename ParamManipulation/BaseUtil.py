__author__ = 'dkreda'

import Ini
#import xml.etree.ElementTree as XmlLib
import re,sys,time,os
import subprocess



class BaseEnum():

    def __init__(self,*args):
        self.__Index= args
        count=0
        for name in args:
            setattr(self,name,count)
            count += 1

    def getIndex(self,num):
        if num < len(self.__Index):
            return self.__Index[num]

    @property
    def EnumSize(self):
        return len(self.__Index)

class ParamsSetter():

    def __init__(self,Unit,Log):
        self.__Unit=Unit
        self.Logger=Log
        self.Handlers={}

    def addSetting(self,paramName,HandlerType,pPath,FileName,*unitList):
        if self.__Unit in unitList:
            #a=dict()
            if not self.Handlers.has_key(HandlerType):
                self.Handlers[HandlerType][FileName]=Handler(FileName)
            elif not self.Handlers[HandlerType].has_key(FileName):
                self.Handlers[HandlerType][FileName]=Handler(FileName)
            self.Handlers[HandlerType][FileName].setParam(pPath)

class Logger():
    Level=BaseEnum("Debug","Info","Warning","Error","Fatal")
    def __init__(self,LogFile,ExposeLevel,Prefix=""):
        self.Prefix=Prefix
        self.exLevel=ExposeLevel
        try:
            self.__fh=open(LogFile,'a') if LogFile else None
        except IOError , e:
            self.__fh=None
            self.WrLog(Logger.Level.Error,'Fail to open/write "%s"' % LogFile,"writing log to the screen only")


    def WrLog(self,level,*messages):
        if level >= self.exLevel:
            prefix= '%-7s- %s %s:' % (self.Level.getIndex(level),time.ctime(time.time()),self.Prefix) \
                    if level < self.Level.EnumSize else ''
            tmpStr= "\n" + ' ' * len(prefix)
            Message= prefix + tmpStr.join(messages)
            print Message
            if self.__fh :
                self.__fh.write(Message)
                self.__fh.write("\n")
                self.__fh.flush()

    def Box(self,*messages,**keyargs):
        Size=keyargs.get('Size',-1)
        BoxCh=keyargs.get('BoxCh','#')
        if Size < 0 :
            for line in messages:
                if len(line) > Size: Size=len(line)
            Size
        BoxLines=[ '%s %*s %s' % (BoxCh,-Size,Mes,BoxCh) for Mes in messages ]
        #BoxLines=[]
        BoxLines.append(BoxCh * (Size + 4))
        BoxLines.insert(0,BoxCh * (Size + 4) )
        self.WrLog(self.Level.Fatal + 100,*BoxLines)

    def __del__(self):
        if self.__fh:
            self.__fh.close()

def FactoryHandler(hType,FileName):
    mapHandlers={ 'txt' : FileHandler_txt ,
                  'ini' : FileHandler_Ini ,
                  'xml' : FileHandler_xml }
    return mapHandlers[hType](FileName)

class ParamDeployer():
    RegEx_Macro=re.compile('%\$(.+?)%')
    RegEx_Param=re.compile('[^\\\\]{(\S+?)}')
    RegEx_HandlerStr=re.compile('(.+),(\S{3}):\/\/(.+)')
    def __init__(self,LogObj=None,**params):
        #print "Log INput: " , LogObj
        self.__Log=LogObj if LogObj else Logger(None,Logger.Level.Debug)
        self.Params=params
        self.Manipulators=[]
        self.Handlers={}
        self.Macros={}
        self.__ErrorList=[]

    def addManipulator(self,Manip):
        self.Manipulators.append(Manip)

    def addHandler(self,fileHandler):
        #fileHandler=Handler()
        if not self.Handlers.has_key(fileHandler.getParamType):
            self.Handlers[fileHandler.getParamType]= {fileHandler.getFileName: [] }
        elif not self.Handlers[fileHandler.getParamType].has_key(fileHandler.getFileName):
            self.Handlers[fileHandler.getParamType][fileHandler.getFileName]=[]
        self.Handlers[fileHandler.getParamType][fileHandler.getFileName].append(fileHandler)

    def addHandlerStr(self,hStr,pName):
        tmpMatch=ParamDeployer.RegEx_HandlerStr.match(self.extractMacros(hStr))
        if tmpMatch:
            unitList=tmpMatch.group(1)
            hType=tmpMatch.group(2)
            param=tmpMatch.group(3)
            self.addHandler(Handler(pName,hType,param,*unitList.split(',')))
        else:
            self.__Log.WrLog(Logger.Level.Fatal,hStr)
            raise SyntaxError("Ilegal parameter definition:",hStr)

    def setParams(self,Unit):
        self.__Log.WrLog(Logger.Level.Debug,"set Values to files/Execute for Unit %s" % Unit)
        for (pType,File) in self.Handlers.items():
            self.__Log.WrLog(Logger.Level.Debug,"setting %s files" % pType)
            #for pRec in File:
            for (fName,pList) in File.items():
                # Todo - Update the correct Handler (acording to file type)
                # Fix the paramPath + Fname to be extract ....
                #pRec=Handler()
                self.__Log.WrLog(Logger.Level.Debug,"setting %s" % fName)

                try:
                    FileH = FactoryHandler(pType, fName)
                except IOError , e:
                    self.Error("Fail to open/read/write to %s" % fName ,e.strerror,e.message)
                    continue
                except KeyError , e1:
                    if e1.message != 'cmd' :
                        self.Error("Unsupported file type " + e1.message)
                        continue
                for pRec in pList:
                    #pRec=Handler()
                    if pRec.isInUnit(Unit) and self.Params[pRec.getParamName] != '$Null' :
                        if pType == 'cmd':
                            cmdStr=self.extractText(pRec.getParamPath)
                            self.__Log.WrLog(Logger.Level.Info,'Exxcute: %s' % cmdStr)

                            Proc = subprocess.Popen(cmdStr, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                                    shell=True)
                            (sout, serr) = Proc.communicate()
                            Proc.wait()
                            if Proc.returncode:
                                self.Error(*sout.split(os.linesep))
                                self.Error("** Last command Finished with exit code %d" % Proc.returncode )
                            else:
                                self.__Log.WrLog(Logger.Level.Debug,*sout.split(os.linesep))
                        else: # regular File Handler
                            FileH.setParam(pRec.getParamPath, self.Params[pRec.getParamName])
                            self.__Log.WrLog(Logger.Level.Debug, "update %s in %s" %
                                     (pRec.getParamName, pRec.getFileName))
                if pType != 'cmd' : FileH.Commit()

    @property
    def Errors(self):
        return len(self.__ErrorList)

    def addMacros(self,**macros):
        for (mName,mVal) in macros.items():
            self.Macros[mName]=mVal
            #self.Macros[mName]=self.extractText(mVal)

    def Error(self,*messages):
        self.__ErrorList.append(messages[0])
        self.__Log.WrLog(Logger.Level.Error,*messages)

    def extractMacros(self,Text):
        LastMatch = ParamDeployer.RegEx_Macro.search(Text)
        while LastMatch:
            MacStr = '%$' + LastMatch.group(1) + '%'
            try:
                Text = Text.replace(MacStr, self.Macros[LastMatch.group(1)])
            except KeyError, e:
                raise KeyError('Undefined macro "%s" ' % LastMatch.group(1), e.message, e.args)
            LastMatch = ParamDeployer.RegEx_Macro.search(Text)
        return Text

    def extractText(self,Text):
        ## extract Macros ##
        Text=self.extractMacros(Text)
        ## extract Params ##
        LastMatch=ParamDeployer.RegEx_Param.search(Text)
        while LastMatch:
            ParamStr= '{%s}' % LastMatch.group(1)
            try:
                Text=Text.replace(ParamStr,self.Params[LastMatch.group(1)])
            except KeyError, e:
                for pn,pv in self.Params.items():
                    print '%-13s %17s' % (pn,pv)
                raise KeyError('Undefined Parameter "%s", resolving "%s"' % (LastMatch.group(1),Text), e.message , e.args)
            LastMatch=ParamDeployer.RegEx_Param.search(Text)
        Text=Text.replace('\\{','{')
        return Text

    def extractLine(self,Line):
        NewLine=Line.split('=',1)
        if len(NewLine)<2 : return Line
        NewLine[1]=self.extractText(NewLine[1])
        return '='.join(NewLine)

    def ManipulatParams(self):
        self.__Log.WrLog(Logger.Level.Debug,"Start Manipulating Parameters")
        for ManRule in self.Manipulators:
            #ManRule=Manipulator()
            pVal=self.Params[ManRule.paramName]
            for (pName,rVal) in ManRule.calculate(pVal).items():
                self.Params[pName]=self.extractText(rVal)
                self.__Log.WrLog(Log.Level.Info,'set "%s" to %s' % (pName,self.Params[pName]))
                #print "set param " , pName , " to " , self.Params[pName]

def ReadCLI():
    Pattern=re.compile("-+(.+)")
    Result={}
    Vals=[]
    Last=None
    for arg in sys.argv:
        RegResult=Pattern.match(arg)
        if RegResult:
            if Last is not None:
                if len(Vals) > 0:
                    Result[Last]= Vals if len(Vals) > 1 else Vals[0]
                else:
                    Result[Last]=None
            Last = RegResult.group(1)
            Vals=[]
        else:
            Vals.append(arg)
    if len(Vals) > 0:
        Result[Last]= Vals if len(Vals) > 1 else Vals[0]
    else:
        Result[Last]=None
    return  Result


if __name__ == '__main__':
    Conf=ReadCLI()
    Log=Logger(Conf.get('LogFile',""),Logger.Level.Debug)

    Mes=[]
    for (name,rec) in Conf.items():
        Mes.append("%-6s: %s" % (str(name), rec if type(rec) is str else ','.join( [''] if rec is None else rec) ))
        #print "%-6s: %s" % (str(name), rec if type(rec) is str else ','.join( [''] if rec is None else rec) )
    Log.WrLog(Logger.Level.Debug,*Mes)
    if Conf.has_key('Conf'):
        Log.WrLog(Logger.Level.Info,"Read Configuration %s" % Conf['Conf'])
        IniParser=Ini.INIFile(Conf['Conf'])
        Params=IniParser.getParams('Octopus.Parameters.Values')
        Log.WrLog(Logger.Level.Debug,"Parameters:" ,
                  *["%s: %s" % (a,b) for (a,b) in Params.items() ])
        Log.WrLog(Logger.Level.Debug,"==============================")
        OctObj=ParamDeployer(**Params)
        ## Parse Macros
        Macros=IniParser.getParams('Macros')
        OctObj.addMacros(**Macros)
        ## Parse / Add Manipulation Rules
        #RulePattern=re.compile('(.+?)=([=~><!])(.+)')
        DepList=IniParser.getParams('Octopus.Parameters.Mapping')
        for (pMainName,pDepName) in DepList.items():

            RuleList=[]
            #LineNum=0
            tmpManipulator=Manipulator(pMainName,pDepName.split(','))
            (Start,Stop)=IniParser.SecMap['Octopus.Parameters.Def.' + pMainName]
            for LineNum in xrange(Start,Stop):
                rLine=IniParser.Content[LineNum]
                if len(rLine) < 1 or rLine.isspace() or re.match('\s*#',rLine):
                        # Ignore comments or empty lines
                        continue
                try:
                    tmpManipulator.addRule(Manipulator.FactoryRule(rLine))
                except SyntaxError , e:
                    OctObj.Error('bad Manipulation rules for "%s" at line %d' % (pMainName,LineNum) , e.message)
                    continue
                print "Debug - Checking " , rLine
            try:
#                tmpManip=Manipulator(pMainName,pDepName.split(','),*RuleList)
                OctObj.addManipulator(tmpManipulator)
            except SyntaxError , e:
                OctObj.Error('bad Manipulation rules for "%s" at Line %d:' % (pMainName , Start) ,*e.args)
                continue


        ### Add Handlers:
        for pName,pRec in IniParser.getParams('RealName.Parameters.Def').items():
            #print Record , xxx
            OctObj.addHandlerStr(pRec,pName)

        Log.WrLog(Logger.Level.Info,"Finish to parse File ...")
        Log.WrLog(Logger.Level.Info,"Start Parameters Manipulation")
        OctObj.ManipulatParams()
        Log.WrLog(Logger.Level.Info,"Start setting parameters in files.")
        OctObj.setParams(Conf['Unit'])
        Log.WrLog(Logger.Level.Info,"Deploy Parameters Finished " + ("With Errors (see log)" if OctObj.Errors else
                  "Succesfully :-)") )
        sys.exit(OctObj.Errors)

