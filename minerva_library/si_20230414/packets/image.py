# pH @ LNA 06/04/2007

import struct

from si.packet import Packet


class Image(Packet):

    """Image.
    Image packet represents and unit of an image return by the server.

    When an acquisition starts, server return a list of Image packets. Each
    packet is identified (curr_packet) and carries a number of bytes from the
    image (img_bytes). CommandServer implements the logic to reconstruct the
    image defined by the list of Image packets.

    """

    def __init__(self):
        Packet.__init__(self)

        # public
        self.err_code = None
        self.img_id = None
        self.img_type = None
        self.serial_length = None
        self.parallel_length = None
        self.total_packets = None
        self.curr_packet = None
        self.offset = None
        self.img_bytes = None

        self.fmt = self.fmt + "iHHHHiiiI"
        self.length = struct.calcsize(self.fmt)

    def fromStruct(self, data):
        results = struct.unpack(self.fmt, data)

        self.length = results[0]
        self.id = results[1]
        self.cam_id = results[2]

        self.err_code = results[3]
        self.img_id = results[4]
        self.img_type = results[5]
        self.serial_length = results[6]
        self.parallel_length = results[7]
        self.total_packets = results[8]
        self.curr_packet = results[9] + 1
        self.offset = results[10]
        self.img_bytes = results[11]

        return True

    def __len__(self):
        return struct.calcsize(self.fmt)

    def __str__(self):
        return "<image packet>\nlength=%d\ncam_id=%d\nerr_code=%d\nimg_id=%d\nimg_type=%d\nserial_length=%d\n" \
               "parallel_length=%d\ntotal_packets=%d\ncurr_packet=%d\noffset=%d\nimg_bytes=%d\n" % (
                   self.length, self.cam_id, self.err_code, self.img_id, self.img_type, self.serial_length,
                   self.parallel_length, self.total_packets, self.curr_packet, self.offset, self.img_bytes)
