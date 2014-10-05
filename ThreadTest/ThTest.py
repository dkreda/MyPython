__author__ = 'danielk'

import threading
import time

########################
# Global Variables
########################

G_ErrCounter=3
G_Dict={ "First" : "This is the content" ,
         "1.1.1.1" : "Ip Example" ,
         "2.2.2.2" : { "State" : "O.K" ,
                       "Next" : 8} }


def ThFun(LocDict):
    global G_ErrCounter
    print "This is Thread Target Function with no "
    print "NoArgs Global Variables:"
    print "G_ErrCounter : %d" % G_ErrCounter
    print "G_Dict (Local Instance) :"
    print LocDict
    print "The no args thread is going to sleep 3 Sec"
    time.sleep(3)
    G_ErrCounter += 2
    LocDict['2.2.2.2']['State']="End Thread"
    print "No Args thread Terminate ...."



Th1=threading.Thread(target=ThFun,name="Test1",args=(G_Dict,))  # ,args=(4,"Hey","Yofi",)
print "Before Thread Start: "
print "G_ErrCounter : %d" % G_ErrCounter
print "G_Dict :"
print G_Dict
print "==== Main Thread ...."
print "Number of active Threads: %d" % threading.active_count()

print "Start to test ...."
Th1.start()
print "Main : Number of active Threads: %d " % threading.active_count()
while (Th1.isAlive()):
    print "Thread %s still run ...." % Th1.getName()
    time.sleep(1)

print "After Thread Finished :"
print "Number of active Threads: %d" % threading.active_count()
print "G_ErrCounter : %d" % G_ErrCounter
print "G_Dict :"
print G_Dict