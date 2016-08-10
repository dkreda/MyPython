__author__ = 'dkreda'

import Ini
import xml.etree.ElementTree as XmlLib
import re,sys,time,os


class ParamRuleEq(object):

    def __init__(self,Rule,*ParamNameList):
        self.Rule=Rule
        self.pList=ParamNameList

    def verify(self,pVal):
        return self.Rule == pVal
    @property
    def Size(self):
        return len(self.pList)

    def Calc(self,pVal):
        return self.pList

class ParamRuleNotEq(ParamRuleEq):

    def verify(self,pVal):
        return self.Rule != pVal

class ParamRuleBigger(ParamRuleEq):

    def verify(self,pVal):
        return self.Rule > pVal

class ParamRuleLower(ParamRuleEq):

    def verify(self,pVal):
        return self.Rule < pVal

class ParamRuleReg(ParamRuleEq):
    pRep=re.compile('(^|[^\\\\])\$(\d+)')
    def verify(self,pVal):
        return True if re.search(self.Rule,pVal) else False

    def __subVals(self,pVal,MatchRec):
        #MatchRec=re.search()
        #pVal=""
        tmpMatch=ParamRuleReg.pRep.search(pVal)
        while tmpMatch:
            #print "Debug - Replace Reg grp Params ...." , tmpMatch.lastindex
            #print pVal , " .... " , tmpMatch.groups()
            for gNum in tmpMatch.groups():
            #for gNum in xrange(1 ,tmpMatch.lastindex + 1):
                if not gNum.isdigit(): continue
                repStr='$' + gNum
                #print "Check For" ,gNum ," (" , MatchRec.lastindex
                #print "Before:" , pVal
                pVal=re.sub(r'\\\$','<###>',pVal)
                #print "After :" ,pVal
                pVal=pVal.replace(repStr,MatchRec.group(int(gNum)))
                pVal=re.sub('<###>','\\\$',pVal)
            tmpMatch=ParamRuleReg.pRep.search(pVal)
        return pVal
        #while tmpMatch:
        #    repStr='$%s' % tmpMatch.

    def Calc(self,pVal):
        #print "Debug - Calculate Regular Expresion Rule"
        tmpMatch=re.search(self.Rule,pVal)
        #print "pList type is " ,self.Size , " >>>>" , ','.join(self.pList)
        result=[]
        for Num in xrange(self.Size):
            result.append(self.__subVals(self.pList[Num],tmpMatch))
            #self.pList[Num]=self.__subVals(self.pList[Num],tmpMatch)
        return result

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

class ParamParser():

    ParamPattern=re.compile('(.+?)=(.+?),([^,\:\/]{3})\:\/\/(.+?)\/([\/\[]+)(.+)')

    def __init__(self,Str):
        mRec=ParamParser.ParamPattern.match(Str)
        if mRec is None:
            raise SyntaxError('Ilegal parameter definition: "%s"' % Str)
        self.__Name=mRec.group(1)
        self.__UnitList=mRec.group(2)
        self.__Type=mRec.group(3)
        self.__FileName=mRec.group(4)
        self.__Path=mRec.group(6)
        if mRec.group(5)[len(mRec.group(5)) - 1 :] == '[' :
            self.__Path= '[' + self.__Path
    @property
    def ParamName(self):
        return self.__Name

    @property
    def Units(self):
        return self.__UnitList.split(',')

    @property
    def FileType(self):
        return self.__Type

    @property
    def ParamPath(self):
        return self.__Path

    @property
    def File(self):
        return self.__FileName

class Handler():
    RegEx_pPath=re.compile('(.+?)\/([\/\[]+)(.+)')
    #def __init__(self,pName,FilePath,pPath,pType,*unitList):
    def __init__(self,pName,pType,pPath,*unitList):
        self.__Name=pName
        self.__Type=pType
        self.__Units=unitList
        if pType == 'cmd' :
            self.__Path=pPath
            self.__File=None
        else:
            tmpMatch=Handler.RegEx_pPath.match(pPath)
            if tmpMatch:
                self.__File=tmpMatch.group(1)
                tmpStr=tmpMatch.group(2)
                tmp=tmpStr.find('[')
                if tmp < 0 : tmp=2
                self.__Path= tmpStr[tmp:] + tmpMatch.group(3)
            else:
                raise SyntaxError('fail to resolve file name or parameter path from "%s"' % pPath)

    @property
    def getParamName(self):
        return self.__Name

    @property
    def getParamPath(self):
        return self.__Path

    @property
    def getParamType(self):
        return self.__Type

    @property
    def getFileName(self):
        return self.__File

    def isInUnit(self,Unit):
        return Unit in self.__Units

class Manipulator():

    def __init__(self,pName,DepList,*Rules):
        self.__Name=pName
        self.__DepList=DepList
        self.__Rules=Rules
        ### just Validate Rules
        for sRule in Rules:
            if sRule.Size != len(DepList):
                raise SyntaxError('Manipulator of "%s" has at list one wrong Rule' % pName,
                                  'Depended number of items: %d, Rule Number of Items: %d ' % (len(DepList),sRule.Size),
                                  'Rule: %s' % ','.join(sRule.pList))


    def calculate(self,pVal):
        #self.__Rules=ParamRuleEq()
        for rIter in self.__Rules:
            if rIter.verify(pVal):
                return dict(zip(self.__DepList,rIter.Calc(pVal)))
        raise LookupError('Fail to find matching rule for "%s" (%s).' % (self.__Name,pVal))

    @property
    def paramName(self):
        return self.__Name

class FileHandler(object):

    def __init__(self,FilePath):
        #tmpFh=open(FilePath,'r')
        self.__FileName=FilePath
        #self.Content=tmpFh.readall()
        #tmpFh.close()

    @property
    def getFileName(self):
        return self.__FileName

    def Backup(self):
        IncNum=0
        bFile=self.__FileName + '.Backup.%f' % (time.time() + IncNum)
        while os.path.exists(bFile):
            IncNum += 1
            bFile=self.__FileName + '.Backup.%f' % (time.time() + IncNum)
        os.rename(self.__FileName,bFile)
        return bFile

    def setParam(self,pPath,pVal):
        pass



class FileHandler_Ini(FileHandler):

    def __init__(self,FilePath):
        super(FileHandler_Ini,self).__init__(FilePath)
        self.Handler=Ini.INIFile(FilePath)

    def setParam(self,pPath,pVal):
        self.Handler.SetParam(pPath,pVal)

    def Commit(self):
        if self.Backup():
            self.Handler.WriteFile()

class FileHandler_xml(FileHandler):
    def __init__(self,FilePath):
        #tmpFh=open(FilePath,'r')
        #self.Content=tmpFh.readall()
        #self.__FileName=FilePath
        super(FileHandler_xml,self).__init__(FilePath)
        self.Handler=XmlLib.parse(FilePath)
        self.Root=self.Handler.getroot()

    def setParam(self,pPath,pVal):
        #self.Root=XmlLib.ElementTree()
        XPath= '.' + pPath if pPath[0] == '/' else pPath
        for xmlIter in self.Root.findall(XPath):
            #xmlIter=XmlLib.Element()
            xmlIter.text=pVal

    def Commit(self):
        if self.Backup():
            self.Handler.write(self.getFileName)
        #pass

class FileHandler_txt(FileHandler):
    RegEx_txtParam=re.compile('(\[(.+?)\])*(.+)')

    def __init__(self,FilePath):
        super(FileHandler_txt,self).__init__(FilePath)
        tmpFh=open(FilePath,'r')
        #self.__FileName=FilePath
        self.Content=tmpFh.readlines()
        tmpFh.close()

    def setParam(self,pPath,pVal):
        tmpMatch=FileHandler_txt.RegEx_txtParam.match(pPath)
        pName=tmpMatch.group(3)
        switchs= tmpMatch.group(2) if tmpMatch.group(2) else 's '
        tmpMatch=re.search('([rab])(\S+)',switchs)
        if tmpMatch: # Replace Switch
            if tmpMatch.group(1) == 'r':
                repStr=tmpMatch.group(2)
                aStr=None
                bStr=None
            elif tmpMatch.group(1) == 'a':
                repStr=None
                aStr=tmpMatch.group(2)
                bStr=None
            elif tmpMatch.group(1) == 'b':
                repStr=None
                aStr=None
                bStr=tmpMatch.group(2)

            switchs=switchs.replace(tmpMatch.group(1) + tmpMatch.group(2) ,'')
            if switchs.find('v') < 0 : switchs += 'v '
        else:
            repStr=None
            aStr=None
            bStr=None

        tmpMatch=re.search('v(.)',switchs)
        vSep=tmpMatch.group(1) if tmpMatch else None
        tmpMatch=re.search('s(.)',switchs)
        pSep= tmpMatch.group(1) if tmpMatch else ' '
        lFlag=False if switchs.find('l') < 0 else True
        ChangeFlag=False
        for LineNum in xrange(len(self.Content)):
            lastPos=self.Content[LineNum].find(pName + pSep)
            if LineNum > 230:
                a=self.Content[LineNum]
                b=pName + pSep
                print "...."
            if lastPos < 0: continue
            if lastPos > 0 and not self.Content[LineNum][:lastPos].isspace() : continue
            Parts=self.Content[LineNum].split(pSep,1)
            print "Debug -- Find the Parameter at Line " , LineNum
            if repStr:
                Parts[1].replace(repStr,pVal)
            elif aStr:
                index=Parts[1].find(aStr)
                if index < 0 : index=len(Parts[1])
                index=Parts[1].find(vSep,index + len(aStr) - 1)
                if index <0 : index=len(Parts[1])
                Parts[1] = Parts[1][:index] + vSep + pVal + Parts[1][index:]
            elif bStr:
                index=Parts[1].find(bStr)
                if index <0 : index =0
                while index > 0 :
                    index -= 1
                    if Parts[1][index] == vSep : break
                Parts[1] = Parts[1][:index] + pVal + vSep + Parts[1][index:]
            elif vSep:
                Parts[1] = Parts[1].rstrip() + vSep + pVal +"\n" if lFlag else pVal + vSep + Parts[1]
            else:
                Parts[1]=pVal
            self.Content[LineNum]=pSep.join(Parts)
            ChangeFlag=True
        if not ChangeFlag: self.Content.append(pSep.join((pName,pVal + "\n")))

    def Commit(self):
        if self.Backup():
            tmpFh=open(self.getFileName,'w')
            tmpFh.write("".join(self.Content))
            tmpFh.close()



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
    #Level=enum('LogLevel',"Debug","Info","Warning","Error","Fatal")
    Level=BaseEnum("Debug","Info","Warning","Error","Fatal")
    def __init__(self,LogFile,ExposeLevel,Prefix=""):
        print Logger.Level
        self.Prefix=Prefix
        self.exLevel=ExposeLevel
        try:
            self.__fh=open(LogFile,'a') if LogFile else None
        except IOError , e:
            self.__fh=None
            self.WrLog(Logger.Level.Error,'Fail to open/write "%s"' % LogFile,"writing log to the screen only")


    def WrLog(self,level,*messages):
        if level >= self.exLevel:
            prefix= '%-7s- %s %s:' % (self.Level.getIndex(level),time.ctime(time.time()),self.Prefix)
            tmpStr= "\n" + ' ' * len(prefix)
            Message= prefix + tmpStr.join(messages)
            print Message
            if self.__fh :
                self.__fh.write(Message)
                self.__fh.write("\n")
                self.__fh.flush()

    def __del__(self):
        if self.__fh:
            self.__fh.close()

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
        tmpMatch=ParamDeployer.RegEx_HandlerStr.match(self.extractText(hStr))
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
                    if pType == 'txt':
                        FileH=FileHandler_txt(fName)
                        #FileH.setParam(pRec.getParamPath,self.Params[pRec.getParamName])
                    elif pType == 'ini':
                        FileH=FileHandler_Ini(fName)
                        #FileH.setParam(pRec.getParamPath,self.Params[pRec.getParamName])
                    elif pType == 'xml' :
                        FileH=FileHandler_xml(fName)
                        #FileH.setParam(pRec.getParamPath,self.Params[pRec.getParamName])
                    elif pType == 'cmd':
                        Log.WrLog(Logger.Level.Debug,"Command handler not implemented yet")
                    else:
                        Log.WrLog(Logger.Level.Error,"Unsuported File Type " + pRec.getParamType)
                        continue
                    #FileH=FileHandler(fName)
                except IOError , e:
                    self.__Log.WrLog(Logger.Level.Error,"Fail to open/read/write to %s" % fName ,
                                     e.strerror,e.message)
                    continue
                for pRec in pList:
                    if pType != 'cmd':
                        if pRec.isInUnit(Unit):
                            FileH.setParam(pRec.getParamPath,self.Params[pRec.getParamName])
                            self.__Log.WrLog(Logger.Level.Debug,"update %s in %s" %
                                             (pRec.getParamName,pRec.getFileName))
                    else:
                        self.__Log.WrLog(Logger.Level.Warning,"Running Command (Not Implemented)")
                if pType != 'cmd' : FileH.Commit()

    @property
    def Errors(self):
        return len(self.__ErrorList)

    def addMacros(self,**macros):
        for (mName,mVal) in macros.items():
            self.Macros[mName]=mVal
            #self.Macros[mName]=self.extractText(mVal)


    def extractText(self,Text):
        ## extract Macros ##
        LastMatch=ParamDeployer.RegEx_Macro.search(Text)
        while LastMatch:
            MacStr= '%$' + LastMatch.group(1) + '%'
            try:
                Text=Text.replace(MacStr,self.Macros[LastMatch.group(1)])
            except KeyError, e:
                raise KeyError('Undefined macro "%s" ' % LastMatch.group(1), e.message , e.args)
            LastMatch=ParamDeployer.RegEx_Macro.search(Text)
        ## extract Params ##
        LastMatch=ParamDeployer.RegEx_Param.search(Text)
        while LastMatch:
            ParamStr= '{%s}' % LastMatch.group(1)
            try:
                Text=Text.replace(ParamStr,self.Params[LastMatch.group(1)])
            except KeyError, e:
                raise KeyError('Undefined Parameter "%s" ' % LastMatch.group(1), e.message , e.args)
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

#ttt = re.match('(\d+)(.)(\d+)(\d+)(\d+)','055-6626')
#print ttt.lastindex
#print ttt.lastgroup
#print ttt.groups()
#a=time.time()
#for i in xrange(5):
#    a=time.time()
#    print "Backup.%f" % a
#print a,":",a.__class__
#sys.exit(0)

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
        RulePattern=re.compile('(.+?)=([=~><!])(.+)')
        DepList=IniParser.getParams('Octopus.Parameters.Mapping')
        for (pMainName,pDepName) in DepList.items():
            RuleList=[]
            #LineNum=0
            (Start,Stop)=IniParser.SecMap['Octopus.Parameters.Def.' + pMainName]
            for LineNum in xrange(Start,Stop):
                rLine=IniParser.Content[LineNum]
                if len(rLine) < 1 or rLine.isspace() or re.match('\s*#',rLine):
                        # Ignore comments or empty lines
                        continue
                try:
                    tmpMatch=RulePattern.match(rLine)
                    dList=tmpMatch.group(3)
                    if tmpMatch.group(2) == '=' :
                        RuleList.append(ParamRuleEq(tmpMatch.group(1),*dList.split(',')))
                    elif tmpMatch.group(2) == '!' :
                        RuleList.append(ParamRuleNotEq(tmpMatch.group(1),*dList.split(',')))
                    elif tmpMatch.group(2) == '>' :
                        RuleList.append(ParamRuleBigger(tmpMatch.group(1),*dList.split(',')))
                    elif tmpMatch.group(2) == '~' :
                        RuleList.append(ParamRuleReg(tmpMatch.group(1),*dList.split(',')))
                    elif tmpMatch.group(2) == '<' :
                        RuleList.append(ParamRuleLower(tmpMatch.group(1),*dList.split(',')))
                    else :
                        Log.WrLog(Logger.Level.Error,'Unsupported manipulation rule "%s" at Line %d:' %
                                  (tmpMatch.group(2),LineNum ,),rLine,"Ignore this Line")
                        continue
                except SyntaxError , e:

                    Log.WrLog(Logger.Level.Error,'bad Manipulation rules for "%s"' % pMainName ,
                              e.message, 'at Line %d' % LineNum)
                    print "??????????????????????"
                    continue
                    #raise SyntaxError("")
                #RuleList.append(ParamRuleEq(rLine))
                print "Debug - Checking " , rLine
            try:
                tmpManip=Manipulator(pMainName,pDepName.split(','),*RuleList)
                OctObj.addManipulator(tmpManip)
            except SyntaxError , e:
                Log.WrLog(Logger.Level.Error,'bad Manipulation rules for "%s" at Line %d:' %
                          (pMainName , Start) ,*e.args)
                continue


        ### Add Handlers:
        #aa=IniParser.Section('RealName.Parameters.Def')
        #RecPattern=re.compile('(.+),(\S{3}):\/\/(.+)')
        #ParamPattern=re.compile('(.+?)\/([\/\[]+)(.+)')
        for pName,pRec in IniParser.getParams('RealName.Parameters.Def').items():
            #print Record , xxx
            OctObj.addHandlerStr(pRec,pName)

        Log.WrLog(Logger.Level.Info,"Finish to parse File ...")
        Log.WrLog(Logger.Level.Info,"Start Parameters Manipulation")
        OctObj.ManipulatParams()
        Log.WrLog(Logger.Level.Info,"Start setting parameters in files.")
        OctObj.setParams(Conf['Unit'])

