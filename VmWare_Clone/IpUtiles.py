#!/usr/bin/python

import math

class IPAddress_Error(Exception):
    pass

class IPAddress(object):
    def __init__(self,*OctOrStr):
        self.__StrToOct('.'.join([ str(oc) for oc in OctOrStr]))

    def __StrToOct(self,IpStr):
        tmpArray=IpStr.split('.')
        if tmpArray.__len__() == 4:
            self.Octets=[1,0,0,0]
            for i in range(4):
                try:
                    currentOct=int(tmpArray[i])
                    if currentOct < self.Octets[i]  or currentOct > 255:
                        raise IPAddress_Error("Octet %d (%s) of ip %s Out of range (%d-255)" %
                                          (i + 1,tmpArray[i],IpStr,self.Octets[i]))
                    self.Octets[i]=currentOct
                except ValueError as Err:
                    raise IPAddress_Error("Octet %i of ip %s should be integer:\n%s" %
                                          (i + 1,IpStr,Err.message))
        else:
            raise IPAddress_Error("IP Address (%s) should have exactly 4 octets" % IpStr)

    def __str__(self):
        return '.'.join([str(Oct) for Oct in self.Octets])

    def SubNet(self,BitMask):
        Result=[]
        for Oct in self.Octets:
            if BitMask > 8:
                Mask= 255
                BitMask -= 8
            else:
                Mask= 256 - 2 ** (8 - BitMask)
                BitMask=0
            Result.append(Oct & Mask)
        return '.'.join([str(Oct) for Oct in Result])

    def is_inSubNet(self,Ip,BitMask):
        return self.SubNet(BitMask) == Ip.SubNet(BitMask)

def BitToMask(Bits):
    if Bits >= 0 and Bits <= 32:
        Result=[0,0,0,0]
        i=0
        while Bits:
            if Bits < 8:
                Result[i]=256 - 2 ** (8 - Bits)
                break
            else:
                Result[i] = 255
                Bits -= 8
            i += 1
    else:
        raise IPAddress_Error("Bit Mask %d out ofs range 0-32" % Bits )
    return IPAddress(*Result)

def MaskToBits(IPMask):
    Mask=IPAddress(IPMask)
    Long=0
    for Oct in Mask.Octets:
        Long = Long *256 + Oct
    Long = 4294967296 - Long
    Result = math.log(Long,2)
    ## print " %g - is integer: %s" % (Result,Result.is_integer())
    ## print  "%15e ( %g )" % (Result - round(Result),Long)
    if abs(Result - round(Result))  < 0.0000000001:
        return int(32 - round(Result))
    raise IPAddress_Error("Illegal Mask bit Order %s" % IPMask)

if __name__ == '__main__':
    for ip in range(1,33):
        Ma=BitToMask(ip)
        print "Bits: %2d , Mask: %s" %(ip,Ma)
        print " - Bits Result: " , MaskToBits(Ma)

    Answer=""
    while not Answer == "quit":
        Answer=raw_input("Enetr IP or quit:")
        if Answer == "quit":
            break

        ##TestIP=__IPAddrs([int(Oct) for Oct in Answer.split('.')])
        TestIP=IPAddress(Answer)
        print "IP: %s" % TestIP
        TestIP=IPAddress(*[ int(oc) for oc in Answer.split(".") ] )
        print "IP: %s" % TestIP
        Answer=raw_input("Enetr Bit Mask:")
        if Answer.isalnum():
            Tmp=BitToMask(int(Answer))
        else:
            Tmp=Answer
            Answer=MaskToBits(Answer)
        print "Mask: %s (%s)" % (Tmp,Answer)
        print "SubNet : %s" % TestIP.SubNet(int(Answer))
        SecIP=IPAddress(TestIP)
        print "SecIP: %s in sub net: %s" % (SecIP,TestIP.is_inSubNet(SecIP,28))
        SecIP.Octets[3] += 25
        print "SecIP: %s in sub net: %s (%s)" % (SecIP,TestIP.is_inSubNet(SecIP,27),SecIP.SubNet(27))

