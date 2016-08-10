__author__ = 'dkreda'

#!/usr/bin/python
######################
##  Check Remarks
###############

import sys,re

class BaseFile(object):
    def __init__(self,FileName):
        self.FileName=FileName
        self.ReadFile()

    def ReadFile(self):
        TmpFHandle=open(self.FileName)
        Line=TmpFHandle.read()
        TmpFHandle.close()
        self.Content=Line.splitlines()
    def WriteFile(self):
        TmpFHandle=open(self.FileName,"w")
        TmpFHandle.writelines("\n".join(self.Content))
        TmpFHandle.close()
        
class INIFile(BaseFile):
   SecPattern=re.compile(r"^\s*\[(.+)\]")
   ParamPattern=re.compile(r"(.+?)=(.+)")
   CommentPattern=re.compile(r"^\s*([#;]|$)")
   IniPathPattern=re.compile(r"\[(.+)\](\S+)")
   def __init__(self,FileName):
       BaseFile.__init__(self,FileName)
#       print( "Debug:")
#       for i in self.Content:
#            print(i)
#       print( "----------------------")
       self.SecMap={}
       self.Parse()
   def __CheckPathDecorator(Func):
        def Formater(self,*IniParams):
            InReg=self.IniPathPattern.match(IniParams[0])
            if InReg:
                 return Func(self,InReg.group(1),InReg.group(2),*IniParams[1:])
            # return (InReg.group(1),InReg.group(2))
            else:
                 return Func(self,*IniParams)
        return Formater
            #return (IniParams[0],IniParams[1])
   def Parse(self):
        Index=-1
        LastMatch=None
        for Line in self.Content:
            Index += 1
            if ( self.CommentPattern.match(Line) ):
                continue
            TmpRegx=self.SecPattern.match(Line)
            if ( TmpRegx ):
                if ( LastMatch ):
                    self.SecMap[LastMatch][1]= Index
                LastMatch=TmpRegx.group(1)
                self.SecMap[LastMatch]=[Index + 1, Index + 1]
        if ( LastMatch ):
            self.SecMap[LastMatch][1]=Index + 1
        ## print("Debug: " , self.SecMap)
       
   def Section(self,SecName):
       SRange=self.SecMap.get(SecName)
       if ( SRange ):
           return self.Content[SRange[0]:SRange[1]]
       else :
           return None
   def ParseSection(self,SecName):
        SecCon=self.SecMap.get(SecName)
        if not SecCon:
            return None
        TmpDict={}
        # for Index in xrange(SecCon[0],SecCon[1]): ## for Python2.7
        for Index in range(SecCon[0],SecCon[1]):
            if ( self.CommentPattern.match(self.Content[Index]) ):
                continue
            try:
                TmpRegex=self.ParamPattern.match(self.Content[Index])
                TmpDict[TmpRegex.group(1)]=[Index,TmpRegex.group(2)]
            except Exception as e:
                print("Error - Line %d at %s Line content:" % (Index,self.FileName),"\n\t\"%s\"" % self.Content[Index],type(TmpRegex))
        if len(SecCon) < 3:
            SecCon.extend([{}])
        SecCon[2]=TmpDict
   def __getSecRec(self,SecName):
        SecCont=self.SecMap.get(SecName)
        if not SecCont:
            return None
        if len(SecCont) < 3:
            self.ParseSection(SecName)
        return self.SecMap[SecName]
   def getParams(self,SecName):
        SecCont=self.__getSecRec(SecName)
        if not SecCont:
            return None
        return { PName : PRec[1] for PName,PRec in SecCont[2].items() }
   def __CheckPath(self,*IniParams):
        InReg=self.IniPathPattern.match(IniParams[0])
        if InReg:
            return (InReg.group(1),InReg.group(2))
        else:
            return (IniParams[0],IniParams[1])
   def __FindLineRec(self,SecName,Param):
        ParamsList=self.__getSecRec(SecName)
        if ( ParamsList ):
            Result=ParamsList[2].get(Param)
            return Result
        else:
            return None
               # def fineLine(self,IniPath,*IniExtra):

   @__CheckPathDecorator
   def fineLine(self,SecName,ParamName):
        #SecName,ParamName=self.__CheckPath(IniPath,*IniExtra)
        Result=self.__FindLineRec(SecName,ParamName)
        if Result :
            return Result[0]
        else:
            return None
               # def findValue(self,IniPath,*IniExtra):

   @__CheckPathDecorator
   def findValue(self,SecName,ParamName):
        ## SecName,ParamName=self.__CheckPath(IniPath,*IniExtra)
        Result=self.__FindLineRec(SecName,ParamName)
        if Result :
            return Result[1]
        else:
            return None
            
   def SetParam(self,IniPath,Value):
        SecName,ParamName=self.__CheckPath(IniPath)
        LNo=self.fineLine(SecName,ParamName)
        if LNo is None:
            Place=self.SecMap.get(SecName)
            #print("Debug - place: %s" % Place)
            #
            if Place is None:
                self.Content.extend(["[%s]" % SecName,"=".join((ParamName,Value))])
            else:
                #print("Debug Content size %d - Place (%s) value %d ...." % (len(self.Content),type(Place[1]),Place[1]))
                #self.Content.insert(Place[1],"Shalom=Ba")
                self.Content.insert(Place[1],"=".join((ParamName,str(Value))))
        else:
            self.Content[LNo]=re.sub("=.+$","=%s" % Value,self.Content[LNo])
        self.Parse()

if __name__ == "__main__":
    ## FName=raw_input("Enter File to read") ## for Python 2.7
    FName=input("Enter File to read")
    TestClass=INIFile(FName)
    print(TestClass.SecMap)
    ## Sec=raw_input("Enter Section:") ## for Python 2.7
    Sec=input("Enter Section:")
    print(TestClass.Section(Sec))
    print(TestClass.getParams(Sec))
    print (TestClass.findValue("test2","pp2"))
    print (TestClass.findValue("[test2]pp2"))
    print (TestClass.findValue("test2","mam"))
    print (TestClass.findValue("[test2]mam"))
    print (TestClass.findValue("test2","BoomBeemBam"))
    print (TestClass.findValue("test2","BoomBeemBam"))
    Stam=TestClass.FileName + ".Backup"
    F=open(Stam,"w")
    F.writelines( "\n".join(TestClass.Content))
    F.close()
    TestClass.SetParam("[test2]Yofi","Tofi")
    TestClass.SetParam("[New Section]Yofi","Tofi")
    ## TestClass.SetParam("New Section","Boom","Bam")
    TestClass.SetParam("[New Section]Beemba","shunra")
    TestClass.SetParam("[Sec with Spaces]par2","Tofi")
    print(TestClass.Content)
    print(TestClass.Section(Sec))
    print(TestClass.getParams(Sec))
    for i in TestClass.Content:
        print(i) 
    TestClass.WriteFile()