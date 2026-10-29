# pH @ LNA 06/04/2007

import struct
import copy

from si.packet import Packet


class Data(Packet):
    """Data.

    Data packet represents data returned by the server.

    Four kinds of data can be returned: Status, Done, AcquisitionStatus
    (not implemented yet) and ImageHeader (not implemented yet).
    """

    def __init__(self):
        Packet.__init__(self)

        # public
        self.err_code = None
        self.data_type = None
        self.byte_length = None

        self.fmt += "iHi"


class Status(Data):
    def __init__(self):
        Data.__init__(self)

        self.statuslist = None

        self.length = struct.calcsize(self.fmt)

    def fromStruct(self, data):
        results = struct.unpack(self.fmt, data[:16])

        self.length = results[0]
        self.id = results[1]
        self.cam_id = results[2]
        self.err_code = results[3]
        self.data_type = results[4]
        self.byte_length = results[5]

        # header without NULL byte
        self.statuslist = struct.unpack(">%ds" % (self.length - 16), data[16:])[0][:-1]

        return True

    def __len__(self):
        return self.length

    def __str__(self):
        return "<data packet (status 2002)>\n%s\n" % self.statuslist


class Done(Data):
    def __init__(self):
        Data.__init__(self)

        # public
        self.func_number = None

        # private
        self.fmt += "H"
        self.length = struct.calcsize(self.fmt)

    def fromStruct(self, data):
        results = struct.unpack(self.fmt, data)

        self.length = results[0]
        self.id = results[1]
        self.cam_id = results[2]
        self.err_code = results[3]
        self.data_type = results[4]
        self.byte_length = results[5]

        self.func_number = results[6]

        return True

    def __len__(self):
        return self.length

    def __str__(self):
        return "<done packet>\nlength=%d\nerr_code=%d\nfunc_number=%d\n" % (
            len(self), self.err_code, self.func_number)


class ImageHeader(Data):
    def __init__(self):
        Data.__init__(self)

        # public
        self.header = None

        # private
        # self._fmt = self._fmt + "s"
        self.length = struct.calcsize(self.fmt)

    def fromStruct(self, data):
        result = struct.unpack(self.fmt, data[:16])

        self.length = result[0]
        self.id = result[1]
        self.cam_id = result[2]
        self.err_code = result[3]
        self.data_type = result[4]
        self.byte_length = result[5]

        # header without NULL byte
        self.header = struct.unpack(">%ds" % (self.length - 16), data[16:])[0][
                      :-1]

        return True

    def __len__(self):
        return self.length

    def __str__(self):
        return "<image_header packet>\nlength=%d\nerr_code=%d\n" % (
            len(self), self.err_code)


class Sgl2Structure(Data):
    def __init__(self):
        Data.__init__(self)

        self.fmt += 'IBBIIHHiiiiii'
        self.length = struct.calcsize(self.fmt)

        self.sgl2settingslist = None

    def fromStruct(self, data):
        result = struct.unpack(self.fmt, data)

        self.length = result[0]
        self.id = result[1]
        self.cam_id = result[2]
        self.err_code = result[3]
        self.data_type = result[4]
        self.byte_length = result[5]

        result = result[6:]

        # public
        self.exptime = result[0]  # U32 Exposure time in ms
        self.number_of_readout_modes = result[1]  # Number of Readout Modes
        self.readout_mode_number = result[2]  # U8 Current Readout Mode
        self.average_n_images = result[3]  # U32 Number of Images to Average
        self.frames = result[4]  # U32 Number of Frames to Acquire
        self.acquisition_mode = result[5]  # U16 Acquisition Mode
        self.acquisition_type = result[6]  # U16 Acquisition Type
        self.serial_origin = result[7]  # I32 CCD Format Serial Origin
        self.serial_length = result[8]  # ?I32 CCD Format Serial Length
        self.serial_binning = result[9]  # I32 CCD Format Serial Binning
        self.parallel_origin = result[10]  # I32 CCD Format Parallel Origin
        self.parallel_length = result[11]  # I32 CCD Format Parallel Length
        self.parallel_binning = result[12]  # I32 CCD Format Parallel Binning

        return True

    def __len__(self):
        return self.length

    def __str__(self):
        return ("<si_image_settings structure 2008>\n"
                "exptime={0:d}\n"
                "number_of_readout_modes={1:d}\n"
                "read_out_mode={2:d}\n"
                "serial_origin={3:d}\n"
                "serial_length={4:d}\n"
                "serial_binning={5:d}\n"
                "parallel_origin={6:d}\n"
                "parallel_length={7:d}\n"
                "parallel_binning={8:d}"
                ).format(self.exptime, self.number_of_readout_modes,
                         self.readout_mode_number, self.serial_origin,
                         self.serial_length, self.serial_binning,
                         self.parallel_origin, self.parallel_length,
                         self.parallel_binning)


class CameraParameterStructure(Data):
    def __init__(self):
        Data.__init__(self)

        self.parameterlist = None
        self.length = struct.calcsize(self.fmt)

    def fromStruct(self, data):
        results = struct.unpack(self.fmt, data[:16])

        self.length = results[0]
        self.id = results[1]
        self.cam_id = results[2]
        self.err_code = results[3]
        self.data_type = results[4]
        self.byte_length = results[5]

        # header without NULL byte
        self.parameterlist = struct.unpack('>%ds' % (self.length - 16), data[16:])[0][:-1]

        return True

    def __str__(self):
        return self.parameterlist


class AcquisitionStatus(Data):
    def __init__(self):
        Data.__init__(self)

        # public
        self.exp_done_percent = None
        self.readout_done_percent = None
        self.relative_readout_position = None
        self.acquiring = None

        # private
        self.fmt += "HHIi"
        self.length = struct.calcsize(self.fmt)

    def fromStruct(self, data):
        results = struct.unpack(self.fmt, data)

        self.length = results[0]
        self.id = results[1]
        self.cam_id = results[2]
        self.err_code = results[3]
        self.data_type = results[4]
        self.byte_length = results[5]

        self.exp_done_percent = results[6]
        self.readout_done_percent = results[7]
        self.relative_readout_position = results[8]
        self.acquiring = results[9]

        return True

    def __len__(self):
        return self.length

    def __str__(self):
        return "<image_acquisition_status packet>\nlength=%d\nerr_code=%d\n" \
               "exposure_done=%d %%\nreadout_done=%d " \
               "%%\nrelative_readout_position=%d\n" % (
                   len(self), self.err_code, self.exp_done_percent,
                   self.readout_done_percent, self.relative_readout_position)


class XMLFileStructure(Data):
    def __init__(self):
        Data.__init__(self)

        self.length = struct.calcsize(self.fmt)

    def fromStruct(self, data):
        result = struct.unpack(self.fmt, data[:16])

        self.length = result[0]
        self.id = result[1]
        self.cam_id = result[2]
        self.err_code = result[3]
        self.data_type = result[4]
        self.byte_length = result[5]

        self.fileslist = struct.unpack(
            '>%ds' % (self.length - 16), data[16:])[0][:-1]

        return True

    def __len__(self):
        return self.length

    def __str__(self):
        return self.fileslist


class MenuInfoStructure(Data):
    def __init__(self):
        Data.__init__(self)

        self.menuinfolist = None
        self.length = struct.calcsize(self.fmt)

    def fromStruct(self, data):
        result = struct.unpack(self.fmt, data[:16])

        self.length = result[0]
        self.id = result[1]
        self.cam_id = result[2]
        self.err_code = result[3]
        self.data_type = result[4]
        self.byte_length = result[5]

        print("MenuInfoStructure: {}".format(self.data_type))

        self.menuinfolist = struct.unpack('>%ds' % (self.length - 16), data[16:])[0][:-1]

        return True

    def __str__(self):
        return self.menuinfolist
