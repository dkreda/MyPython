__author__ = 'dkreda'

import sys,os,re,time
import random
#import pickle      ### serialization Module
import PkgHandle
import string
import socket
import thread
from abc import abstractmethod,abstractproperty

class BaseClass(object):
    def __init__(self,**Config):
        self.LogFile=Config.get('LogFile')
        self.Name=Config.get('Name')
        self.WriteLog("Debug","Test multi Message log","This is the second line")

    def WriteLog(self,Level,*Messages):
        prefix="(%s)," % self.Name if self.Name else ""
        prefix='%-6s %s%s: ' % (Level,prefix,time.asctime()) if Level else ""
        for line in Messages:
            print prefix , line
            prefix = ' ' * len(prefix)
        #OutMessage = "%-6s (%s),%s: %s" % (Level,self.Name,time.asctime(),Message) if Level else Message
        #print OutMessage

    def GenerateKey(self,Size):
        self.WriteLog("Debug","Generate Special Key of Size %d" % (Size))
        Chars=string.ascii_letters + string.digits
        return "".join(random.choice(Chars) for i in xrange(Size))

    def Title(self,*Text):
        Size=80
        self.WriteLog('','*' * Size)
        for line in Text:
           self.WriteLog('',"* %-*s*" % (Size - 3 , line))
        self.WriteLog('','*' * Size)

class Kr_AbstractServer(BaseClass):
    def __init__(self,**Config):
        super(Kr_AbstractServer,self).__init__(**Config)
        self.MaxConnect=int(Config.get('MaxConnect',3))
        self.port=int(Config.get('Port',0))
        self.LifeTime=int(Config.get('LifeTime',120))
        self.EncryptMethod=Config.get('Encrypt','Simple')
        self.Running=False
        self.ServerInit(Config)

    @abstractmethod
    def ServerInit(self,Config):
        pass

    def StartServer(self):
        self.Running=True
        ServerSocket=socket.socket()
        ServerSocket.bind(('',self.port))
        ServerSocket.listen(self.MaxConnect)
        ### Verify Encryption method
        try:
            test=PkgHandle.EncObj('123',None,self.EncryptMethod)
            ### Title Print
            self.Title("Server " + self.Name + " is up" ,
                        "Listen at Port %d" % self.port )
            self.ControlSock=ServerSocket
            thread.start_new_thread(self.Listen,(ServerSocket,))
        except TypeError , e:
            self.WriteLog("Error","Wrong configuration " + e.message ,
                          "Server " + self.Name + " Failed to start")


    @abstractmethod
    def VerifyRequest(self,Request,ClientAddr):
        pass

    def BuildTicket(self,UserName,Server,SessionID,ClientAddress):
        TimeStamp=time.time()
        Key=self.GenerateKey(16)
        return PkgHandle.Ticket(TimeStamp,UserName,SessionID,ClientAddress,Server,Key,self.LifeTime)

    @abstractmethod
    def BuildResponse(self,Ticket,Key):
        ## Key is the Kry for entire message encryption
        ## The Ticket will be encrypt using the Server->Key
        print "Debug - Abstract Responce"

    def additionalService(self,ServerSocket):
        pass

    def Listen(self,ServerSock):
        while self.Running:
            (Content,Address)=ServerSock.accept()
            self.WriteLog("Info","Received Req from " + Address[0])
            Request=PkgHandle.Message(Content.recv(2048))
            Response=self.HandleRequest(Request.getRecord(),Address[0])
            if Response:
                ResMessage=PkgHandle.Message(Response)
                Content.send(ResMessage.ObjStr)
                self.additionalService(Content)
            else:
                self.WriteLog("Error","Fail to handle request from Client " + Address[0] )
                Content.send("Error Request rejected")
            Content.close()
        self.WriteLog("Info","Server finished to listen ....")

    def StopServer(self):
        self.Running=False
        self.ControlSock.close()
        self.WriteLog("Info","Stop due to request")

    def HandleRequest(self,Request,ClientAddr):
        (Ticket,Key)=self.VerifyRequest(Request,ClientAddr)
        if Key:
            self.WriteLog("Info","Request Verification Pass O.K.")
            self.WriteLog("Debug","Response Ticket type is " + str(Ticket.__class__) )
            Res=self.BuildResponse(Ticket,Key)
            return Res
        else:
            self.WriteLog("Error","Request from %s Verification Failed" % (ClientAddr,))
            return False

class Kr_AuthServer(Kr_AbstractServer):

    def VerifyRequest(self,Request,ClientAddr):
        if hasattr(Request,'Server'):
            #client=self._retreiveClient(Request.User)
            client=self.DataBase.getClientRecord(Request.User)
            if type(None) == type(client):
                self.WriteLog("Error","Request with unknown user Reject.")
                return (None,None)
            tmpspe=client.spe
            ClientKey=self.GenerateKey(6)
            tmpspe.sendMessage(ClientKey)
            Session=self._getSessionID(Request.User,Request.Server)
            Tkt=self.BuildTicket(Request.User,Request.Server,Session,ClientAddr)
            return (Tkt,ClientKey)
        else:
            self.WriteLog("Error","Illegal Request from client " + self._getClientAddress())
            return None

    def addClient(self,Client):
        self.DataBase.addClient(Client)
        #self.userConf[Client.name]=Client

    def LoadTGSKey(self):
        self.TGSKey=self.DataBase.getServerKey('TGS')
        return
        tmp=self.DBName
        self.DBName=self.ServersDB
        for RecTuple in self.LoadDB():
            #print "Debug --- RecTuple " ,RecTuple.__class__
            #print "Debug --- RecTuple Content: " ,RecTuple
            if RecTuple[0] == 'TGS':
                self.TGSKey=RecTuple[2]
                break
        self.DBName=tmp
        self.WriteLog("Info","Load TGS Server Key (from DB)")
        #print "Debug - " + self.Name + " Load TGS Key"

    def _getSessionID(self,clientID,Server):
        return "%d-%s%s-%s" % (random.randint(1000000,10000000),time.time(),clientID,Server)


    def ServerInit(self,Config):
        super(Kr_AuthServer,self).ServerInit(Config)
        #self.DBName= Config.get('DB' , 'NA')
        tmp=DBWrapper(Config.get('DB' , 'NA'))
        self.DataBase=tmp.Connect()
        #self.userConf={}
        #self.ServersDB = Config.get('ServersDB', 'ServerList' )
        #self.LoadUserDB()
        self.LoadTGSKey()

    def BuildResponse(self,Ticket,Key):
        #Ticket=PkgHandle.Ticket()
        #Tkt=PkgHandle.Ticket(timeStamp,client.name,SessionID,'tmp NA','TGS Server (My IP)',TktKey,LifeTime)
        SerKey=self.TGSKey #    self._getTicketKey(Ticket.Server)
        tmpEncObj=PkgHandle.EncObj(SerKey,Ticket,self.EncryptMethod)
        answer=PkgHandle.ResMessageAS(Ticket.TimeStamp,Ticket.Key,tmpEncObj._Obj,Ticket.user,Ticket.sessionID,
                                      Ticket.LifeTime)
        self.WriteLog("Debug","Encrypt response using key " + Key)
        EncAnswer=PkgHandle.EncObj(Key,answer,self.EncryptMethod)
        return EncAnswer._Obj

    def printClients(self):
        for cRec in self.userConf.items():
            print cRec[0] , " >> " , cRec[1].spe

class Kr_TGSServer(Kr_AbstractServer):

    def LoadServersKey(self):
        counter=0
        for RecTuple in self.LoadDB():
            ServerRec=ServerRecord(RecTuple[0],RecTuple[1],RecTuple[2])
            self.addServer(ServerRec)
            counter+=1
        self.WriteLog("Info","Load total %d Servers records " %  counter)

    def addServer(self,Server):
        if hasattr(Server,'Key'):
            self.ServerList[Server.Name]=Server.Key
        else:
            self.WriteLog("Error","Illegal Server Record")

    def ServerInit(self,Config):
        super(Kr_TGSServer,self).ServerInit(Config)
        #self.keyList=[]
        tmp=DBWrapper(Config.get('DB' , 'NA'))
        #self.DBName=
        self.DataBase=tmp.Connect()

    def _getTicketKey(self,Server):
        ## Find the Server Private Key
        return self.DataBase.getServerKey(Server)
        #return self.ServerList[Server]

    def VerifyRequest(self,Request,ClientAddr):
        if hasattr(Request,'Tkt') and  hasattr(Request,'Auth'):
            Key=self.DataBase.getServerKey(self.Name)
            #Key=self._getTicketKey(self.Name)
            tmpEncObj=PkgHandle.EncObj(Key,Request.Tkt,self.EncryptMethod)
            Ticket=tmpEncObj.getObj()
            ### get Client-TGS Key
            Key=Ticket.Key
            tmpEncObj=PkgHandle.EncObj(Key,Request.Auth,self.EncryptMethod)
            Auth=tmpEncObj.getObj()
            #Ticket-PkgHandle.Ticket()
            if Ticket.TimeStamp + Ticket.LifeTime >= time.time() :
                if Ticket.sessionID == Auth.sessionID and Ticket.user == Auth.user and \
                    Ticket.TimeStamp == Auth.TimeStamp:
                    #Request=TicketRequest()
                    ServerTkt=self.BuildTicket(Auth.user,Request.Server,Auth.sessionID,ClientAddr)
                    return (ServerTkt,Ticket.Key)
                else:
                    self.WriteLog("Error","Authentication Failed. Auth Record don't match the Ticket request")
                    return (None,None)
            else:
                self.WriteLog("Debug","Ticket expired at " + time.ctime(Ticket.TimeStamp + Ticket.LifeTime))
                self.WriteLog("Error","Ticket period expired. Ignore the request")
                return (None,None)

    def BuildResponse(self,Ticket,Key):
        try:
            SerKey=self._getTicketKey(Ticket.Server)
        except KeyError , e :
            ErrorMessage="Server %s (or %s) are not memeber of this kerberos domain" % (Ticket.Server,e.message)
            self.WriteLog("Error",ErrorMessage)
            return "Error: " + ErrorMessage
        tmpEncObj=PkgHandle.EncObj(SerKey,Ticket,self.EncryptMethod)
        answer=PkgHandle.ResMessageTGS(Ticket.TimeStamp,Ticket.Key,tmpEncObj._Obj)
        self.WriteLog("Debug","Encrypt TGS Server answer using Key " + Key )
        EncAnswer=PkgHandle.EncObj(Key,answer,self.EncryptMethod) # self.PassMap[Ticket.user],answer)
        return EncAnswer._Obj

class clientRecord(object):
    def __init__(self,cName,speList,description):
        self.name=cName
        self.spe=speList
        self.desc=description

class ServerRecord(object):
    def __init__(self,Name,Address,Key):
        self.Name=Name
        self.Address=Address
        self.Key=Key

class TicketRequest(object):
    ## Request for specific Service (Server)
    def __init__(self,Service,Ticket,Auth):
        self.Server=Service
        self.Tkt=Ticket
        self.Auth=Auth

class abstractSPE(object):
    def __init__(self,connectInfo):
        self.SPE=connectInfo

    def sendMessage(self,message,**destConf):
        Size=50
        print '*' * Size
        for line in ("SPE send message to client:",message,):
           print "* %-*s*" % (Size - 3 , line)
        print '*' * Size
        #print message

class AuthReq(object):
    def __init__(self,user,server,TimeStamp):
        self.User=user
        self.Server=server
        self.TimeStamp=TimeStamp

    def __str__(self):
        return "Request: Authentication: " + '||'.join((self.User,self.Server,str(self.TimeStamp)))

class DBWrapper():
    def __init__(self,ConnectionStr):
        #username[/password]@myserver[:port][/myservice:dedicated][/instancename]
        #for file file@FileName/
        self.__ConnStr=ConnectionStr

    def Connect(self):
        if re.match('^file',self.__ConnStr,re.IGNORECASE):
            tmpObj=DBcsvWrapper(self.__ConnStr)
            #return
        else:
            raise Exception("Unsupported DataBase connection type " + self.__ConnStr)
        tmpObj.Connect()
        return tmpObj

    def getClientRecord(self,ClientID):
        pass

    def getTGSKey(self):
        pass

    def addClient(self,ClientRec):
        pass

    def getServerKey(self,Server):
        pass

    def addServer(self,Server):
        pass

    def getServerRecord(self,ServerName):
        pass

class DBcsvWrapper(DBWrapper):
    def __init__(self,ConnectStr):
        self.fileList=ConnectStr.split('@')
        self.__clientList={}
        self.__ServerList={}

    def ReadCsv(self,FileName):
        dBFile=open(FileName,'r')
        Result=[]
        for line in  dBFile:
            clist=line.split(',')
            Result.append(clist)
        dBFile.close()
        return Result

    def Connect(self):
        ## Read Servers List
        for RecTuple in self.ReadCsv(self.fileList[1]):
           self.addServer(ServerRecord(RecTuple[0],RecTuple[1],RecTuple[2]))
        if len(self.fileList) > 2:
            for RecTuple in self.ReadCsv(self.fileList[2]):
                self.addClient(clientRecord(RecTuple[0],abstractSPE(RecTuple[1]),RecTuple[2]))

    def addClient(self,ClientRec):
        self.__clientList[ClientRec.name]=ClientRec

    def getClientRecord(self,ClientID):
        return self.__clientList.get(ClientID,None)

    def addServer(self,Server):
        self.__ServerList[Server.Name]=Server

    def getServerKey(self,Server):
        return self.__ServerList[Server].Key

    def getServerRecord(self,ServerName):
        #Server=self.__ServerList.get(ServerName)
        #Server=ServerRecord()
        #if Server:
        #    return PkgHandle.HostRec(Server.Name,Server.Address)
        return self.__ServerList.get(ServerName)




if  __name__ == '__main__' :
    print "This is Server running (Not Module ...)"
    ServerConf=PkgHandle.Config('kerberosConfiguration.conf')
    #ServerConf.readFile()
    print "Start Server ...."
    KerberosServer=Kr_AuthServer(**ServerConf.AuthenticationServer)
    TGSServer=Kr_TGSServer(**ServerConf.TGSServer)
    KerberosServer.StartServer()
    TGSServer.StartServer()
    time.sleep(600)
    KerberosServer.StopServer()
    TGSServer.StopServer()
    print "Server Finished ...."
