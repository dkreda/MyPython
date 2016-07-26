__author__ = 'dkreda'

import KerberosServer,PkgHandle
import time,sys

class ServerSimulation(KerberosServer.Kr_AbstractServer):
    def ServerInit(self,Config):
        #Config=dict()
        if Config.has_key('DB'):
            DataBaseObj=KerberosServer.DBWrapper(Config['DB'])
            DataBaseObj=DataBaseObj.Connect()
            tmpRec=DataBaseObj.getServerRecord(Config['Name'])
            #PkgHandle.HostRec(ServerRec[0],ServerRec[1])
            #tmpRec=KerberosServer.ServerRecord()
            HostConf=PkgHandle.HostRec(tmpRec.Name,tmpRec.Address)
            self.port=HostConf.Port
            self.myKey=tmpRec.Key
            self.WriteLog("Debug","Load configuration from Kerberos DataBase")
            #self.DBName=Config['File']
            #for ServerRec in self.LoadDB():
            #    if ServerRec[0] == Config['Name']:
            #        tmpRec=PkgHandle.HostRec(ServerRec[0],ServerRec[1])
            #        self.port=tmpRec.Port
            #        self.myKey=ServerRec[2]
            #        self.WriteLog("Debug","Load configuration from Kerberos DataBase")
            #        break
        else:
            self.myKey=Config['Key']
        self.WriteLog("Info","configuration loaded")

    def VerifyRequest(self,Request,ClientAddr):
        #Request=PkgHandle.ServiceRequest()
        tmpEncObj=PkgHandle.EncObj(self.myKey,Request.Ticket,self.EncryptMethod)
        Ticket=tmpEncObj.getObj()
        if type(Ticket) is PkgHandle.Ticket:
            #Ticket=PkgHandle.Ticket()
            tmpEncObj=PkgHandle.EncObj(Ticket.Key,Request.Auth,self.EncryptMethod)
            AuthRec=tmpEncObj.getObj()
            #AuthRec=PkgHandle.AuthRec()
            if type(AuthRec) is PkgHandle.AuthRec:
                if AuthRec.TimeStamp + int(Ticket.LifeTime) >=time.time():
                    if AuthRec.user == Ticket.user and AuthRec.sessionID == Ticket.sessionID and \
                        AuthRec.TimeStamp == Ticket.TimeStamp and AuthRec.userAddr == Ticket.userAddr:
                        self.WriteLog("Info","Authentication pass O.K")
                        Tkt=PkgHandle.BasicRec(AuthRec.TimeStamp + 1)
                        return (Tkt,Ticket.Key)
                    else:
                        self.WriteLog("Debug","Ticket     : " + str(Ticket))
                        self.WriteLog("Debug","Auth Record: " + str(AuthRec))
                        self.WriteLog("Error","Authentication Failed (Auth and Tickrt don't match)")
                else:
                    self.WriteLog("Error","Session LifeTime expired")
            else:
                self.WriteLog("Error","Authentication failed (wrong key)")
        else:
            self.WriteLog("Error","Authentication failed (wrong key)")
        return None

    def BuildResponse(self,Ticket,Key):
        Response=Ticket  #  PkgHandle.BasicRec(Ticket)
        EncAnswer=PkgHandle.EncObj(Key,Response,self.EncryptMethod)
        self.WriteLog("Debug","Build Response: " + str(Response.TimeStamp) )
        return EncAnswer._Obj

if __name__ == '__main__' :
    Config={}
    if len(sys.argv) > 1:
        print "Loading configuration from CLI"
        Config['Name']=sys.argv[1]
        Config['File']='ServerList'
        Config['DB']='file@ServerList'
    Simulator=ServerSimulation(**Config)
    Simulator.StartServer()
    time.sleep(200)
    Simulator.StopServer()

