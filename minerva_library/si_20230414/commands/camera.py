# pH @ LNA 06/04/2007

# import struct
# import socket
# import select
# import time
# import array
# import os
# import numpy as np

import si.packets  # NOTE: this imports everything, see packets.__init__()


class CameraCommand(object):
    """CameraCommand.
    CameraCommand defines the interface for Camera Commands. Classes should
    inherit from this class and implement the command and result methods.

    The command method must return a Command packet of appropriate type with
    the required parameters set.

    The result method must return the packet expected to be returned by the
    server for a Command of the type returned by the command method.
    """

    def command(self):
        pass

    # def result(self, struct):
    # pass
    def result(self):
        pass


class GetStatusFromCamera(CameraCommand):
    def __init__(self):
        CameraCommand.__init__(self)

    def command(self):
        cmd = si.packets.Command()
        cmd.func_number = 1011

        return cmd

    def result(self):
        return si.packets.Status()


class SaveImage(CameraCommand):
    def __init__(self, filename, saveAs = 'U16 FITS'):
        CameraCommand.__init__(self)

        self.saveAsOptions = {'U16': 0,
                              'I16': 1,
                              'I32': 2,
                              'SGL': 3,
                              'U16 FITS': 0,
                              'I16 FITS': 1,
                              'I32 FITS': 2,
                              'SGL FITS': 3,
                              'U16 TIFF': 4,
                              'I16 TIFF': 5,
                              'I32 TIFF': 6,
                              'SGL TIFF': 7}
        self.saveAs = 0
        self.saveAsStr = 'U16 FITS'
        try:
            self.saveAs = self.saveAsOptions[saveAs]
            self.saveAsStr = saveAs
        except:
            self.saveAs = 0
            self.saveAsStr = 'U16 FITS'
        self.filename = filename

    def command(self):
        cmd = si.packets.Command()
        cmd.func_number = 1031

        cmd.addParam(">H", self.saveAs)
        cmd.addParam(">%ds" % (len(self.filename)+1), self.filename)

        return cmd

    def result(self):
        return si.packets.Done()

class SetAcquisitionMode(CameraCommand):
    def __init__(self, mode):
        CameraCommand.__init__(self)

        self.mode = mode

    def command(self):
        cmd = si.packets.Command()
        cmd.func_number = 1034

        cmd.addParam(">B", self.mode)  # acquisitiom mode (0-4)

        return cmd

    def result(self):
        return si.packets.Done()


class SetExposureTime(CameraCommand):
    def __init__(self, exp_time):
        CameraCommand.__init__(self)

        self.exp_time = float(exp_time)

    def command(self):
        cmd = si.packets.Command()
        cmd.func_number = 1035

        # exposure time as a double in seconds
        cmd.addParam(">d", float(self.exp_time))

        return cmd

    def result(self):
        return si.packets.Done()


class SetAcquisitionType(CameraCommand):
    def __init__(self, acq_type):
        CameraCommand.__init__(self)

        self.acq_type = acq_type

    def command(self):
        cmd = si.packets.Command()
        cmd.func_number = 1036

        # 0: light
        # 1: dark
        # 2: triggered
        # 3: NOT ASSIGNED!
        # 4: TDI external
        # 5: TDI internal
        cmd.addParam(">B", self.acq_type)

        return cmd

    def result(self):
        return si.packets.Done()


class Acquire(CameraCommand):
    def __init__(self):
        CameraCommand.__init__(self)

    def command(self):
        cmd = si.packets.Command()
        cmd.func_number = 1037

        return cmd

    def result(self):
        return si.packets.Done()


class SetMultipleFrameBufferMode(CameraCommand):
    def __init__(self, mode):
        CameraCommand.__init__(self)

        self.mode = mode

    def command(self):
        cmd = si.packets.Command()
        cmd.func_number = 1040

        # mode (0 single frame buffer, 1 multiple frame buffer)
        cmd.addParam(">B", self.mode)

        return cmd

    def result(self):
        return si.packets.Done()


class SetNumberOfFrames(CameraCommand):
    def __init__(self, num):
        CameraCommand.__init__(self)

        self.num = num

    def command(self):
        cmd = si.packets.Command()
        cmd.func_number = 1039

        cmd.addParam(">H", self.num)  # number of frames

        return cmd

    def result(self):
        return si.packets.Done()


class TerminateAcquisition(CameraCommand):
    def __init__(self):
        CameraCommand.__init__(self)

    def command(self):
        cmd = si.packets.Command()
        cmd.func_number = 1018

        return cmd

    def result(self):
        return si.packets.Done()


class RetrieveImage(CameraCommand):
    def __init__(self, type):
        CameraCommand.__init__(self)

        self.type = type  # 0 = U16, 1 = I16, 2 = I32, 3 = SGL

    def command(self):
        cmd = si.packets.Command()
        cmd.func_number = 1019

        cmd.addParam(">H", self.type)  # 0 = U16, 1 = I16, 2 = I32, 3 = SGL

        return cmd

    def result(self):
        return si.packets.Image()


class TerminateImageRetrieve(CameraCommand):
    def __init__(self):
        CameraCommand.__init__(self)

    def command(self):
        cmd = si.packets.Command()
        cmd.func_number = 1020

        return cmd

    def result(self):
        return si.packets.Done()


class GetImageHeader(CameraCommand):
    def __init__(self, buff):
        CameraCommand.__init__(self)

        self.buff = buff

    def command(self):
        cmd = si.packets.Command()
        cmd.func_number = 1024

        cmd.addParam(">H", self.buff)  # buffer (1-2)

        return cmd

    def result(self):
        return si.packets.ImageHeader()


class InquireAcquisitionStatus(CameraCommand):
    def __init__(self):
        CameraCommand.__init__(self)

    def command(self):
        cmd = si.packets.Command()
        cmd.func_number = 1017

        return cmd

    def result(self):
        return si.packets.AcquisitionStatus()


class SetReadoutMode(CameraCommand):
    def __init__(self, rom):
        CameraCommand.__init__(self)
        self.rom = rom

    def command(self):
        cmd = si.packets.Command()
        cmd.func_number = 1042

        cmd.addParam(">B", self.rom)

    def result(self):
        return si.packets.Done()


class SetCCDFormatParameters(CameraCommand):
    def __init__(self, SerialOrigin, SerialLength, SerialBinning,
                 ParallelOrigin, ParallelLength, ParallelBinning):
        CameraCommand.__init__(self)
        self.SerialOrigin = SerialOrigin
        self.SerialLength = SerialLength
        self.SerialBinning = SerialBinning
        self.ParallelOrigin = ParallelOrigin
        self.ParallelLength = ParallelLength
        self.ParallelBinning = ParallelBinning

    def command(self):
        cmd = si.packets.Command()
        cmd.func_number = 1043

        cmd.addParam(">i", self.SerialOrigin)
        cmd.addParam(">i", self.SerialLength)
        cmd.addParam(">i", self.SerialBinning)

        cmd.addParam(">i", self.ParallelOrigin)
        cmd.addParam(">i", self.ParallelLength)
        cmd.addParam(">i", self.ParallelBinning)

    def result(self):
        return si.packets.Done()


class SetCooler(CameraCommand):
    def __init__(self, state):
        CameraCommand.__init__(self)
        self.state = state

    def command(self):
        cmd = si.packets.Command()
        cmd.func_number = 1046

        cmd.addParam(">B", self.state)  # 0 = off, 1 = on

        return cmd

    def result(self):
        return si.packets.Done()


class SetSaveToFolderPath(CameraCommand):
    def __init__(self, path):
        CameraCommand.__init__(self)
        self.path = path

    def command(self):
        cmd = si.packets.Command()
        cmd.func_number = 1047

        cmd.addParam(">%ds" % len(self.path), self.path)  # Path

        return cmd

    def result(self):
        return si.packets.Done()


class GetCameraParameters(CameraCommand):
    def __init__(self):
        CameraCommand.__init__(self)

    def command(self):
        cmd = si.packets.Command()
        cmd.func_number = 1048

        return cmd

    def result(self):
        return si.packets.CameraParameterStructure()


class SetCameraSingleParameter(CameraCommand):
    def __init__(self, val, par):
        CameraCommand.__init__(self)
        self.val = val
        self.par = par

    def command(self):
        cmd = si.packets.Command()
        cmd.func_number = 1044

        cmd.addParam('>%ds' % self.val, self.par)

        return cmd

    def result(self):
        return si.packets.Done()


class GetSIImageSGLIISettings(CameraCommand):
    def __init__(self):
        CameraCommand.__init__(self)

    def command(self):
        cmd = si.packets.Command()
        cmd.func_number = 1041
        return cmd

    def result(self):
        return si.packets.Sgl2Structure()


class GetCameraXMLFile(CameraCommand):
    def __init__(self, xmlfile):
        CameraCommand.__init__(self)

        self.xmlfile = xmlfile

    def command(self):
        cmd = si.packets.Command()
        cmd.func_number = 1060

        cmd.addParam(">%ds" % len(self.xmlfile), self.xmlfile)

        return cmd

    def result(self):
        return si.packets.XMLFileStructure()


class GetImageAcquisitionTypes(CameraCommand):
    def __init__(self):
        CameraCommand.__init__(self)

    def command(self):
        cmd = si.packets.Command()
        cmd.func_number = 1061

    def result(self):
        return si.packets.MenuInfoStructure()


class SetContinuousClearMode(CameraCommand):
    def __init__(self, mode):
        CameraCommand.__init__(self)

        self.mode = mode  # (0 = Enable, 1 = Disable 1 Cycle, 2 = Disable)

    def command(self):
        cmd = si.packets.Command()
        cmd.func_number = 1062

        cmd.addParam('>B', self.mode)

    def result(self):
        return si.packets.Done()


class SetMultipleAcquisitionOptions(CameraCommand):
    def __init__(self, interval, nim):
        CameraCommand.__init__(self)

        self.interval = interval
        self.nim = nim

    def command(self):
        cmd = si.packets.Command()
        cmd.func_number = 1069

        cmd.addParam('>I', self.interval)
        cmd.addParam('>I', self.nim)

    def result(self):
        return si.packets.Done()


class GetAcquisitionModes(CameraCommand):
    def __init__(self):
        CameraCommand.__init__(self)

    def command(self):
        cmd = si.packets.Command()
        cmd.func_number = 1066

        return cmd

    def result(self):
        return si.packets.MenuInfoStructure()


class ResetCamera(CameraCommand):
    def __init__(self):
        CameraCommand.__init__(self)

    def command(self):
        cmd = si.packets.Command()
        cmd.func_number = 1063

    def result(self):
        return si.packets.Done()


class HardwareCameraReset(CameraCommand):
    def __init__(self):
        CameraCommand.__init__(self)

    def command(self):
        cmd = si.packets.Command()
        cmd.func_number = 1064

    def result(self):
        return si.packets.Done()


class OpenShutter(CameraCommand):
    NotImplementedError()


class CloseShutter(CameraCommand):
    NotImplementedError()


class LeaveShutter(CameraCommand):
    NotImplementedError()
