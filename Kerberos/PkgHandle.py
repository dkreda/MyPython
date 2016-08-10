__author__ = 'dkreda'
###############################################################################
# This Module contains all the common records and structures that are used
# both by server side and client side.
###############################################################################
import pickle
import re
import Ini
import time

class KrRecord(object):
    # Basic record - all the record inherit from this basic just to
    # keep the same convention look at the records display
    delimiter = '||'
    def _attrList(self):
        return ()

    def EncFormat(self,Obj,ClassName='Record'):
        return "Encrypted %s <???>" % ClassName if Obj.__class__ == "".__class__ else str(Obj)

    def __str__(self):
        return KrRecord.delimiter.join(self._attrList())

class HostRec(object):
    # represent Server:
    # Name - is the Server's Name. as appears in the Kerberos dataBase.
    # Address - is the IP of the Server.
    # Port - the port of the server
    def __init__(self,HostName,Address,Port = 0):
        self.Name=HostName
        StrAddress=Address.split(':')
        self.Address=StrAddress[0] if len(StrAddress) > 1 else Address
        self.Port=int(StrAddress[1]) if len(StrAddress) > 1 else Port

    def getAddress(self):
        return (self.Address,self.Port)

    def __str__(self):
        return "(%s) %s:%d" % (self.Name,self.Address,self.Port)

class EncObj(object):
    # Handle the Encryption: get Object and a key
    #        the Object may be Encrypted Object / or regular Object
    #  method getObj - always return the regular object
    def __init__(self,Key,Obj,Method="AES"):
        # Key - is the key to use for Encryption/Decryption
        # Obj - is the Object to Encrypt/Decrypt - if Obj is string it is encrypted Object
        # Method - is the Encryption (cypher) method to use
        Saltedkey=str(Key) + 'ThisIsPaddesKey0987654321'
        self.__Key=Saltedkey[:BlockSize]
        if Method == "AES":
            from Crypto.Cipher import AES
            # import the module just if needed.
            self.__CypherEngine=AES.new(self.__Key) #,AES.MODE_CBC)
        elif Method == "Simple":
            self.__CypherEngine = SimpleEncrypt(self.__Key)
        else:
            raise TypeError('Unsupported encryption type "%s"' % Method)
        if type(Obj) is str and len(Obj) % BlockSize == 0:
            # This looks like an already Encrypted object
            self.__EncryptedObj = Obj
        else:
            self.__EncryptedObj = self.__CypherEngine.encrypt(pad(Obj))

    def getObj(self):
        # return the Original Object.
        # decrypt and restore the Original object
        try:
            decStr=self.__CypherEngine.decrypt(self.__EncryptedObj)
            return pickle.loads(trim(decStr))
        except ValueError, ex:
            if re.match('Input strings must be a multiple',ex.message):
                # this exception may raise by encrypt method that requires multiple
                # of fix length block size such as AES.
                # this may be an already decrypt string
                return self.__EncryptedObj
            else:
                raise KeyError('Fail to decrypt using key "%s"' % self.__Key )
        except KeyError :
            raise KeyError('Wrong Key "%s" Fail to decrypt' % self.__Key)
        except Exception , e:
            if type(self.__EncryptedObj) is SimpleEncrypt:
                EncMethod="Simple"
            elif re.search('AES',self.__EncryptedObj.__class__) :
                EncMethod='AES'
            else:
                EncMethod=str(self.__EncryptedObj.__class__)
            raise KeyError('Fail to decrypt - using key "%s" with method "%s"' %(self.__Key,EncMethod) )
        return None

    def __str__(self):
        return self.__EncryptedObj

class Message(object):
    # This class Handle the serialization and representation of messages between
    # server - client communication.
    def __init__(self,Obj):
        self.ObjStr = pickle.dumps(Obj) if Obj.__class__  != "".__class__ else Obj

    def getRecord(self):
        try:
            return pickle.loads(self.ObjStr)
        except EOFError:
            raise ValueError("Corrupted message - fail to restore message")
        return None

####################################
# Response classes

class BasicRec(KrRecord):
    # General server Response (Just timeStamp)
    def __init__(self,TimeStamp):
        self.TimeStamp=float(TimeStamp)

    def _attrList(self):
        return (str(self.TimeStamp),)

class ResMessageTGS(BasicRec):
    # TGS Server Response
    def __init__(self,TimeStamp,Key,Ticket):
        super(ResMessageTGS,self).__init__(TimeStamp)
        self.Key=str(Key)
        self.Ticket=Ticket

    @property
    def getTktDisp(self):
        return "Ticket: %s" % self.EncFormat(self.Ticket,'Ticket')

    def _attrList(self):
        return (time.ctime(self.TimeStamp),self.Key, self.getTktDisp)

class ResMessageAS(ResMessageTGS):
    # Authentication Server (ASServer) response
    def __init__(self,TimeStamp,Key,Ticket,UserName,SessionID,Lifetime):
        super(ResMessageAS,self).__init__(TimeStamp,Key,Ticket)
        self.User=UserName
        self.SessionID=str(SessionID)
        self.LifeTime=Lifetime

    def _attrList(self):
       return (time.ctime(self.TimeStamp),self.Key,self.User,self.SessionID,str(self.LifeTime),self.getTktDisp)

####################################
# Request classes

#class BasicRequest(KrRecord):
#    pass

class AuthRequest(KrRecord):
    # Authentication  request - send to ASServer
    def __init__(self,user,server,TimeStamp):
        self.User=user
        self.Server=server
        self.TimeStamp=TimeStamp

    def _attrList(self):
        return (self.User,self.Server,str(self.TimeStamp),)

class ServiceRequest(KrRecord):
    # Service Request - send to Server before the first standard request
    #                   This is the last message request in the kerberos protocol
    def __init__(self,TicketRec,Auth):
        self.Ticket=TicketRec
        self.Auth=Auth

    def _attrList(self):
        return ("Tkt: (%s)" % self.EncFormat(self.Ticket,'Ticket'), 'Auth: (%s)' %
                self.EncFormat(self.Auth,'Auth Record'))

class TicketRequest(KrRecord):
    # Ticket Request - request Ticket for specific server
    def __init__(self,Service,Ticket,Auth):
        self.Server=Service
        self.Tkt=Ticket
        self.Auth=Auth

    def _attrList(self):
        return (self.Server ,"Tkt: (%s)" % self.EncFormat(self.Tkt,"Ticket"),
                "Auth: (%s)" % self.EncFormat(self.Auth,"Auth Record") , )

####################################
# Messages records: records which
#           are used inside messages

class AuthRec(BasicRec):
    #######################################################
    # @ This Class is the Authentication Record which is
    #   send with each Service request or Ticket request
    def __init__(self,TimeStamp,user,SessionID,Address):
        super(AuthRec,self).__init__(TimeStamp)
        self.user=user
        self.sessionID=str(SessionID)
        self.userAddr=Address

    def _attrList(self):
        return (self.user,self.sessionID,str(self.TimeStamp),self.userAddr)

class KrTicket(AuthRec):
    # Ticket Record
    def __init__(self,TimeStamp,user,SessionID,Address,Server,Key,LifeTime):
        super(KrTicket,self).__init__(TimeStamp,user,SessionID,Address)
        self.Key=str(Key)
        self.Server=Server
        self.LifeTime=LifeTime

    def _attrList(self):
        return (self.user,self.sessionID,time.ctime(self.TimeStamp),self.userAddr,self.Key,str(self.LifeTime))

    @property
    def expired(self):
        # Verify if Ticket LifeTime expired
        return self.TimeStamp + self.LifeTime < time.time()

    def ValideAuthentication(self,AuthRecord):
        # Validate if Ticket have same values as at AuthRec
        return self.TimeStamp == AuthRecord.TimeStamp and \
               self.user == AuthRecord.user and \
               self.sessionID == AuthRecord.sessionID and \
               self.userAddr == AuthRecord.userAddr

class SimpleEncrypt():
    # Simple Encrypt engine (just do XOR with the Key)
    def __init__(self,Key):
        if type(Key) is str:
            self.__Key=Key
        else:
            raise TypeError("Key must be a string type")

    def encrypt(self,message):
        tmpList=[]
        for indx in xrange(len(message)):
            tmpList.append(ord(message[indx]) ^ ord(self.__Key[indx % len(self.__Key)]))
        tmpStr=[ chr(ch) for ch in tmpList ]
        return "".join(tmpStr)

    def decrypt(self,code):
        return self.encrypt(code)

PAD='#'
BlockSize=16
DefKey='Empty key'

def pad(Obj):
    # Utility - just pad the string (Obj representation/serialization)
    # till reach the required block size
    tmp=pickle.dumps(Obj)
    tmp += (BlockSize -  len(tmp) % BlockSize ) * PAD
    return tmp

def trim(Obj):
    # Utility - do the opposite of pad.
    tmp = re.sub( '%s*$' % PAD , '' , Obj )
    return tmp

class Config():
    # this Class just read from Ini file and build dict Type
    def __init__(self,fileName):
        self._fName=fileName
        self.readFile()

    def readFile(self):
        ConfFile=Ini.INIFile(self._fName)
        for secName in ConfFile.getSecList():
            tmpDict={PName : Rec[1] for PName,Rec in ConfFile.getSection(secName) }
            setattr(self,secName,tmpDict)
