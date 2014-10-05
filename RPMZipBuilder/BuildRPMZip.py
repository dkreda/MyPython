__author__ = 'danielk'

import sys,re,zipfile,os
import hashlib

###############################################################################
#
# This script should help build RPM zip file
#
###############################################################################

def ExtarctVer(FullPath):
    MatchPattern=re.search('([^\\\/]+)$',FullPath)
    if not MatchPattern: return None
    FileName=MatchPattern.group(1)
    MatchPattern=re.match('(\D+)[\-_]([\d\-\._]+)\..*rpm',FileName)
    return [MatchPattern.group(2),MatchPattern.group(1)] if MatchPattern else ["",FileName]

def BaseName(FullPath):
    Tmp=ExtarctVer(FullPath)
    return Tmp[1] if Tmp else Tmp
    #MatchPattern=re.search('([^\\\/]+)$',FullPath)
    #if not MatchPattern: return None
    #FileName=MatchPattern.group(1)
    #MatchPattern=re.match('(\D+)[\-_]\d.+rpm',FileName)
    #return MatchPattern.group(1) if MatchPattern else FileName

class Config(object):
    SecPattern=re.compile('\[(.+)\]')
    CommentPattern=re.compile('\s*(#|$)')
    def __init__(self,FileName):
        self.__ConfFile=FileName
        self.__ReadFile()

    def __ReadFile(self):
        self.Target=None
        self.RpmList=[]
        File=open(self.__ConfFile)
        Lines=[ Str.rstrip("\n") for Str in File.readlines()]
        File.close()
        for Line in Lines:
            if self.CommentPattern.match(Line): continue
            MatchStr=self.SecPattern.match(Line)
            if MatchStr:
                Section=MatchStr.group(1)
            elif Section == "Target":
                self.Target=Line
            elif Section == "List":
                self.RpmList.append(Line)
            else:
                raise Exception("Error - Unknown section %s or definition with out preffix section definition at file %s" %
                                (Section,self.__ConfFile))

    @property
    def TargetZip(self):
        return self.Target

class TargetZip(object):
    def __init__(self,ZipFile):
        self.Target=ZipFile
        self.__AddList=[]
        self.__DelList=[]
        if os.path.exists(ZipFile):
            self.__zip=zipfile.ZipFile(ZipFile)
            self.__zip.close()
        else:
            self.__zip=None

    @property
    def ZipName(self):
        return self.Target

    def AddMember(self,FileName):
        self.__AddList.append(FileName)
        #self.__zip.write(FileName)
        #print "Debug --- New Member added !(%s)" % FileName

    def ReplaceMember(self,FileName):
        BaseItem=BaseName(FileName)
        for ZipMem in self.__zip.namelist():
            if BaseItem == BaseName(ZipMem):
                self.__DelList.append(ZipMem)
                self.__AddList.append(FileName)
                break
#            else:
#                print "Not Match %20s %s" % (BaseItem,BaseName(ZipMem))

    def Version(self,Item):
        BaseItem=BaseName(Item)
        for ZipMem in self.__zip.namelist():
            VerList=ExtarctVer(ZipMem)
            if not VerList: continue
            if VerList[1] == BaseItem:
                return VerList[0]
        return None

    def Save(self):
        print "Info - Build zip File %s" % self.ZipName
        if self.__zip:
            OldZipName="%s.Backup" % self.Target
            os.rename(self.Target,OldZipName)
            OldZip=zipfile.ZipFile(OldZipName)
            self.__zip=zipfile.ZipFile(self.Target,mode="w")
            print "Debug - DelList:\n%s\n\n" % "\n".join(self.__DelList)
            for Member in OldZip.namelist():
                if Member in self.__DelList: continue
                Bytes=OldZip.read(Member)
                self.__zip.writestr(Member,Bytes)
            OldZip.close()
        else:
            self.__zip=zipfile.ZipFile(self.Target,mode="w")
        for Member in self.__AddList:
            MatchPattern=re.search('([^\\\/]+)$',Member)
            MemName="RPMs/%s" % MatchPattern.group(1) if MatchPattern else Member
            self.__zip.write(Member,MemName)
        self.__zip.close()
        #print "\n*) ".join(self.__zip.namelist())
        print "Info - Calculate md5 sum"
        Buffer=open(self.ZipName)
        BufSize=65536 if os.path.getsize(Buffer.name) > (1024 * 1024 * 50) else -1
        Line=True
        ChkSum=hashlib.md5()
        while Line:
            Line=Buffer.read(BufSize)
            ChkSum.update(Line)
        Buffer.close()
        Buffer=open("%s.md5" % self.ZipName,"w")
        Buffer.write("%s  %s" % (ChkSum.hexdigest(),self.ZipName))
        Buffer.close()

    def __contains__(self, item):
        NoVerItem=BaseName(item)
        return NoVerItem in [BaseName(Iter) for Iter in self.__zip.namelist()]


###############################################################################
#
#                           M A I N
#
###############################################################################

Conf=Config(sys.argv[1])
Target=TargetZip(Conf.TargetZip)

#print "Debug - Target is %s" % Conf.TargetZip
#print "Debug  -  Rpm List:\n%s\n\n" % "\n".join(Conf.RpmList)


for Rpm in Conf.RpmList:
    #print "Debug - %s : %s" % (BaseName(Rpm),Rpm)
    if Rpm in Target:
        #print "Debug - %s already exists at zip file Overwrite it !" % Rpm
        NewRpm=ExtarctVer(Rpm)
        OldRpm=Target.Version(Rpm)
        print "Info - Replace %s" % NewRpm[1]
        print "     Old Version    New Version\n%16s    %s" % (OldRpm,NewRpm[0])
        Target.ReplaceMember(Rpm)
    else:
        print "Info - add new rpm %s" % BaseName(Rpm)
        Target.AddMember(Rpm)

Target.Save()
