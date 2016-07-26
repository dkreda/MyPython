__author__ = 'dkreda'


import pickle
import re
import Ini
import time

class BasicRec(object):
    def __init__(self,TimeStamp):
        self.TimeStamp=float(TimeStamp)

    def _attrList(self):
        return (str(self.TimeStamp),)

    def __str__(self):
        return "||".join(self._attrList())

class AuthRec(BasicRec):
    #######################################################
    # @ This Class is the Authentication Record which is
    #   send with each Service request or Ticket request
    def __init__(self,TimeStamp,user,SessionID,Address):
        super(AuthRec,self).__init__(TimeStamp)
        self.user=user
        self.sessionID=str(SessionID)
        self.userAddr=Address
        #self.ts=TimeStamp

    def _attrList(self):
        return (self.user,self.sessionID,str(self.TimeStamp),self.userAddr)

    #def __str__(self):
    #    return "||".join(self._attrList())

class ResMessageTGS(BasicRec):
    def __init__(self,TimeStamp,Key,Ticket):
        super(ResMessageTGS,self).__init__(TimeStamp)
        self.Key=str(Key)
        #self.TimeStamp=TimeStamp
        self.Ticket=Ticket

    @property
    def getTktDisp(self):
        return "Ticket: %s" % ("Encrypted Ticket <???>" if self.Ticket.__class__ == "".__class__ else str(self.Ticket))

    def _attrList(self):
        #print "Debug - (Line 52) ResMessageTGS.Ticket is :" , type(self.Ticket)
        return (time.ctime(self.TimeStamp),self.Key,self.getTktDisp)
                #"Ticket: %s" % str(self.Ticket))

class ResMessageAS(ResMessageTGS):
    def __init__(self,TimeStamp,Key,Ticket,UserName,SessionID,Lifetime):
        super(ResMessageAS,self).__init__(TimeStamp,Key,Ticket)
        self.User=UserName
        self.SessionID=str(SessionID)
        self.LifeTime=Lifetime

    def _attrList(self):
       #print "Debug - ResMessageAS.Ticket is :" , type(self.Ticket)
       #return (" ???????   Line 63 ..........")
       return (time.ctime(self.TimeStamp),self.Key,self.User,self.SessionID,str(self.LifeTime),self.getTktDisp)
               #"Ticket: %s" % ("Encrypted Ticket <???>" if self.Ticket.__class__ == "".__class__ else str(self.Ticket)))

class Ticket(AuthRec):
    def __init__(self,TimeStamp,user,SessionID,Address,Server,Key,LifeTime):
        super(Ticket,self).__init__(TimeStamp,user,SessionID,Address)
        self.Key=str(Key)
        self.Server=Server
        self.LifeTime=LifeTime

    def _attrList(self):
        return (self.user,self.sessionID,time.ctime(self.TimeStamp),self.userAddr,self.Key,str(self.LifeTime))

class EncObj(object):
    def __init__(self,Key,Obj,Method="AES"):
        Saltedkey=str(Key) + 'ThisIsPaddesKey0987654321'
        self._Key=Saltedkey[:BlockSize]
        if Method == "AES":
            from Crypto.Cipher import AES
            self._encObj=AES.new(self._Key) #,AES.MODE_CBC)
        elif Method == "Simple":
            self._encObj = SimpleEncrypt(self._Key)
        else:
            raise TypeError("Unsupported encryption type " + Method)
        #self._encObj._cipher
        self._Obj= self._encObj.encrypt(pad(Obj)) if Obj.__class__ != type("") else Obj

    def getObj(self):
        try:
            decStr=self._encObj.decrypt(self._Obj)
            return pickle.loads(trim(decStr))
        except ValueError, ex:
            if re.match('Input strings must be a multiple',ex.message):
                print ex.message + ". This may be unencripted String"
                return self._Obj
            else:
                print "Decript Error: " , ex.message
        except KeyError :
            print "Error - wrong Key (%s)" % self._Key
        except Exception , e:
            print "Error - Fail to encrypt Object"
            print "Exception: " , e.message , " > " , e.__class__
        return None

    def __str__(self):
        return self._Obj

class Message(object):
    def __init__(self,Obj):
        self.ObjStr = pickle.dumps(Obj) if Obj.__class__  != "".__class__ else Obj

    def getRecord(self):
        try:
            return pickle.loads(self.ObjStr)
        except EOFError:
            print "Error - corrupted message or connection terminate abnormal"
            return None
        return None

class ServiceRequest(object):
    def __init__(self,Ticket,AuthRec):
        self.Ticket=Ticket
        self.Auth=AuthRec

class HostRec(object):
    def __init__(self,HostName,Address,Port = 0):
        self.Name=HostName
        StrAddress=Address.split(':')
        self.Address=StrAddress[0] if len(StrAddress) > 1 else Address
        self.Port=int(StrAddress[1]) if len(StrAddress) > 1 else Port

    def getAddress(self):
        return (self.Address,self.Port)

    def __str__(self):
        return "(%s) %s:%d" % (self.Name,self.Address,self.Port)

class SimpleEncrypt():
    def __init__(self,Key):
        if type(Key) is str:
            self.__Key=Key
        else:
            raise TypeError("Key must be a string type")

    def encrypt(self,message):
        tmpList=[]
        for indx in xrange(len(message)):
            #print indx
            tmpList.append(ord(message[indx]) ^ ord(self.__Key[indx % len(self.__Key)]))
        tmpStr=[ chr(ch) for ch in tmpList ]
        #print "Debug - ", "".join(tmpStr)
        return "".join(tmpStr)

    def decrypt(self,code):
        return self.encrypt(code)


#def encrypt(Obj):
    #tmp = AES.new(111111)
#    return defEnc.encrypt(pad(Obj))

#def decrypt(EObj):
    #tmp = AES.new(111111)
#    return defEnc.decrypt(trim(EObj))

PAD='#'
BlockSize=16
DefKey='Empty key'

def pad(Obj):
    tmp=pickle.dumps(Obj)
    tmp += (BlockSize -  len(tmp) % BlockSize ) * PAD
    return tmp

def trim(Obj):
    tmp = re.sub( '%s*$' % PAD , '' , Obj )
    return tmp

class Config():
    def __init__(self,fileName):
        self._fName=fileName
        self.readFile()

    def readFile(self):
        ConfFile=Ini.INIFile(self._fName)
        for secName in ConfFile.getSecList():
            tmpDict={PName : Rec[1] for PName,Rec in ConfFile.getSection(secName) }
            setattr(self,secName,tmpDict)


##################################
# Global
#DefKey += '1234567890123456'
#defEnc = AES.new(DefKey[:BlockSize])
#print "Debug : PkgHandler Loded for: " , __name__ , '__main__'
