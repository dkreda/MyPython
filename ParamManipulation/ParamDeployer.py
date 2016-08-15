__author__ = 'dkreda'

__author__ = 'dkreda'

import Ini
from BaseUtil import Logger as LG
import BaseUtil as Base
import xml.etree.ElementTree as XmlLib
import re,sys,time,os
import subprocess


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

class Handler():
    RegEx_pPath=re.compile('(.+?)\/([\/\[]+)(.+)')
    #
    #def __init__(self,pName,FilePath,pPath,pType,*unitList):
    def __init__(self,pName,pType,pPath,*unitList,**kwargs):
        self.__Name=pName
        self.__Type=pType
        self.__Units=unitList
        self.MetaData=kwargs
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
            elif pType == 'farm':
                self.__Path=pPath
                self.__File="/usr/cti/conf/balancer/balancer.conf"
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
    opMapping= { '=' : ParamRuleEq ,
                 '!' : ParamRuleNotEq ,
                 '~' : ParamRuleReg ,
                 '>' : ParamRuleBigger ,
                 '<' : ParamRuleLower }
    def __init__(self,pName,DepList,*Rules):
        self.__Name=pName
        self.__DepList=DepList
        self.__Rules=list(Rules)
        ### just Validate Rules
        for sRule in Rules:
            self.validateRule(sRule)

    def calculate(self,pVal):
        #self.__Rules=ParamRuleEq()
        for rIter in self.__Rules:
            if rIter.verify(pVal):
                return dict(zip(self.__DepList,rIter.Calc(pVal)))
        raise LookupError('Fail to find matching rule for "%s" (%s).' % (self.__Name,pVal))

    @property
    def paramName(self):
        return self.__Name

    def addRule(self,Rule):
        if self.validateRule(Rule):
            self.__Rules.append(Rule)

    def validateRule(self,Rule):
        #Rule=ParamRuleEq()
        if Rule.Size != len(self.__DepList):
            raise SyntaxError('Manipulator of "%s" has at list one wrong Rule' % self.paramName,
                              'Depended number of items: %d, Rule Number of Items: %d ' % (len(DepList), Rule.Size),
                              'Rule: %s' % ','.join(Rule.pList))
        else: return True

    ## static Method
    @staticmethod
    def FactoryRule(RuleStr):
        RulePattern=re.match('(.+?)=([%s])(.+)' % ''.join(Manipulator.opMapping.keys()) , RuleStr)
        if RulePattern:
            uList=RulePattern.group(3).split(',')
            return Manipulator.opMapping[RulePattern.group(2)](RulePattern.group(1),*uList)
        else:
            raise SyntaxError('Unsupported manipulation rule "%s"' % RuleStr)

class FileHandler(object):

    def __init__(self,FilePath,DebugLog=None):
        self.__FileName=FilePath
        self.__Debug=DebugLog

    @property
    def getFileName(self):
        return self.__FileName

    def Backup(self):
        IncNum=0
        bFile=self.__FileName + '.Backup.%f' % (time.time() + IncNum)
        while os.path.exists(bFile):
            IncNum += 1
            bFile=self.__FileName + '.Backup.%f' % (time.time() + IncNum)
        self._WrLog('Backup "%s"' % self.__FileName , 'to restore the original use %s' % bFile)
        os.rename(self.__FileName,bFile)
        return bFile

    def _WrLog(self,*messages):
        if self.__Debug:
            #self.__Debug=LG()
            self.__Debug.WrLog(LG.Level.Debug,*messages)
        else:
            print "\n".join(messages)

    def setParam(self,pPath,pVal):
        self._WrLog("abstract function nt implemented ...")
        pass

class FileHandler_Ini(FileHandler):

    def __init__(self,FilePath,DebugLog=None):
        super(FileHandler_Ini,self).__init__(FilePath,DebugLog)
        self.Handler=Ini.INIFile(FilePath)

    def setParam(self,pPath,pVal):
        self._WrLog('Update "%s"' % pPath)
        self.Handler.SetParam(pPath,pVal)

    def Commit(self):
        if self.Backup():
            self.Handler.WriteFile()

class FileHandler_xml(FileHandler):
    def __init__(self,FilePath,DebugLog=None):
        super(FileHandler_xml,self).__init__(FilePath,DebugLog)
        self.Handler=XmlLib.parse(FilePath)
        self.Root=self.Handler.getroot()

    def setParam(self,pPath,pVal):
        XPath= '.' + pPath if pPath[0] == '/' else pPath
        for xmlIter in self.Root.findall(XPath):
            #xmlIter=XmlLib.Element()
            self._WrLog('Update "%s"' % xmlIter.tag )
            xmlIter.text=pVal

    def Commit(self):
        if self.Backup():
            self.Handler.write(self.getFileName)
        #pass

class FileHandler_txt(FileHandler):
    RegEx_txtParam=re.compile('(\[(.+?)\])*(.+)')

    def __init__(self,FilePath,DebugLog=None):
        super(FileHandler_txt,self).__init__(FilePath,DebugLog)
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
            ## This section is just fro debug purpose (catch text line
            if LineNum > 930:
                a=self.Content[LineNum]
                b=pName + pSep
                print "...."
            ### End of Debug section
            if lastPos < 0: continue
            if lastPos > 0 and not self.Content[LineNum][:lastPos].isspace() : continue
            Parts=self.Content[LineNum].split(pSep,1)
            #print 'Debug -- Find "%s" at Line %d' % (pName,LineNum)
            self._WrLog('Find "%s" at line %d' % (pName,LineNum,))
            if vSep and re.search('(^|%s)%s(%s|$)' % (vSep,pVal,vSep),Parts[1]):
                ## if value alreday exists ignore - nochange is done
                #print 'Debug ... (Text - Handler) No Change is done to "%s" value already exists' % pName
                self._WrLog('No Change is done to "%s" value already exists' % pName)
                ChangeFlag=True
                continue
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

class FileHandler_farm(FileHandler):
    RegEx_farm=re.compile(r'([^:]+)(:(\d+))?')

    def __init__(self,FilePath,DebugLog=None):
        super(FileHandler_farm,self).__init__(FilePath,DebugLog)
        self.Handler=Ini.INIFile(FilePath)

    def setParam(self,pPath,pVal):
        tmpMatch=self.RegEx_farm.match(pPath)
        farmName=tmpMatch.group(1)
        Port= tmpMatch.group(3) if tmpMatch.groups() >= 3 else None
        self._WrLog('Update farm "%s"' % farmName)
        ## Build Farm Addresses
        sList=[]
        for ipAddress in re.split(r'[,;]',pVal):
            sList.append('server%d=%s,A,' % (len(sList) + 1,ipAddress,))


        secName='farm=' + farmName
        if secName in self.Handler.SecMap.keys():
            self._WrLog('Update farm "%s"' % farmName)
            (StartLine,EndLine)=self.Handler.SecMap[secName]
            StartDel=EndLine
            StopDel=StartLine
            for indx in xrange(StartLine,EndLine):
                if re.match('server',self.Handler.Content[indx]) :
                    if indx < StartDel : StartDel=indx
                    if indx > StopDel : StopDel = indx

            self.Handler.Content = self.Handler.Content[:StartDel] + sList +  self.Handler.Content[StopDel + 1:]
        else:
            self.Handler.Content.append('')
            self.Handler.Content.append('[%s]' % secName)
            self.Handler.Content += sList

        self.Handler.Parse()
        if Port:
            self.Handler.SetParam('[%s]port' % secName , Port)

    def Commit(self):
        if self.Backup():
            self.Handler.WriteFile()


def FactoryHandler(hType,FileName,Log=None):
    mapHandlers={ 'txt' : FileHandler_txt ,
                  'ini' : FileHandler_Ini ,
                  'xml' : FileHandler_xml ,
                  'farm' : FileHandler_farm}
    return mapHandlers[hType](FileName,Log)

class ParamDeployer():
    RegEx_Macro=re.compile('%\$(.+?)%')
    RegEx_Param=re.compile('[^\\\\]{(\S+?)}')
    RegEx_HandlerStr=re.compile('(.+),(\S+?):\/\/(.+)')
    def __init__(self,LogObj=None,**params):
        #print "Log INput: " , LogObj
        self.__Log=LogObj if LogObj else LG(None,LG.Level.Debug)
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

    def addHandlerStr(self,hStr,pName,**keyargs):
        tmpMatch=ParamDeployer.RegEx_HandlerStr.match(self.extractMacros(hStr))
        if tmpMatch:
            unitList=tmpMatch.group(1)
            hType=tmpMatch.group(2)
            param=tmpMatch.group(3)
            self.addHandler(Handler(pName,hType,param,*unitList.split(',')))
        else:
            ErrMessage='Illegal parameter definition "%s":' % pName
            self.__Log.WrLog(LG.Level.Fatal,ErrMessage,hStr)
            raise SyntaxError(ErrMessage + hStr)

    def setParams(self,Unit):
        self.__Log.WrLog(LG.Level.Debug,"set Values to files/Execute for Unit %s" % Unit)
        for (pType,File) in self.Handlers.items():
            self.__Log.WrLog(LG.Level.Debug,"setting %s files" % pType)
            #for pRec in File:
            for (fName,pList) in File.items():
                # Todo - Update the correct Handler (acording to file type)
                # Fix the paramPath + Fname to be extract ....
                #pRec=Handler()
                self.__Log.WrLog(LG.Level.Debug,"setting %s" % fName)

                try:
                    FileH = FactoryHandler(pType, fName,self.__Log)
                except IOError , e:
                    self.Error("Fail to open/read/write to %s" % fName ,e.strerror,e.message)
                    continue
                except KeyError , e1:
                    if e1.message != 'cmd' :
                        LineNo=pList[0].get_attr('LineNo',None)
                        if LineNo:
                            mes='at Line %d' % LineNo
                        self.Error("Unsupported file type " + e1.message)
                        continue
                for pRec in pList:
                    #pRec=Handler()
                    if pRec.isInUnit(Unit) and self.Params[pRec.getParamName] != '$Null' :
                        if pType == 'cmd':
                            cmdStr=self.extractText(pRec.getParamPath)
                            self.__Log.WrLog(LG.Level.Info,'Exxcute: %s' % cmdStr)

                            Proc = subprocess.Popen(cmdStr, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                                    shell=True)
                            (sout, serr) = Proc.communicate()
                            Proc.wait()
                            if Proc.returncode:
                                self.Error(*sout.split(os.linesep))
                                self.Error("** Last command Finished with exit code %d" % Proc.returncode )
                            else:
                                self.__Log.WrLog(LG.Level.Debug,*sout.split(os.linesep))
                        else: # regular File Handler
                            FileH.setParam(pRec.getParamPath, self.Params[pRec.getParamName])
                            self.__Log.WrLog(LG.Level.Debug, "update %s in %s" %
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
        self.__Log.WrLog(LG.Level.Error,*messages)

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
        self.__Log.WrLog(LG.Level.Debug,"Start Manipulating Parameters")
        for ManRule in self.Manipulators:
            #ManRule=Manipulator()
            pVal=self.Params[ManRule.paramName]
            for (pName,rVal) in ManRule.calculate(pVal).items():
                self.Params[pName]=self.extractText(rVal)
                self.__Log.WrLog(Log.Level.Info,'set "%s" to %s' % (pName,self.Params[pName]))
                #print "set param " , pName , " to " , self.Params[pName]


if __name__ == '__main__':
    Conf=Base.ReadCLI()
    Log=LG(Conf.get('LogFile',""),LG.Level.Debug)
    #Log.Box('This is my First message ...')
    Mes=['Start ParamDeployer. Input CLI:']
    for (name,rec) in Conf.items():
        Mes.append("%-6s: %s" % (str(name), rec if type(rec) is str else ','.join( [''] if rec is None else rec) ))
        #print "%-6s: %s" % (str(name), rec if type(rec) is str else ','.join( [''] if rec is None else rec) )
    #Log.WrLog(LG.Level.Debug,*Mes)
    Log.Box(*Mes,Size=60,BoxCh='*')
    if Conf.has_key('Conf'):
        Log.WrLog(LG.Level.Info,"Read Configuration %s" % Conf['Conf'])
        IniParser=Ini.INIFile(Conf['Conf'])
        Params=IniParser.getParams('Octopus.Parameters.Values')
        Log.WrLog(LG.Level.Debug,"Parameters:" ,
                  *["%s: %s" % (a,b) for (a,b) in Params.items() ])
        Log.WrLog(LG.Level.Debug,"==============================")
        OctObj=ParamDeployer(**Params)
        ## Parse Macros
        Macros=IniParser.getParams('Macros')
        OctObj.addMacros(**Macros)
        ## Parse / Add Manipulation Rules
        #RulePattern=re.compile('(.+?)=([=~><!])(.+)')
        DepList=IniParser.getParams('Octopus.Parameters.Mapping')
        for (pMainName,pDepName) in DepList.items():
            Log.WrLog(LG.Level.Debug,"Build Manipulation Rule for " + pMainName)
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
                #print "Debug - Checking " , rLine
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

        Log.WrLog(LG.Level.Info,"Finish to parse File ...")
        Log.WrLog(LG.Level.Info,"Start Parameters Manipulation")
        OctObj.ManipulatParams()
        Log.WrLog(LG.Level.Info,"Start setting parameters in files.")
        OctObj.setParams(Conf['Unit'])
        Log.WrLog(LG.Level.Info,"Deploy Parameters Finished " + ("With Errors (see log)" if OctObj.Errors else
                  "Succesfully :-)") )
        sys.exit(OctObj.Errors)

