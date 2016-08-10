__author__ = 'dkreda'
###############################################################################
#                                                                             #
# This file serves as MAIN program that implement a Server that is a member   #
# in kerberos domain. The server just read the message from client and send   #
# simple string as response.                                                  #
# This show how to implement a server using the "GeneralServer" class.        #
# All you have to do is overwrite the method additionalService - and write    #
# all the service work at this method.                                        #
# usage: ServerSim.py [serverName]                                            #
#    if no parameters at CLI it would load the server configuration           #
#    from kerberosConfiguration.conf                                          #
#    if "ServerName" is given it would load the configuration from the        #
#     kerberos dataBase (from ServerList.csv)                                 #
###############################################################################
import KerberosServer,PkgHandle
import time,sys,thread

class ServerSimulation(KerberosServer.GeneralServer):
    def additionalService(self,ServerSocket):
        try:
            Request=ServerSocket.recv(2048)
            self.WriteLog("Info","Server received from client:",Request)
            ServerSocket.send("O.K - Ready to serve...")
            ServerSocket.close()
        except IOError , e:
           self.WriteLog("Error","Fail to continue session with client", e.strerror , e.filename )

if __name__ == '__main__' :
    Config={}
    if len(sys.argv) > 1:
        DBConnection='file@DataBase/ServerList.csv'
        print "Loading configuration of %s (Read from DataBase)" % sys.argv[1]
        Config['Name']=sys.argv[1]
        DataBaseObj=KerberosServer.DBWrapper(DBConnection)
        DataBaseObj=DataBaseObj.Connect()
        tmpRec=DataBaseObj.getServerRecord(Config['Name'])
        if tmpRec is not None:
            HostConf=PkgHandle.HostRec(tmpRec.Name,tmpRec.Address)
            Config['Port']=HostConf.Port
            Config['Key']=tmpRec.Key
            Config['LogFile']='C:\\Temp\\%s.log' % sys.argv[1]
            Config['Encrypt']='Simple'
        else:
            raise KerberosServer.ServerFatal("Fail to find %s in DataBase" % sys.argv[1])
    else:  # Load Configuration from File configuration
        iniFile='Configuration/kerberosConfiguration.conf'
        iniObj=PkgHandle.Config(iniFile)
        Config=iniObj.ServerConfiguration

    Simulator=ServerSimulation(**Config)
    # we start the server in separate thread just to limit the server
    # period running
    thread.start_new_thread(Simulator.StartServer,())
    time.sleep(1)
    if Simulator.Running:  time.sleep(200)
    Simulator.StopServer()