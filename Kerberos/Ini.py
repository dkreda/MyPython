#!/usr/bin/python
######################
##  Check Remarks
#  This is Generic module which handle Reading and writing Ini files.
#
# 2 Main Classes are used:
# BaseFile class - which read and write raw data (ASCII) - it loads all the file to memory
# INIFile class - handle Ini Files
###############

import sys,re

class BaseFile(object):
    ### This is basic File Handle that Rerad Ascii file to memory and save it
    def __init__(self,FileName):
        self.FileName=FileName
        self.ReadFile()
    def ReadFile(self):
       print "Debug Going to read from %s" % self.FileName
       TmpFHandle=open(self.FileName)
       ##self.Content=[Line.strip() for Line in TmpFHandle.readlines()]
       self.Content=TmpFHandle.readlines()
       ##self.Content=[Line.rstrip() for Line in TmpFHandle.readlines()]
       TmpFHandle.close()
    def WriteFile(self):
        TmpFHandle=open(self.FileName,"w")
        TmpFHandle.writelines("\n".join(self.Content))
        TmpFHandle.close()

class Section(object):
    SecPattern=re.compile(r"^\s*\[(.+)\]")
    ParamPattern=re.compile(r"(.+?)=(.+)")
    IgnorePattern=re.compile(r"\s*(#|$)")
    def __init__(self,StartLine,EndLine,ContentArray):
        Flag=re.match(r'\[(.+)\]',ContentArray[StartLine])
        if Flag:
            self.__Cont=ContentArray
            self.__Name=Flag.group(1)
            self.__Start=StartLine +1
            self.__End=EndLine
            self.__ChangeFlage=False
            self.Parse()
        else:
            raise Exception("Line %d is not section Title." % StartLine)
    def Parse(self):
        self.__ParamIndex={}
        for LineNo in xrange(self.__Start,self.__End + 1):
            Flag = self.IgnorePattern.match(self.__Cont[LineNo])
            if Flag : continue
            Flag = self.ParamPattern.match(self.__Cont[LineNo])
            self.__ParamIndex[Flag.group(1)] = [LineNo,Flag.group(2)]
        self.__ChangeFlage=False

    def __setitem__(self, key, value):
        self.__Cont[self.__ParamIndex[key][0]]= "%s\n" % '='.join((key,value,))
        self.__ParamIndex[key][1]=value
        self.__ChangeFlage=True

    def __getitem__(self, item):
        return self.__ParamIndex[item][1]

    def getLineNo(self,ParamName):
        return self.__ParamIndex[ParamName][0]

    def __contains__(self, item):
        return item in self.__ParamIndex

    def __iter__(self):
        for ParamName,ParamVal in self.__ParamIndex.items():
            yield ParamName,ParamVal

    @property
    def Changed(self):
        return self.__ChangeFlage

    @property
    def Name(self):
        return self.__Name

    def AddParam(self,ParamName,ParamVal):
        if ParamName in self.__ParamIndex:
            raise Exception("Parameter %s already exists at section %s" % (ParamName,self.__Name))
        self.__Cont.insert(self.__End+1,"%s\n" % "=".join((ParamName,ParamVal,)))
        self.__ChangeFlage=True

class INIFile(BaseFile):

   IniPathPattern=re.compile(r"\[(.+)\](\S+)")
   def __init__(self,FileName):
       # print "Debug - IniFile Init"
       super(INIFile,self).__init__(FileName)
       self.__Parse()
       #print "Debug - End of INIFile Init ...."
       
   def __Parse(self):
       self.__SecMap={}
       LastMatch=None
       for LineNo in xrange(len(self.Content)):
           if Section.IgnorePattern.match(self.Content[LineNo]): continue
           Flag=Section.SecPattern.match(self.Content[LineNo])
           if Flag:
               if LastMatch is not None:
                   Tmp=Section(LastMatch,LineNo - 1,self.Content)
                   self.__SecMap[Tmp.Name]=Tmp
               LastMatch = LineNo
       if LastMatch is not None:
            Tmp=Section(LastMatch,len(self.Content) - 1,self.Content)
            self.__SecMap[Tmp.Name]=Tmp

   @property
   def Changed(self):
       return reduce(lambda x,y:  x or y.Changed , self.__SecMap.values() , False )

   def getSection(self,SecName):
       return self.__SecMap[SecName]

   def getSecList(self):
       return self.__SecMap.keys()

   def __getitem__(self, item):
       Flag=self.IniPathPattern.match(item)
       if Flag:
           return self.__SecMap[Flag.group(1)][Flag.group(2)]
       else:
           raise Exception("Ilegal Ini Path Pattern %s" % item)

   def __setitem__(self, key, value):
       Flag=self.IniPathPattern.match(key)
       if Flag:
           SecName=Flag.group(1)
           ParamName=Flag.group(2)
           if ParamName in self.__SecMap[SecName]:
                self.__SecMap[SecName][ParamName]=value
           else:
                self.__SecMap[SecName].AddParam(ParamName,value)
       else:
           raise Exception("Ilegal Ini Path Pattern %s" % key)

   def FindAllParams(self,Pattern):
       Result=[]
       for SecName,SecRec in self.__SecMap.items():
           SecMatchList=[ r'[%s]%s' % (SecName,PName,) for PName,Pv in SecRec if re.search(Pattern,PName) ]
           Result.extend(SecMatchList)
       return Result

   def WriteFile(self):
       if self.Changed:
           self.__Parse()
           super(INIFile,self).WriteFile()

class MultiIni(object):
    def __init__(self,*IniFiles):
        self.IniObjList=[ INIFile(FileName) for FileName in IniFiles ]
    def Section(self,SecName):
        Result=[]
        for IniObj in self.IniObjList:
            Tmp=IniObj.Section(SecName)
            if Tmp:
                Result.extend(Tmp)
        return Result
    def getParams(self,SecName):
        Result={}
        for IniObj in self.IniObjList:
            Tmp=IniObj.getParams(SecName)
            if Tmp:
                Result.extend(Tmp)
        return Result

if __name__ == "__main__":
    FName=raw_input("Enter File to read: ")
    while FName:
        TestClass=BaseFile(FName)
        print TestClass.Content[0]
        FName=raw_input("Enter File to read: ")
    FName=raw_input("Enter Ini File to read:")
    TestClass=INIFile(FName)
    print "List of Sections:\n -%s" % '\n -'.join(TestClass.getSecList())
    Sec=raw_input("Enter Section:")
    Pattern=raw_input("Enter Parameter Pattern:")
    print "List of all Match at section %s :" % Sec
    Tmp=TestClass.FindAllParams(Pattern)
    print '\n'.join(Tmp)
    print "Param Value of %s" % Tmp[-1]
    print TestClass[Tmp[-1]]

    print "Does File Changed %s" % TestClass.Changed

    TestClass['[test2]Yofi']="This is New Value for Exising Parameter"
    TestClass['[test2]NewParam']="New Parameter in this Section !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"

    print "".join(TestClass.Content)

    print "\n\nDoes File Changed %s" % TestClass.Changed
    TestClass.SetParam("[test2]Yofi","Tofi")
    TestClass.SetParam("test2","Bilby","Tofi")
    TestClass.SetParam("test2","ok",6)
    TestClass.SetParam("[New Section]Yofi","Tofi")
    TestClass.SetParam("[Sec with Spaces]par2","Tofi")
    print TestClass.Content
    print TestClass.Section(Sec)
    print TestClass.getParams(Sec)
    for i in TestClass.Content:
        print i 
    TestClass.WriteFile()