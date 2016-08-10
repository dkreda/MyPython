__author__ = 'dkreda'
###############################################################################
#                                                                             #
# This file serves as MAIN program that implement Kerberos client             #
# and as module which supply class to implement client side that wish to      #
# run kerberos authentication.                                                #
#                                                                             #
# Kr_Client - class that help to implement kerberos client side               #
###############################################################################
import KerberosServer,PkgHandle
import time,sys
import socket
import re

################################################
#  Client class

class Kr_Client(KerberosServer.BaseClass):
    # Kr_Client: Kerberos Client side. this class should be used in application that
    #         participate as Kerberos Client. this class design with no user interface
    #         to be as mach generic as possible.
    # Configuration Parameters this class requires:
    # Name - string
    # ASServer - HostRec: contains name and address of ASServer.
    # TGSServer - HostRec: contains name and address of TGSServer
    # optional parameters
    # Encrypt - Encrypt method to use. valid values: AES,Simple
    # LogFile - name of the logfile to write to. Default - No Log (just print to screen)
    def __init__(self,UserName,**Configuration):
        super(Kr_Client,self).__init__(**Configuration)
        self.ASServer=Configuration['ASServer']
        self.TGS=Configuration['TGSServer']
        self.User=UserName
        self.Authenticated=False    # indicates the state of user
        self.TicketList={}          # cache of servers tickets
        self.sendAuthReq()

    def sendAuthReq(self):
        #send request for TGS ticket from ASServer (Phase1)
        ClientSoc=socket.socket()
        try:
            ClientSoc.connect(self.ASServer.getAddress())
            self.ClientAddress = ClientSoc.getsockname()[0]
            Request=PkgHandle.AuthRequest(self.User,self.TGS.Name,time.time())
            self.WriteLog("Debug","Send Request: " + str(Request))
            sendMessage=PkgHandle.Message(Request)
            # send the message
            ClientSoc.send(sendMessage.ObjStr)
            # wait for response - save in LastResponse for future use
            self.LastResponse=ClientSoc.recv(2048)
            self.WriteLog("Debug","Client received message from Server")
            ClientSoc.close()
        except socket.error , e:
            self.WriteLog("Error","Fail to connect to AS Server. Check configuration or if server is up")
            #print "Error - Fail to connect to AS Server. Check configuration or if server is up"
            self.LastResponse='Error - Failed to connect to AS Server: ' + e.message + e.strerror

    def Authenticate(self,Password):
        # use password to decrypt the last received message from server
        EncryptedResponse=PkgHandle.EncObj(Password,self.LastResponse,self.EncryptMethod)
        self.TgsTicket=EncryptedResponse.getObj()
        if not type(self.TgsTicket) is PkgHandle.ResMessageAS :
            # The message is NOT response from AS Server
            self.Authenticated=False
            if  re.match("Error",self.LastResponse,flags=re.IGNORECASE):
                self.WriteLog("Error",'Received from Server: "%s"' % self.LastResponse )
                self.ErrorMessage = self.LastResponse
            else:
                self.WriteLog("Error","wrong password")
        else: # this is response from AS Server
            self.Authenticated=True
        return  self.Authenticated

    def requestTicket(self,Server):
        # request a Ticket from TGS server (Phase2).
        # Server - is the required server we wish to get Ticket
        TktRequest=PkgHandle.TicketRequest(Server,self.getTGSTicket,self.getAuthRec(self.getTGSTimeStamp))
        ClientSoc=socket.socket()
        try:
            ClientSoc.connect(self.TGS.getAddress())
            sendMessage=PkgHandle.Message(TktRequest)
            self.WriteLog("Debug","Send request Ticket " + str(TktRequest.__class__) ,
                          "Content: " + str(TktRequest))
            ClientSoc.send(sendMessage.ObjStr)
            # wait for response from TGS Server
            EncResponse=ClientSoc.recv(2048)
            ClientSoc.close()
            tmpEncMess=PkgHandle.EncObj(self.getTGSKey,EncResponse,self.EncryptMethod)
            Response=tmpEncMess.getObj()
            self.WriteLog("Debug","Client received " + str(Response))
            # verify we get a Ticket from TGS server.
            if type(Response) is PkgHandle.ResMessageTGS:
                # This is response from TGS Server. save the relevant data for future use
               self.TicketList[Server]=ServerRecord(Response.Key,Response.Ticket,Response.TimeStamp)
               if hasattr(self,'ErrorMessage'): delattr(self,'ErrorMessage')
            elif re.match("Error",EncResponse):
                # received error message from Server.
                self.WriteLog("Error",'Client received error message from server: "%s"' % EncResponse)
                self.ErrorMessage=EncResponse
                if re.search('expired',EncResponse):
                    self.Authenticated=False
        except socket.error , e:
            self.WriteLog("Error","Failed to connect to TGS Server %s:%d" % self.TGS.getAddress())
            self.ErrorMessage = e.message + e.strerror

    def RequestService(self,ServerID,ServerAddress):
        # send Ticket to server "ServerID" and validate the server is safe (Phase3)
        # this method do the last phase of the client side kerberos protocol and if
        # the response answer from the server is correct return the open socket
        # for further interaction with the server.
        TimeStamp=self.getTimeStamp(ServerID)
        if TimeStamp is None:
            self.WriteLog("Error",'unsupported Service/Server "%s". or %s is not member of this kerberos domain' %
                         (ServerID,ServerID) )
            return None
        # Build the request.
        ServiceRequest=PkgHandle.ServiceRequest(self.getTicket(ServerID),self.getAuthRec(TimeStamp))
        ClientSoc=socket.socket()
        try:
            ClientSoc.connect(ServerAddress)
            sendMessage=PkgHandle.Message(ServiceRequest)
            self.WriteLog("Debug","Send Ticket to server: %s" % str(ServiceRequest))
            ClientSoc.send(sendMessage.ObjStr)
            if hasattr(self,'ErrorMessage'): delattr(self,'ErrorMessage')
            # wait for response from server
            EncResponse=ClientSoc.recv(2048)
            Key=self.getKey(ServerID)
            self.WriteLog("Debug","Received answer from %s." % ServerID ,
                          "Decrypt message using key " + Key )
            tmpEncMess=PkgHandle.EncObj(self.getKey(ServerID),EncResponse,self.EncryptMethod)
            # decrypt the response
            try:
                Response=tmpEncMess.getObj()
            except BaseException , e:
                Response=None
                self.WriteLog("Error","Fail to decrypt message from server" ,
                                   "%s: %s" % ( str( e.__class__ ) ,e.message ,) )
            self.WriteLog("Debug","Client received %s" % Response )
            if type(Response) is PkgHandle.BasicRec and Response.TimeStamp == TimeStamp +1:
                # response from server is O.K
                self.Title("Server %s is ready to serve (Server is safe)" % ServerID,
                           "Client get the right answer from server")
                return ClientSoc
            elif re.search("Error",EncResponse,re.IGNORECASE):
                # received error message from server
                self.WriteLog("Error","Received error message from server: " + EncResponse )
                if re.search('expired',EncResponse,re.IGNORECASE):
                    # Ticket expired - request new Ticket from TGS and resend the new Ticket to the server
                    self.WriteLog("Info","Ticket period Expired. request Ticket again")
                    # deletion of the Server record will trigger the sending request for Ticket from TGS
                    del self.TicketList[ServerID]
                    ClientSoc.close()
                    # recall to this method this time with no server record in the cache
                    return self.RequestService(ServerID,ServerAddress)
                else:
                    self.WriteLog("Debug","Unknown Server Error")
                    self.ErrorMessage=EncResponse
            else:
                self.WriteLog("Error","Service is not available (Authentication Failed)",
                              "fail to decrypt the message from server" ,
                              "or wrong challenge response from " + ServerID )
        except socket.error , e:
            self.WriteLog("Error","Fail to connect to server %s %s:%d" % (ServerID,ServerAddress[0],ServerAddress[1]))
            self.ErrorMessage=e.message + e.strerror
        ClientSoc.close()
        return None

    def getTicket(self,Server):
        # retrieve Ticket for Server from the cache.
        # if the Ticket not exists at cache - send request for Ticket to TGS server.
        if not self.TicketList.has_key(Server):
            # there is no Ticket in the cache send request for Ticket to TGS.
            self.requestTicket(Server)
        # retrieve from cache
        ServerRec=self.TicketList.get(Server,None)
        if ServerRec is None:
            self.WriteLog("Error",
                          self.ErrorMessage if hasattr(self,'ErrorMessage') else "Fail to get Ticket from TGS Server")
            return None
        else:
            return ServerRec.Ticket

    def getTimeStamp(self,Server):
        # retrieve TimeStamp of Server from the cache.
        # if there is no ServerRecord at cache - send request for Ticket to TGS server.
        if not self.TicketList.has_key(Server):
            self.requestTicket(Server)
        ServerRec=self.TicketList.get(Server,None)
        return ServerRec.TimeStamp if ServerRec else None

    def getKey(self,Server):
        # retrieve relevant encryption Key of Server from the cache.
        # if there is no ServerRecord at cache - send request for Ticket to TGS server.
        if not self.TicketList.has_key(Server):
            self.requestTicket(Server)
        ServerRec=self.TicketList.get(Server,None)
        return ServerRec.Key if ServerRec else None

    def getAuthRec(self,TimeStamp):
        # Build Auth Record
        if hasattr(self,'TgsTicket'):
            SessionID=self.TgsTicket.SessionID
            ClientAddress=self.ClientAddress
        else:
            self.WriteLog("Warning","Authentication record request before authentication process")
            SessionID=0
            ClientAddress='N/A'
        return PkgHandle.AuthRec(TimeStamp,self.User,SessionID,ClientAddress)

    @property
    def isExpired(self):
        if hasattr(self,'TgsTicket'):
            Expired=self.TgsTicket.TimeStamp + self.TgsTicket.LifeTime
            return Expired < time.time()
        return True

    @property
    def isAuthenticate(self):
        if self.Authenticated:
            return not self.isExpired
        return False

    @property
    def ServerErrorMessage(self):
        return self.ErrorMessage if hasattr(self,'ErrorMessage') else ''

    @property
    def getTGSTicket(self):
        if not hasattr(self,'TgsTicket'):
            self.authenticate()
        return self.TgsTicket.Ticket

    @property
    def getTGSTimeStamp(self):
        if not hasattr(self,'TgsTicket'):
            self.authenticate()
        return self.TgsTicket.TimeStamp

    @property
    def getTGSKey(self):
        if not hasattr(self,'TgsTicket'):
            self.authenticate()
        return self.TgsTicket.Key

###############################################
# Classes for Client implementation

class MenuItem(object):
    def __init__(self,Display,Value):
        self.Disp=Display
        self.Val=Value

    def __str__(self):
        return self.Disp

class Menu():
    def __init__(self):
        self.ItemList=[]

    def addItem(self,menuItem):
        self.ItemList.append(menuItem)

    def Display(self):
        count=1
        for Disp in self.ItemList:
            line="%-2d. %s" % (count,Disp.Disp)
            print line
            count += 1
        print '-' * 60

    def getSelected(self):
        self.Display()
        Answer=0
        while not Answer:
            Answer=raw_input("Enter Selection:")
            try:
                if int(Answer):
                    return self.ItemList[int(Answer)-1].Val
                else:
                    print "Esc Request ..."
                    return 0
            except Exception ,e:
                print "Exception " , e
                print e.message
                print "Enter a number between 1 to " , len(self.ItemList)
                Answer=0
            print "Debug - Selected " , Answer
                #raw_input("select again: ")

class ServerRecord():
    # This Record is used for the client cache
    # it saves for each server the following parameters:
    # Key - the Key that should be use to decrypt messages from this server
    # Ticket - the Ticket received from TGS Server for this server.
    # TimeStamp - the Time Stamp to use when sending the server request.
    def __init__(self,Key,Ticket,TimeStamp):
        self.Key=Key
        self.Ticket=Ticket
        self.TimeStamp=TimeStamp

###############################################
# General function - just for use at this main client implementation

def ReadCsvFile(FileName):
    CsvFile = open(FileName,'r')
    Result=[]
    for Line in CsvFile:
        Field=Line.split(',')
        Result.append(Field)
    CsvFile.close()
    return Result

def ClientAuth(ClientObj):
    # verify the password/Key entered by the user.
    # if password is O.K the message from ASServer can be decrypt
    MaxRetry=3
    InputMessage="Enter Password:"
    while MaxRetry:
      Password=raw_input(InputMessage)
      if ClientObj.Authenticate(Password):
          break
      MaxRetry = 0 if ClientObj.ServerErrorMessage else MaxRetry - 1
      InputMessage="Wrong Password Try again: "

###########################
# MAIN
###########################
if __name__ == '__main__':
  # sample - implementation of kerberos client. this implementation demonstrates how to use
  #         Kr_Client class when implementing client.
  ConfFile=sys.argv[1] if len(sys.argv) > 1 else 'Configuration/ClientConfiguration.conf'
  IniRecord=PkgHandle.Config(ConfFile)
  # Build configuration
  Configuration=IniRecord.ClientConfig
  Configuration['ASServer']=PkgHandle.HostRec('AS Server',Configuration['ASServer'])
  Configuration['TGSServer']=PkgHandle.HostRec('TGS',Configuration['TGSServer'])
  userName = raw_input("Enter user name (or press Enter to see list of available clients): ")
  if not userName:
      # Enter pressed - build menu of clients.
      txtMenu=Menu()
      for ClientRec in ReadCsvFile(Configuration['UsersList']):
          txtMenu.addItem(MenuItem(ClientRec[0],ClientRec[0]))
      txtMenu.addItem(MenuItem("Not existence User !","abcdefg"))
      userName=txtMenu.getSelected()
  ## initiate/Start the kerberos session.
  ClientExample=Kr_Client(userName,**Configuration)
  ClientAuth(ClientExample)
  while ClientExample.isAuthenticate:
      txtMenu=Menu()
      for SerRec in ReadCsvFile(Configuration['ServersFile']):
          txtMenu.addItem(MenuItem(SerRec[0],(SerRec[0],SerRec[1],)))
      txtMenu.addItem(MenuItem('Press 0 to exit',False))
      Service=raw_input("Enter Server name to connect (or press Enter to select from list):")
      Service=(Service,"") if Service else txtMenu.getSelected()
      if Service:
         print "Selected " , Service[0] , " Server address: " ,Service[1]
         Address=PkgHandle.HostRec(Service[0],Service[1])
         CSocket=ClientExample.RequestService(Address.Name,Address.getAddress())
         if CSocket:
           print "Client Receives Service From Server"
           CSocket.send("Thanks GoodBy from " + ClientExample.User )
           CSocket.close()
         elif ClientExample.isExpired:
             print "TGS Ticket expired."
             Answer=raw_input("Do you wish to authenticate again ? (Yes|No):")
             if re.search('Yes',Answer,re.IGNORECASE):
                 ClientExample.sendAuthReq()
                 ClientAuth(ClientExample)
         else:
           print "Error - Client Failed to get Service from " + Address.Name
      else: break