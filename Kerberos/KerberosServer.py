__author__ = 'dkreda'
###############################################################################
#                                                                             #
# This file serves as MAIN program that implement Kerberos servers            #
# and as module which supply base classes to implement servers that wish to   #
# run kerberos authentication before serving a user.                          #
# classes that may be used (in module mode:                                   #
# GeneralServer - Regular server that check kerberos ticket before start      #
#                 serving                                                     #
# Kr_TGSServer - Implemnts TGS Server                                         #
# Kr_AuthServer - implements AS Server                                        #
###############################################################################
import sys,re,time,random
import PkgHandle
import string
import socket
import thread,threading,traceback
from abc import abstractmethod

class BaseClass(object):
    # Base Class: set basic methods /utilities that all
    # Kerberos subclass requires
    # Configuration Parameters this class requires:
    # Name - string
    # optional parameters
    # Encrypt - Encrypt method to use. valid values: AES,Simple
    # LogFile - name of the logfile to write to. Default - No Log (just print to screen)
    def __init__(self,**Config):
        self.Name=Config.get('Name')
        self.EncryptMethod=Config.get('Encrypt','Simple')
        self.__Lock=threading.RLock()
        self.__LogFile=False
        try:
            self.__LogFile=open(Config.get('LogFile'),'w+')
            self.WriteLog("Info","open new log file " + Config['LogFile'])
        except TypeError , e:
            self.WriteLog("Error","Log File is not available","missing LogFile configuration")
        except IOError , e:
            self.WriteLog("Error","Log File is not available",e.strerror)
        ### Verify Encrypt Method
        try:
            Dummy=PkgHandle.EncObj('dummyKey',None,self.EncryptMethod)
        except TypeError , e:
            ErrorMessage="Wrong configuration " + e.message
            self.WriteLog("Error", ErrorMessage)
            raise ServerFatal(ErrorMessage)

    def WriteLog(self,Level,*Messages):
        prefix="(%s)," % self.Name if self.Name else ""
        prefix='%-6s %s%s: ' % (Level,prefix,time.asctime()) if Level else ""
        mList=[]
        for line in Messages:
            mList.append( prefix + line )
            #print prefix , line
            prefix = ' ' * len(prefix)
        ### Lock this section just in case several threads may write to the log
        ### This may be very rare that several threads will write to the log
        ### cause python do not run multipy threads (it runs thread just if the
        ### other are in block state - waiting for an IO or system request termination)
        self.__Lock.acquire()
        print "\n".join(mList)
        if self.__LogFile:
            #self.__LogFile.writelines("\n".join(mList))
            self.__LogFile.write("\n".join(mList))
            self.__LogFile.write("\n")
            self.__LogFile.flush()
        ### Release the lock
        self.__Lock.release()

    def stopLog(self):
        if self.__LogFile:
            self.__LogFile.close()

    def GenerateKey(self,Size):
        # Generates random Key of Size Bytes
        # Size - the length of Key in Bytes
        self.WriteLog("Debug","Generate Special Key of Size %d" % (Size))
        Chars=string.ascii_letters + string.digits
        return "".join(random.choice(Chars) for i in xrange(Size))

    def Title(self,*Text):
        Size=80
        MessageList=["* %-*s*" % (Size - 3 , line) for line in Text ]
        MessageList.insert(0,'*' * Size)
        MessageList.append('*' * Size)
        self.WriteLog('',*MessageList)

class Kr_AbstractServer(BaseClass):
    # Server Ancestor Class: Every server type should inherent this class
    # Configuration Parameters this class requires:
    # Name - string
    # Port - integer 1 - 65535. the port this server should listen
    # optional parameters
    # LogFile - name of the logfile to write to. Default - No Log (just print to screen)
    # Encrypt - Encrypt method to use. valid values: AES,Simple
    # MaxConnect - Number of maximum active open connections. Default 3
    # LifeTime - period of Ticket Life Time in sec units. Default - 120 sec
    def __init__(self,**Config):
        try:
            super(Kr_AbstractServer,self).__init__(**Config)
            self.MaxConnect=int(Config.get('MaxConnect',3))
            self.port=int(Config.get('Port',0))
            self.LifeTime=int(Config.get('LifeTime',120))
            self.EncryptMethod=Config.get('Encrypt','Simple')
            self.Running=False     # use to control the server operation
            self.ServerInit(Config)
        except ServerFatal ,e:
            raise e
        except KeyError , e:
            raise ServerFatal("missing configuration Parameters (%s)" % e.message )
        except BaseException , e:
            raise ServerFatal("Fail to initial Server: " + e.message)

    @abstractmethod
    def ServerInit(self,Config):
        pass

    def StartServer(self):
        try:
            ServerSocket=socket.socket()
            ServerSocket.bind(('',self.port))
            ServerSocket.listen(self.MaxConnect)
            self.ControlSock=ServerSocket
            self.Running=True
        except socket.error , e:
            self.WriteLog("Error","Fail to listen on Port %d" % self.port ,
                          "verify the port is not in usage or fix the configuration" ,
                           e.strerror, e.message  )
            raise ServerFatal("Fail to listen on Port %d" % self.port )
        self.Title("Server " + self.Name + " is up" ,
                   "Listen at Port %d" % self.port )
        self.Listen(ServerSocket)

    @abstractmethod
    def VerifyRequest(self,Request,ClientAddr):
        # This method should return tuple (Rec,Key)
        # Rec - a Rec that should be read by BuildResponse method.
        # Key - the key to use to encrypt the response
        pass

    def BuildTicket(self,UserName,Server,SessionID,ClientAddress):
        TimeStamp=time.time()
        Key=self.GenerateKey(16)
        tmp = PkgHandle.KrTicket(TimeStamp,UserName,SessionID,ClientAddress,Server,Key,self.LifeTime)
        return tmp

    @abstractmethod
    def BuildResponse(self,Ticket,Key):
        ## Key is the Key for entire message encryption
        ## Ticket - is a record the should contain relevant info to build response
        pass

    def additionalService(self,ServerSocket):
        pass

    def runRequest(self,ConnectSocket):
        # handle active connection with client.
        # this method should run in separate thread to avoid DOS in case the operation
        # takes too long ....
        Request=PkgHandle.Message(ConnectSocket.recv(2048))
        Address=ConnectSocket.getpeername()[0]
        self.WriteLog("Info","Start Thread session " + str(thread.get_ident()))
        try: # make sure exception would terminate the connection gracefully
            Response=self.HandleRequest(Request.getRecord(),Address)
            if Response:
                ResMessage=PkgHandle.Message(Response)
                ConnectSocket.send(ResMessage.ObjStr)
                self.additionalService(ConnectSocket)
            else:
                self.WriteLog("Error","Fail to handle request from Client " + Address )
                ConnectSocket.send("Error Request rejected")
        except ServerFatal , e:
            self.WriteLog("Error",'send error message to client: "%s"' % e.KrMessage)
            ConnectSocket.send("Error " + e.KrMessage )
        except ValueError , e:
            self.WriteLog("Error","Fail to retrieve message from client " + Address,
                              e.message)
            ConnectSocket.send('Error corrupted message' + Request.ObjStr)
        self.WriteLog("Debug","Finished Thread handling " +  str(thread.get_ident()))

    def Listen(self,ServerSock):
        # handle the Listen socket and open a new thread for each connection.
        while self.Running:
            (Content,Address)=ServerSock.accept()
            self.WriteLog("Info","Received Req from " + Address[0])
            thread.start_new_thread(self.runRequest,(Content,))
        self.WriteLog("Info","Finished Listening")

    def StopServer(self):
        self.Running=False
        self.ControlSock.close()
        self.WriteLog("Info","Stop due to request")
        self.stopLog()

    def HandleRequest(self,Request,ClientAddr):
        # handle kerberos request.
        # Request - any kerberos request type.
        # ClientAddr - String, the client address (IP part)
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
    # This class implements the ASServer
    # Configuration Parameters this class requires:
    # Name - string
    # Port - integer 1 - 65535. the port this server should listen
    # DB - connection string to database.
    # TGSServerName - the key name of TGS Server in the database.
    # optional parameters
    # LogFile - name of the logfile to write to. Default - No Log (just print to screen)
    # Encrypt - Encrypt method to use. valid values: AES,Simple
    # MaxConnect - Number of maximum active open connections. Default 3
    # LifeTime - period of Ticket Life Time in sec units. Default - 120 sec
    def VerifyRequest(self,Request,ClientAddr):
        if hasattr(Request,'Server'):
            # Verify the request have the relevant fields.
            client=self.DataBase.getClientRecord(Request.User)
            if type(None) == type(client):
                self.WriteLog("Error","user %s Rejected." % Request.User)
                raise ServerFatal("user %s Rejected." % Request.User)
            else:
                self.WriteLog("Debug","Client %s from %s has SPE entity: %s" %
                              (client.name,ClientAddr,client.spe.SPEType))
            tmpspe=client.spe
            # Generate random key and send via the SPE
            ClientKey=self.GenerateKey(6)
            tmpspe.sendMessage(ClientKey)
            Session=self._getSessionID(Request.User,Request.Server)
            Tkt=self.BuildTicket(Request.User,Request.Server,Session,ClientAddr)
            return (Tkt,ClientKey)
        else:
            self.WriteLog("Error","Illegal Request from client " + ClientAddr)
            raise ServerFatal("corrupted Message")

    def addClient(self,Client):
        # Update database with new client record.
        self.DataBase.addClient(Client)

    def LoadTGSKey(self,TGSServerName):
        try:
            self.TGSKey=self.DataBase.getServerKey(TGSServerName)
        except:
            raise ServerFatal('Fail to retrieve "%s" from DataBase' % TGSServerName )

    def _getSessionID(self,clientID,Server):
        # Generate unique identify for current session.
        return "%d-%s%s-%s" % (random.randint(1000000,10000000),time.time(),clientID,Server)

    def ServerInit(self,Config):
        super(Kr_AuthServer,self).ServerInit(Config)
        try:
            tmp=DBWrapper(Config.get('DB' , 'NA'))
            self.DataBase=tmp.Connect()
        except IOError , e:
            self.WriteLog("Error","Fail to load/read/connect to DataBase" ,
                          "Exception reason: " + e.message )
            raise ServerFatal("Fail to load/read/connect to DataBase: " + e.message )
        except Exception , e:
            self.WriteLog("Error","Fail to load/read/connect to DataBase" ,
                          "Exception reason: " + str(e.__class__)  ,
                          e.message if e.message else "" )
            raise ServerFatal("Fail to load/read/connect to DataBase: " + e.message , traceback)
        self.LoadTGSKey(Config['TGSServerName'])

    def BuildResponse(self,Ticket,Key):
        SerKey=self.TGSKey
        tmpEncObj=PkgHandle.EncObj(SerKey,Ticket,self.EncryptMethod)
        answer=PkgHandle.ResMessageAS(Ticket.TimeStamp,Ticket.Key,str(tmpEncObj) ,Ticket.user,Ticket.sessionID,
                                      Ticket.LifeTime)
        self.WriteLog("Debug","Encrypt response using key " + Key)
        EncAnswer=PkgHandle.EncObj(Key,answer,self.EncryptMethod)
        return str(EncAnswer)

class Kr_TGSServer(Kr_AbstractServer):
    # This class implements the TGS Server
    # Configuration Parameters this class requires:
    # Name - string
    # Port - integer 1 - 65535. the port this server should listen
    # DB - connection string to database.
    # optional parameters
    # LogFile - name of the logfile to write to. Default - No Log (just print to screen)
    # Encrypt - Encrypt method to use. valid values: AES,Simple
    # MaxConnect - Number of maximum active open connections. Default 3
    # LifeTime - period of Ticket Life Time in sec units. Default - 120 sec
    def ServerInit(self,Config):
        super(Kr_TGSServer,self).ServerInit(Config)
        try:
            tmp=DBWrapper(Config.get('DB' , 'NA'))
            self.DataBase=tmp.Connect()
        except IOError , e:
            self.WriteLog("Error","Fail to load/read/connect to DataBase" ,
                          'Exception reason: %s "%s"' % (e.strerror,e.filename,) )
            raise ServerFatal("Fail to load/read/connect to DataBase: " + e.strerror )
        except Exception , e:
            self.WriteLog("Error","Fail to load/read/connect to DataBase" ,
                          "Exception reason: " + str(e.__class__)  ,
                          e.message if e.message else "" )
            raise ServerFatal("Fail to load/read/connect to DataBase: " + e.message , traceback)

    def _getTicketKey(self,Server):
        ## Find the Server Private Key
        return self.DataBase.getServerKey(Server)

    def VerifyRequest(self,Request,ClientAddr):
        if hasattr(Request,'Tkt') and  hasattr(Request,'Auth'):
            Key=self.DataBase.getServerKey(self.Name)
            try: # verify Ticket and Auth Record can be decrypt.
                tmpEncObj=PkgHandle.EncObj(Key,Request.Tkt,self.EncryptMethod)
                Ticket=tmpEncObj.getObj()
                Key=Ticket.Key
                tmpEncObj=PkgHandle.EncObj(Key,Request.Auth,self.EncryptMethod)
                Auth=tmpEncObj.getObj()
            except Exception, e:
                self.WriteLog("Error","Fail to decrypt parts of the request",e.message)
                raise ServerFatal("Fail to read request. wrong key or wrong Cypher method")
            # Verify Ticket is still relevant.
            if not Ticket.expired:
                # verify Ticket content
                if Ticket.ValideAuthentication(Auth):
                    ServerTkt=self.BuildTicket(Auth.user,Request.Server,Auth.sessionID,ClientAddr)
                    return (ServerTkt,Ticket.Key)
                else:
                    self.WriteLog("Debug",str(Ticket),str(Auth))
                    self.WriteLog("Error","Authentication Failed. Auth Record don't match the Ticket request")
                    raise ServerFatal("Auth Record don't match the Ticket data")
                    return (None,None)
            else:
                self.WriteLog("Debug","Ticket expired at " + time.ctime(Ticket.TimeStamp + Ticket.LifeTime))
                self.WriteLog("Error","Ticket period expired. Ignore the request")
                raise ServerFatal("Ticket period expired. Session TimeOut")
                return (None,None)
        else: # this is not TGS request or the request message is corrupted
            self.WriteLog("Error","corrupted or unsupported message request from " + ClientAddr)
            raise ServerFatal("TGS Server received unsupported request type or corrupted request")

    def BuildResponse(self,Ticket,Key):
        try:
            SerKey=self._getTicketKey(Ticket.Server)
        except KeyError , e :
            ErrorMessage="Server %s (or %s) are not member of this kerberos domain" % (Ticket.Server,e.message)
            self.WriteLog("Error",ErrorMessage)
            return "Error: " + ErrorMessage
        tmpEncObj=PkgHandle.EncObj(SerKey,Ticket,self.EncryptMethod)
        answer=PkgHandle.ResMessageTGS(Ticket.TimeStamp,Ticket.Key,str(tmpEncObj))
        self.WriteLog("Debug","Encrypt TGS Server answer using Key " + Key )
        EncAnswer=PkgHandle.EncObj(Key,answer,self.EncryptMethod) # self.PassMap[Ticket.user],answer)
        return str(EncAnswer)

    def addServer(self,Server):
        # update database with new server record
        if hasattr(Server,'Key'):
            self.ServerList[Server.Name]=Server.Key
        else:
            self.WriteLog("Error","Illegal Server Record")

class GeneralServer(Kr_AbstractServer):
    # This class should be ancestor or each Server that supports kerberos protocol
    # Configuration Parameters this class requires:
    # Name - string
    # Port - integer 1 - 65535. the port this server should listen
    # Key - the key to Decrypt the Ticket. This key must be the same as define at Kerberos DataBase !
    # optional parameters
    # LogFile - name of the logfile to write to. Default - No Log (just print to screen)
    # Encrypt - Encrypt method to use. valid values: AES,Simple
    # MaxConnect - Number of maximum active open connections. Default 3
    # LifeTime - period of Ticket Life Time in sec units. Default - 120 sec
    def ServerInit(self,Config):
        self.myKey=Config['Key']
        self.WriteLog("Info","configuration loaded")

    def VerifyRequest(self,Request,ClientAddr):
        tmpEncObj=PkgHandle.EncObj(self.myKey,Request.Ticket,self.EncryptMethod)
        try:
            Ticket=tmpEncObj.getObj()
        except BaseException , e:
            self.WriteLog("Error","Fail to decrypt Ticket" , "%s: %s" % (str(e.__class__),e.message))
            Ticket = None
        if type(Ticket) is PkgHandle.KrTicket:
            # Verify the request is in the correct format.
            tmpEncObj=PkgHandle.EncObj(Ticket.Key,Request.Auth,self.EncryptMethod)
            AuthRec=tmpEncObj.getObj()
            if type(AuthRec) is PkgHandle.AuthRec:
                if not Ticket.expired:
                    # verify the Ticket is NOT Expired
                    if Ticket.ValideAuthentication(AuthRec):
                        # verify the Ticket is valid (have the same value as in the Auth Record)
                        self.WriteLog("Info","Authentication pass O.K")
                        Tkt=PkgHandle.BasicRec(AuthRec.TimeStamp + 1)
                        return (Tkt,Ticket.Key)
                    else:
                        self.WriteLog("Debug","Ticket     : " + str(Ticket))
                        self.WriteLog("Debug","Auth Record: " + str(AuthRec))
                        self.WriteLog("Error","Authentication Failed (Auth and Ticket don't match)")
                        raise ServerFatal("Authentication Failed: Ticket and auth rec don't Match")
                else:
                    self.WriteLog("Error","user Session (%s) LifeTime expired" % Request.Auth.user)
                    raise ServerFatal("Ticket period expired. Session TimeOut")
            else:
                self.WriteLog("Error","Authentication failed (wrong key)")
                raise ServerFatal("Authentication failed. failed to read auth Record")
        else:
            self.WriteLog("Error","Authentication failed (wrong key)")
            raise ServerFatal("Authentication failed. fail to read Ticket")
        return (None,None)

    def BuildResponse(self,Ticket,Key):
        Response=Ticket
        EncAnswer=PkgHandle.EncObj(Key,Response,self.EncryptMethod)
        self.WriteLog("Debug","Build Response: " + str(Response.TimeStamp) )
        return str(EncAnswer)

class clientRecord(object):
    # DataBase record.
    def __init__(self,cName,spe,description):
        self.name=cName
        self.spe=spe
        self.desc=description

class ServerRecord(object):
    # DataBase record
    def __init__(self,Name,Address,Key):
        self.Name=Name
        self.Address=Address
        self.Key=Key

class abstractSPE(object):
    # Ancestor SPE class - each inherit class must overwrite "sendMessage" method
    # connectInfo syntax SPE_Type:Destination. example: Mail:user@maildomain
    # this class DO NOT send message just print to screen.
    def __init__(self,connectInfo):
        self.__SPE=connectInfo

    def sendMessage(self,message,**destConf):
        # just print to screen the message.
        Size=50
        MessageList=[ "SPE send message via " + self.SPEType ,
                      "to " + self.SPEDest + ":",
                      message]
        print '*' * Size
        for line in MessageList:
           print "* %-*s*" % (Size - 3 , line)
        print '*' * Size

    @property
    def SPEType(self):
        SpeType=re.match("(\S+):",self.__SPE)
        return SpeType.group(1) if SpeType.group(1) else 'N/A'

    @property
    def SPEDest(self):
        speDest=self.__SPE.split(':')
        return speDest[1] if speDest else 'N/A'

class DBWrapper():
    # wrapper for database handling.
    # ConnectionStr - each database vendor has its own database string.
    # Connect - this method acts as Factory Pattern - return new Object of type
    #           that supports the required connection string. the return Object MUST
    #           be child of DBWrapper class

    def __init__(self,ConnectionStr):
        #username[/password]@myserver[:port][/myservice:dedicated][/instancename]
        #for file file@FileName
        self.__ConnStr=ConnectionStr

    def Connect(self):
        # Factory pattern - return new object.
        if re.match('^file',self.__ConnStr,re.IGNORECASE):
            tmpObj=DBcsvWrapper(self.__ConnStr)
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
    # this class implements the csv database handler (read the data from csv files)
    # connectStr syntax is file@path_to csv_file[@path_to csv_file]
    #   where first file should be the servers list the second file (optional) is
    #   the users definition file.
    def __init__(self,ConnectStr):
        self.fileList=ConnectStr.split('@')
        self.__clientList={}
        self.__ServerList={}

    def ReadCsv(self,FileName):
        # read csv file and split the fields
        dBFile=open(FileName,'r')
        Result=[]
        for line in  dBFile:
            tmp=line.strip("\n")
            clist=tmp.split(',')
            Result.append(clist)
        dBFile.close()
        return Result

    def Connect(self):
        ## Read Servers List
        for RecTuple in self.ReadCsv(self.fileList[1]):
           self.addServer(ServerRecord(RecTuple[0],RecTuple[1],RecTuple[2]))
        if len(self.fileList) > 2:
            # read clients list
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
        return self.__ServerList.get(ServerName)

##################################
# Exception definition
#################################

class ServerFatal(Exception):
    def __init__(self,*args,**Kwargs):
        super(ServerFatal,self).__init__(*args,**Kwargs)
        self.KrMessage=args[0] if len(args) > 0 else ""

if  __name__ == '__main__' :
    ## Implementation of kereberos servers (ASServer and TGS Server
    ## run only if this file is used as main file (wont run if this file is imported by other )
    print "This is Kerberos Server demonstration (Not Module ...)"
    ConfFile= sys.argv[1] if len(sys.argv) > 1 else 'Configuration/kerberosConfiguration.conf'
    print "Reading configuration file" , ConfFile
    ServerConf=PkgHandle.Config(ConfFile)
    KerberosServer=Kr_AuthServer(**ServerConf.AuthenticationServer)
    TGSServer=Kr_TGSServer(**ServerConf.TGSServer)
    thread.start_new_thread(KerberosServer.StartServer,())
    thread.start_new_thread(TGSServer.StartServer,())
    time.sleep(1)
    # replace the following if statement with infinite loop - to run servers without time limit
    if KerberosServer.Running and TGSServer.Running:
        time.sleep(600)
    KerberosServer.StopServer()
    TGSServer.StopServer()
    print "Server Finished ...."
