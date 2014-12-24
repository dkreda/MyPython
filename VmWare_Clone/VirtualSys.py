__author__ = 'danielk'

import PkgUtil
import pysphere

class VmHelper(object):
    def __init__(self,VsphereObj,**Conf):
        self.ViServer=VsphereObj
        self.Conf={}
        for Param,PVal in Conf:
            self.Conf[Param]=PVal

