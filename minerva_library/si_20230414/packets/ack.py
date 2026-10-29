# -*- encoding: iso-8859-1 -*-

# pH @ LNA 06/04/2007

import struct

from si.packet import Packet


class Ack (Packet):

    """Ack.

    Ack packet represents an acknowledge from the server. It´s return for every command (except for TerminateAcquisition
    and InquireAcquisitionStatus Commands). Ack returns an accept flag indicating if the last command sent was accepted or not.
    """

    def __init__(self):
        Packet.__init__(self)

        # public
        self.accept = None

        # private
        self.fmt = self.fmt + "H"
        self.length = struct.calcsize(self.fmt)

    def fromStruct(self, data):

        result = struct.unpack(self.fmt, data)

        self.length = result[0]
        self.id = result[1]
        self.cam_id = result[2]
        self.accept = result[3]

        return True

    def __str__(self):
        return "<ack packet>\nlength=%d\ncam_id=%d\naccept=%s\n" % (len(self), self.cam_id, bool(self.accept))

    def __len__(self):
        return self.length
