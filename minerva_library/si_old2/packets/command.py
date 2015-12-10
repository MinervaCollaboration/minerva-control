# -*- encoding: iso-8859-1 -*-

# pH @ LNA 06/04/2007

import struct

from si.packet import Packet

class Param (object):
    """Param.

    Param represents parameter for Command packets. Each param have a value and format. Value is normal Python object
    and format is the equivalent binary representation (defined by SI's implementation). See Packet documentation for more
    information on packet representations.
    """

    def __init__ (self, fmt, value):
        self.fmt = fmt
        self.value = value

    def __len__ (self):
        return struct.calcsize (self.fmt)

    def toStruct (self):
        return struct.pack (self.fmt, self.value)

class Command (Packet):
    """Command.

    Command represents a Command to send to SI's server. Each command have an function number (defined by SI) and a
    list of parameters. Commands are built by defining a function number and add parameters. Then the toStruct method takes
    care of the transformation to SI binary representation.


    """

    def __init__ (self):
        Packet.__init__ (self)

        # public
        self.func_number = None

        # private
        self.id = 128
        self.params = []
        self.param_length = 0      

        self._fmt = self._fmt + "HH"

        self.length = struct.calcsize (self._fmt)

    def addParam (self, fmt, value):
        param = Param (fmt, value)

        self.param_length += len(param)
        self.params.append (param)

    def toStruct (self):

        cmd = struct.pack (self._fmt,
                           self.length + self.param_length,
                           self.id,
                           self.cam_id,
                           self.func_number,
                           self.param_length)

        lfmt = self._fmt
        for param in self.params:
            lfmt += param.fmt[1:]
            cmd = cmd+struct.pack (param.fmt, param.value)

        return cmd

    def __len__ (self):
        return self.length + self.param_length

    def __str__ (self):
        s = "<command packet>\nlength=%d\ncam_id=%d\nfunc_number=%d\nparam_length=%d\n" % (len(self), self.cam_id,
                                                                                           self.func_number, self.param_length)

        for i, param in enumerate(self.params):
            s += "param%d=%s\n" % (i+1, str(param.value))

        return s
