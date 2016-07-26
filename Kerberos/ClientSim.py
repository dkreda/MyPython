__author__ = 'dkreda'

import KerberosServer,PkgHandle,Ini
import time,sys
import socket
import re



class MenuItem(object):
    def __init__(self,Display,Value):
        self.Disp=Display
        self.Val=Value

    def __str__(self):
        return self.Disp

class Menue():
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
    def __init__(self,Key,Ticket,TimeStamp):
        self.Key=Key
        self.Ticket=Ticket
        self.TimeStamp=TimeStamp


################################################
#  Client class

class Kr_Client(KerberosServer.BaseClass):
    def __init__(self,UserName,AuthServer,TGSServer):
        #####  This is just for test I should replace it by Servers Name / Records
        self.ASServer=AuthServer
        self.TGS=TGSServer
        self.User=UserName
        #self.EncMethod="AES"
        self.Authenticated=False
        self.TicketList={}
        self.sendAuthReq()

    def sendAuthReq(self):
        ClientSoc=socket.socket()
        try:
            ClientSoc.connect(self.ASServer.getAddress())
            self.ClientAddress = ClientSoc.getsockname()[0]
            Request=KerberosServer.AuthReq(self.User,self.TGS.Name,time.time())
            print "Debug --  send " , Request
            sendMessage=PkgHandle.Message(Request)
            ClientSoc.send(sendMessage.ObjStr)
            self.LastResponse=ClientSoc.recv(2048)
            print "Debug -- Client Received Encrypted message"
            ClientSoc.close()
        except socket.error , e:
            print "Error - Fail to connect to AS Server. Check configuration or if server is up"
            self.LastResponse='Error - Failed to connect to AS Server: ' + e.message + e.strerror

    def Authenticate(self,Password):
        EncryptedResponse=PkgHandle.EncObj(Password,self.LastResponse)
        self.TgsTicket=EncryptedResponse.getObj()
        if not type(self.TgsTicket) is PkgHandle.ResMessageAS :
            self.Authenticated=False
            if  re.match("Error",EncryptedResponse._Obj,flags=re.IGNORECASE):
                print 'Error - Received from Server: "%s"' % EncryptedResponse._Obj
                self.ErrorMessage = EncryptedResponse._Obj
            else:
                print "Error - wrong password"
        else:
            self.Authenticated=True
        return  self.Authenticated

    def requestTicket(self,Server):
        TktRequest=KerberosServer.TicketRequest(Server,self.getTGSTicket,self.getAuthRec(self.getTGSTimeStamp))
        ClientSoc=socket.socket()
        try:
            ClientSoc.connect(self.TGS.getAddress())
            sendMessage=PkgHandle.Message(TktRequest)
            print "Debug - send Request Ticket: " , TktRequest
            print "\tContent: " , str(TktRequest)
            ClientSoc.send(sendMessage.ObjStr)
            EncResponse=ClientSoc.recv(2048)
            tmpEncMess=PkgHandle.EncObj(self.getTGSKey,EncResponse)
            Response=tmpEncMess.getObj()
            print "Debug -- Client Received " , Response
            if type(Response) is PkgHandle.ResMessageTGS:
               #Response=PkgHandle.ResMessageTGS()
               self.TicketList[Server]=ServerRecord(Response.Key,Response.Ticket,Response.TimeStamp)
               if hasattr(self,'ErrorMessage'): delattr(self,'ErrorMessage')
            elif re.match("Error",EncResponse):
                print 'Error - Client received error messsage from server: "%s"' % EncResponse
                self.ErrorMessage=EncResponse
        except socket.error , e:
            print "Error - Failed to connect to TGS Server"
            self.ErrorMessage = e.message + e.strerror

    def getTicket(self,Server):
        if not self.TicketList.has_key(Server):
            self.requestTicket(Server)
        ServerRec=self.TicketList.get(Server,None)
        #ServerRec=ServerRecord()
        return ServerRec.Ticket if ServerRec else None

    def getTimeStamp(self,Server):
        if not self.TicketList.has_key(Server):
            self.requestTicket(Server)
        ServerRec=self.TicketList.get(Server,None)
        #ServerRec=ServerRecord()
        return ServerRec.TimeStamp if ServerRec else None

    def getKey(self,Server):
        if not self.TicketList.has_key(Server):
            self.requestTicket(Server)
        ServerRec=self.TicketList.get(Server,None)
        #ServerRec=ServerRecord()
        return ServerRec.Key if ServerRec else None

    def RequestService(self,ServerID,ServerAddress):
        TimeStamp=self.getTimeStamp(ServerID)
        if TimeStamp is None:
            print 'Error - unsupported Service/Server "%s". or %s is not member of this kerberos domain' % \
                  (ServerID,ServerID)
            return None

        ServiceRequest=PkgHandle.ServiceRequest(self.getTicket(ServerID),self.getAuthRec(TimeStamp))
        ClientSoc=socket.socket()
        try:
            ClientSoc.connect(ServerAddress)
            sendMessage=PkgHandle.Message(ServiceRequest)
            print "Debug - send Ticket to Server: " , ServiceRequest
            ClientSoc.send(sendMessage.ObjStr)
            if hasattr(self,'ErrorMessage'): delattr(self,'ErrorMessage')
            EncResponse=ClientSoc.recv(2048)
            Key=self.getKey(ServerID)
            print "Debug - Received Answer from " + ServerID + ". decrypt message using key " , Key
            tmpEncMess=PkgHandle.EncObj(self.getKey(ServerID),EncResponse)
            Response=tmpEncMess.getObj()
            print "Debug -- Client Received " , Response
            #Response=PkgHandle.BasicRec()
            if type(Response) is PkgHandle.BasicRec and Response.TimeStamp == TimeStamp +1:
                print "Service is Ready to serve you (Server authenticated)"
                return ClientSoc
            elif re.match("Error",EncResponse,re.IGNORECASE):
                print "Error - Received error message from server: " + EncResponse
                self.ErrorMessage=EncResponse
            else:
                print "Error - Service is not available (Authentication Failed)"
        except socket.error , e:
            print "Error - Fail to connect to " , ServerID
            self.ErrorMessage=e.message + e.strerror

        ClientSoc.close()
        return None

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

    def getAuthRec(self,TimeStamp):
        if hasattr(self,'TgsTicket'):
            #TimeStamp=self.TgsTicket.TimeStamp
            SessionID=self.TgsTicket.SessionID
            ClientAddress=self.ClientAddress
        else:
            #TimeStamp=-1
            print "Warning - Authentication record request before authentication process"
            SessionID=0
            ClientAddress='N/A'
        return PkgHandle.AuthRec(TimeStamp,self.User,SessionID,ClientAddress)




###########################
# MAIN
###########
# Global Parameters
#################################

if __name__ == '__main__':
  ConfFile=sys.argv[1] if len(sys.argv) > 1 else 'ClientConfiguration.conf'
  IniRecord=Ini.INIFile(ConfFile)
  Configuration=IniRecord.getSection('ClientConfig')
  AS_Server=PkgHandle.HostRec('AS Server',Configuration['ASServer']) #  'localhost',1111)
  TGS_Server=PkgHandle.HostRec('TGS',Configuration['TGS'])
  userName = raw_input("Enter user name: ")
  ClientExample=Kr_Client(userName,AS_Server,TGS_Server)
  MaxRetry=3
  InputMessage="Enter Password:"

  while MaxRetry:
      Password=raw_input(InputMessage)
      if ClientExample.Authenticate(Password):
          break
      MaxRetry = 0 if ClientExample.ServerErrorMessage else MaxRetry - 1
      InputMessage="Wrong Password Try again: "

  while ClientExample.isAuthenticate:
      ConfFile = open(Configuration['ServersFile'],'r')
      txtMenu=Menue()
      for Line in ConfFile:
          Field=Line.split(',')
          txtMenu.addItem(MenuItem(Field[0],(Field[0],Field[1])))
      ConfFile.close()
      txtMenu.addItem(MenuItem('Press 0 to exit',False))
      Service=txtMenu.getSelected()
      if Service:
        print "Selected " , Service[0] , " Server address: " ,Service[1]
        Address=PkgHandle.HostRec(Service[0],Service[1])
        CSocket=ClientExample.RequestService(Address.Name,Address.getAddress())
        if CSocket:
          print "Client Recieves Servise From Server"
          CSocket.send("Thanks GoodBy from " + ClientExample.User )
          CSocket.close()
        else:
          print "Error - Client Failed to get Service from " + Address.Name
      else: break

  print "Just for test ..."
  ClientExample.RequestService("ooops",('localhost',25))
