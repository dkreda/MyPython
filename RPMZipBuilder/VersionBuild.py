__author__ = 'danielk'
###############################################################################
#
# This script builds list of knew version files.
# usage: VersionBuild configuration_file [csvfile]
#
###############################################################################
import sys,re,zipfile,os

def ExtarctVer(FullPath):
    CompPattern= { 'fnkernel' : re.compile(r'fn_([\d\-\._]+)\.') ,
                   'fnkernel-devel' : re.compile(r'fn_([\d\-\._]+)\.') ,
                   'dailyReports': re.compile(r'[\-_]V?([\d\-\._]+)\.') ,
                   'IBM' : re.compile(r'\D(\d+[\-_][\d\-\._]+)\.')}
    MatchPattern=re.search('([^\\\/]+)$',FullPath)
    if not MatchPattern: return None
    FileName=MatchPattern.group(1)
    MatchPattern=re.match('(\D+)[\-_]',FileName)
    CompName=MatchPattern.group(1)
    MatchPattern=CompPattern[CompName] if CompName in CompPattern else re.compile(r'[\-_]([\d\-\._]+)\.')
    CompVer=MatchPattern.search(FileName)
    #MatchPattern=re.match('(\D+)[\-_]([\d\-\._]+)\..*rpm',FileName)
    return [CompVer.group(1),CompName] if CompVer else ["",CompName]

class Config(object):
    SecPattern=re.compile('\[(.+)\]')
    CommentPattern=re.compile('\s*(#|$)')
    def __init__(self,FileName,*SetList):
        self.__ConfFile=FileName
        self.__List=SetList
        self.__SecList={}
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
                continue

            if Section in self.__List:
                if Section in self.__SecList:
                    self.__SecList[Section].append(Line)
                else:
                    self.__SecList[Section]=[Line]
            else:
                # print "Debug - Insert into %s Single Value (%s)" % (Section,Line)
                self.__SecList[Section]=Line

    def __getitem__(self, item):
        #print "Debug - Get Item %s" % item
        if item in self.__SecList:
            return self.__SecList[item]
        else:
            return None
    def __contains__(self, item):
        return item in self.__SecList

class Component(object):
    def __init__(self,FullPath,Date=None,*Alias):
        self.__FullPath=FullPath
        self.__Info=ExtarctVer(FullPath)
        if not Date:
            TmpArray=os.stat(FullPath)
            self.__FInfo=TmpArray[8]
        else:
            self.__FInfo=Date
        self.Alias=Alias if Alias else None

    @property
    def Name(self):
        return self.__Info[1]

    @property
    def Version(self):
        return self.__Info[0]

    @property
    def Date(self):
        return self.__FInfo

    @property
    def Path(self):
        return self.__FullPath

    def __gt__(self, other):
        return self.Date > other.Date

    def __ge__(self, other):
        #print "Debug Compare %d >= %d" % (self.Date , other.Date)
        return self.Date >= other.Date

class VersionTree(object):
    def __init__(self,*CompnonetList):
        self.__CompList={}

    def Update(self,CompItem):
        if not ( CompItem.Name in self.__CompList and self.__CompList[CompItem.Name] >= CompItem):
            ## print "Debug - Update %s to version %s" % (CompItem.Name,CompItem.Version)
            self.__CompList[CompItem.Name] = CompItem

    def __contains__(self, item):
        return item in self.__CompList

    def __getitem__(self, item):
        return self.__CompList[item]

    def getCompList(self):
        return self.__CompList.keys()

    def __add__(self, other):
        ## print "Debug - Add Tree ...."
        for TmpComp in other.getCompList():
            self.Update(other[TmpComp])
        return self

class TreeBuilder(object):
    RegExpDir=re.compile(r'(.+?)([^\/\\]*\*[^\/\\]*)(.*)$')
    RegExpRpm=re.compile(r'\.rpm$')
    RegExpZip=re.compile(r'\.zip',flags=re.IGNORECASE)
    def __init__(self,*Path,**Params):
        self.__Tree=VersionTree()
        self.__Debug=True if 'Debug' in Params else False
        self.__Aliases=Params
        for Folder in Path:
            if self.__Debug:
                print "Debug - Search Folder: %s" % Folder
            Tmp=self.__StrSearch(Folder)
            if Tmp: self.__Tree += Tmp
        #return self

    def __FolderSearch(self,Folder):
        if not os.path.exists(Folder): return None
        VersionList=VersionTree()
        if os.path.isfile(Folder):
            if self.RegExpRpm.search(Folder):
                Tmp=Component(Folder)
                if Tmp.Name in self.__Aliases:
                    Tmp.Alias=self.__Aliases[Tmp.Name]
                VersionList.Update(Tmp)
                if self.__Debug:
                    print "Debug: RPM %s" % Tmp.Name
                    print "\t-Version: %s" % Tmp.Version
                    print "\t-Full Path: %s" % Tmp.Path
            elif self.RegExpZip.search(Folder):
                return self.__ZipSearch(Folder)
            else:
                return None
        else:
            for FileName in os.listdir(Folder):
                Tmp=self.__FolderSearch("%s/%s" % (Folder,FileName) )
                if Tmp: VersionList += Tmp
        return VersionList

    def __ZipSearch(self,ZipFile):
        MyZip=zipfile.ZipFile(ZipFile)
        MyZip.close()
        FStat=os.stat(ZipFile)
        Result=VersionTree()
        for Mem in MyZip.namelist():
            if self.RegExpRpm.search(Mem): #  re.search(r'\.rpm$',Mem):
                Tmp=Component(Mem,FStat[8])
                if Tmp and Tmp.Name in self.__Aliases:
                    Tmp.Alias=self.__Aliases[Tmp.Name]
                Result.Update(Tmp)
        return Result

    def __StrSearch(self,Folder):
        TmpMatch=self.RegExpDir.match(Folder) #   re.match(r'(.+?)([^\/\\]*\*[^\/\\]*)(.*)$',Folder)
        if TmpMatch:
            VersionList=VersionTree()
            BaseF=TmpMatch.group(1)
            FName=TmpMatch.group(2)
            suffix=TmpMatch.group(3)
            if not os.path.exists(BaseF):return None
            FStr=re.sub(r'\*',r'.*',FName,flags=re.DOTALL)
            Filter=re.compile(FStr)
            #print "Debug - Seraching Base Dir %s" % BaseF
            for Files in os.listdir(BaseF):
                Tmp=Filter.match(Files)
                if Tmp:
                    FullPath="%s%s%s" % (BaseF,Files,suffix)
                    TmpResult=self.__StrSearch(FullPath)
                    if TmpResult: VersionList += TmpResult
            return VersionList
        else:
            return self.__FolderSearch(Folder)

    @property
    def CompList(self):
        return self.__Tree


def BuildColumns(OldVer,NewVer,Title=None):
    Row=["Component Name","Last Version","Next version","Change","Package Location"]
    Result=[Title,Row] if Title else [Row]
    for Comp in ( set(OldVer.getCompList()) | set(NewVer.getCompList())) :
        VerArray=(OldVer[Comp].Version if Comp in OldVer else "N/A",
                  NewVer[Comp].Version if Comp in NewVer else "N/A",)
        NoChange=VerArray[0] == VerArray[1]
        CompObj=NewVer[Comp] if Comp in NewVer else OldVer[Comp]
        Row=["%s (%s)" % (CompObj.Alias,Comp) if CompObj.Alias else Comp ,
             VerArray[0],VerArray[1],
             "From Last Drop" if NoChange else "New !",
             "" if NoChange or not Comp in NewVer else NewVer[Comp].Path]
        Result.append(Row)
    return Result

Conf=Config(sys.argv[1],'Source','List','Aliases')
AliasesList={}
if 'Aliases' in Conf:
    print "Debug - Aliases List:"
    for Line in Conf['Aliases']:
        print "Debug - A-  %s" % Line
        AlMatch=re.match(r'(\S+?)=(.+)',Line)
        if AlMatch:
            AliasesList[AlMatch.group(1)]=AlMatch.group(2)

NewCompList=TreeBuilder(*Conf['Source'],**AliasesList) #  VersionTree()
ZipVers=TreeBuilder(Conf['Target'],**AliasesList) # SearchZip(Conf['Target'])
CsvFile=open(sys.argv[2],mode='w') if len(sys.argv) > 2 else None
print "\n\nVersion Check:"
Lines=BuildColumns(ZipVers.CompList,NewCompList.CompList)
for Row in (Lines):
    print "%-25s %-15s %-15s %-10s %s" % (Row[0],Row[1],Row[2],Row[3],Row[4])
    if CsvFile:
        CsvFile.write("%s\n" % ','.join(Row))
if CsvFile: CsvFile.close()
if len(sys.argv) > 2:
    IniFileName=re.sub('csv','ini',sys.argv[2])
    IniFile=open(IniFileName,mode='w')
    IniFile.write("%s\n" % "\n".join(("[Target]",Conf['Target'],"",)))
    IniFile.write("[List]\n")
    IniFile.write("%s\n" % "\n".join([Col[4] for Col in Lines if re.match('New',Col[3])]))
    IniFile.close()
