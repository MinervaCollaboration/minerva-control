# -*- encoding: iso-8859-1 -*-

# pH @ LNA 06/04/2007

import struct
import socket
import select
import time
import array
import os
import numpy as np

from si.packets import *

########################################################################################################################

class CameraCommand (object):
    """CameraCommand.

    CameraCommand defines the interface for Camera Commands. Class should inherities from this class and implement
    the command and result methods.

    command method must return return and Command packet of appropriate type with the required parameteres seted.

    result method must returns the packet expected to be return by the server for a Command of the type returned by the command method.

    """

    def command (self):
        pass

    def result (self, struct):
        pass

########################################################################################################################

class GetStatusFromCamera (CameraCommand):

    def __init__ (self):
        CameraCommand.__init__ (self)

    def command (self):

        cmd = Command ()
        cmd.func_number = 1011

        return cmd

    def result (self):

        return Status ()

########################################################################################################################
#
# DEPRECATED COMMAND
#
# class DirectAcquire (CameraCommand):
#
#     def __init__ (self, texp, mode, buff, img_type, name):
#         CameraCommand.__init__ (self)
#
#         self.texp = texp
#         self.mode = mode
#         self.buff = buff
#         self.img_type = img_type
#         self.name = name
#
#     def command (self):
#
#         cmd = Command ()
#         cmd.func_number = 1012
#
#         cmd.addParam (">I", self.texp) # exposure time
#         cmd.addParam (">H", self.mode) # mode (1-4)
#         cmd.addParam (">H", self.buff) # buffer number (1-2)
#         cmd.addParam (">H", self.img_type) # save as (0-7)
#         cmd.addParam (">%ds" % len(self.name), self.name) # name
#
#         return cmd
#
#     def result (self):
#
#         return Image ()
#
########################################################################################################################

class SetAcquisitionMode (CameraCommand):

    def __init__ (self, mode):
        CameraCommand.__init__ (self)

        self.mode = mode

    def command (self):
        cmd = Command ()
        cmd.func_number = 1034

        cmd.addParam (">B", self.mode) # acquisitiom mode (0-4)
           
        return cmd

    def result (self):
        return Done ()

########################################################################################################################

class SetExposureTime (CameraCommand):

    def __init__ (self, exp_time):
        CameraCommand.__init__ (self)

        self.exp_time = float(exp_time)

    def command (self):
        cmd = Command ()
        cmd.func_number = 1035

        cmd.addParam (">d", float(self.exp_time)) # exposure time as a double in seconds


        return cmd

    def result (self):
        return Done ()

########################################################################################################################

class SetAcquisitionType (CameraCommand):

    def __init__ (self, acq_type):
        CameraCommand.__init__ (self)

        self.acq_type = acq_type

    def command (self):
        cmd = Command ()
        cmd.func_number = 1036

        cmd.addParam (">B", self.acq_type) # acquisition type (0-5)
           
        return cmd

    def result (self):
        return Done ()

########################################################################################################################

class Acquire (CameraCommand):

    def __init__ (self):
        CameraCommand.__init__ (self)

    def command (self):

        cmd = Command ()
        cmd.func_number = 1037

        return cmd

    def result (self):

        return Done ()

########################################################################################################################

class SetMultipleFrameBufferMode (CameraCommand):

    def __init__ (self, mode):
        CameraCommand.__init__ (self)

        self.mode = mode

    def command (self):
        cmd = Command ()
        cmd.func_number = 1040

        cmd.addParam (">B", self.mode) # mode (0 single frame buffer, 1 multiple frame buffer)
           
        return cmd

    def result (self):
        return Done ()
 
########################################################################################################################

class SetNumberOfFrames (CameraCommand):

    def __init__ (self, num):
        CameraCommand.__init__ (self)

        self.num = num

    def command (self):
        cmd = Command ()
        cmd.func_number = 1039

        cmd.addParam (">H", self.num) # number of frames
           
        return cmd

    def result (self):
        return Done ()

########################################################################################################################

class TerminateAcquisition (CameraCommand):

    def __init__ (self):
        CameraCommand.__init__ (self)

    def command (self):
        cmd = Command ()
        cmd.func_number = 1018

        return cmd

    def result (self):
        return Done ()

########################################################################################################################

class RetrieveImage (CameraCommand):

    def __init__ (self, type):
        CameraCommand.__init__ (self)

        self.type=type # 0 = U16, 1 = I16, 2 = I32, 3 = SGL

    def command (self):
        cmd = Command ()
        cmd.func_number = 1019

        cmd.addParam (">H", self.type) # 0 = U16, 1 = I16, 2 = I32, 3 = SGL

        return cmd

    def result (self):
        return Image ()

########################################################################################################################

class GetImageHeader (CameraCommand):

    def __init__ (self, buff):
        CameraCommand.__init__ (self)

        self.buff = buff

    def command (self):
        cmd = Command ()
        cmd.func_number = 1024

        cmd.addParam (">H", self.buff) # buffer (1-2)

        return cmd

    def result (self):
        return ImageHeader ()

########################################################################################################################

class InquireAcquisitionStatus (CameraCommand):

    def __init__ (self):
        CameraCommand.__init__ (self)

    def command (self):
        cmd = Command ()
        cmd.func_number = 1017

        return cmd

    def result (self):
        return AcquisitionStatus ()

########################################################################################################################

class SetReadoutMode(CameraCommand):

    def __init__(self,rom):
        CameraCommand.__init__ (self)
        self.rom = rom

    def command(self):
        cmd = Command()
        cmd.func_number = 1042

        cmd.addParam(">B",self.rom)

    def result(self):
        return Done ()

########################################################################################################################

class SetCCDFormatParameters(CameraCommand):

    def __init__(self,SerialOrigin,SerialLength,SerialBinning,ParallelOrigin,ParallelLength,ParallelBinning):
        CameraCommand.__init__ (self)
        self.SerialOrigin = SerialOrigin
        self.SerialLength = SerialLength
        self.SerialBinning = SerialBinning
        self.ParallelOrigin = ParallelOrigin
        self.ParallelLength = ParallelLength
        self.ParallelBinning = ParallelBinning

    def command(self):
        cmd = Command()
        cmd.func_number = 1043

        cmd.addParam(">i",self.SerialOrigin)
        cmd.addParam(">i",self.SerialLength)
        cmd.addParam(">i",self.SerialBinning)

        cmd.addParam(">i",self.ParallelOrigin)
        cmd.addParam(">i",self.ParallelLength)
        cmd.addParam(">i",self.ParallelBinning)

    def result(self):
        return Done ()

########################################################################################################################

class SetCooler(CameraCommand):

    def __init__(self,state):
        CameraCommand.__init__ (self)
        self.state = state

    def command(self):
        cmd = Command()
        cmd.func_number = 1046

        cmd.addParam(">B",self.state) # 0 = off, 1 = on

        return cmd

    def result(self):
        return Done ()

########################################################################################################################

class SetSaveToFolderPath(CameraCommand):

    def __init__(self,path):
        CameraCommand.__init__ (self)
        self.path = path

    def command(self):
        cmd = Command()
        cmd.func_number = 1047

        cmd.addParam (">%ds" % len(self.path), self.path) # Path

    def result(self):
        return Done ()

########################################################################################################################

class GetCameraParameter(CameraCommand):

    def __init__(self):
        CameraCommand.__init__ (self)

    def command(self):
        cmd = Command()
        cmd.func_number = 1048

        return cmd

    def result(self):
        return CameraParameterStructure()

########################################################################################################################

class GetSIImageSGLIISettings(CameraCommand):

    def __init__(self):
        CameraCommand.__init__ (self)

    def command(self):
        cmd = Command()
        cmd.func_number = 1041

        return cmd

    def result(self):
        return SIImageSGLIISettings ()

########################################################################################################################

class GetCameraXMLFile(CameraCommand):

    def __init__(self,xmlfile):
        CameraCommand.__init__ (self)

        self.xmlfile = xmlfile

    def command(self):
        cmd = Command()
        cmd.func_number = 1060

        cmd.addParam(">%ds"%len(self.xmlfile),self.xmlfile)

    def result(self):
        return Done ()

########################################################################################################################

class GetImageAcquisitionTypes(CameraCommand):

    def __init__(self):
        CameraCommand.__init__(self)

    def command(self):
        cmd = Command()
        cmd.func_number = 1061

    def result(self):
        return Done ()

########################################################################################################################

class SetContinuousClearMode(CameraCommand):

    def __init__(self,mode):
        CameraCommand.__init__(self)

        self.mode = mode # (0 = Enable, 1 = Disable 1 Cycle, 2 = Disable)

    def command(self):
        cmd = Command()
        cmd.func_number = 1062

        cmd.addParam('>B',self.mode)

    def result(self):
        return Done ()

########################################################################################################################

class ResetCamera(CameraCommand):

    def __init__(self):
        CameraCommand.__init__(self)

    def command(self):
        cmd = Command()
        cmd.func_number = 1063

    def result(self):
        return Done ()

########################################################################################################################

class HardwareCameraReset(CameraCommand):

    def __init__(self):
        CameraCommand.__init__(self)

    def command(self):
        cmd = Command()
        cmd.func_number = 1064

    def result(self):
        return Done ()

########################################################################################################################
