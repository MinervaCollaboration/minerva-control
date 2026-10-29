# pH @ LNA 06/04/2007

# import struct
import socket
import select
import time
import numpy as np
# import os
import time

import logging

# import array

# from si.packet import Packet
from si.packets import *
from si.commands import *

log = logging.getLogger(__name__)

class AckException(Exception):

    '''
    Raise when acknowledge is not accepted by the serve.
    '''

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class SIClient (object):

    """SIClient.

    SIClient communicates with the SI server. SIClient execute CameraCommand's
     using the executeCommand method.
    """

    def __init__(self, host, port):

        self.host = host
        self.port = port

        self.buff = ""

        self.sk = None

    def connect(self):

        try:
            self.sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sk.connect((self.host, self.port))
            self.sk.settimeout(10)
        except socket.error, e:
            raise e

    def disconnect(self):

        if not self.sk:
            return

        self.sk.close()

    def recv(self, n):
        """
        Receive n bytes from the server.

        This method takes care of underrrun and overrun conditions and assure
        correct framing. The method will ask the socket for n bytes and make
        sure that the return value contain exactly this amount of bytes.
        """

        if len(self.buff) > 0:
            log.warning("Buffer not empty...")

        # if buffer isn't empty, return it and clear it
        bytes_to_receive = n - len(self.buff)

        bytes_received = self.buff
        self.buff = ""

        retries = 0

        # log.debug("bytes to receive %d (received %d)" %
        #               (bytes_to_receive, len(bytes_received)))

        while bytes_to_receive > 0:

            # log.debug("bytes to receive %d" % bytes_to_receive)
            this_try = self.sk.recv(bytes_to_receive)

            # log.debug("bytes received on this try %d" % len(this_try))
            bytes_to_receive -= len(this_try)

            bytes_received += this_try
            retries += 1

        ret = ""

        if len(bytes_received) > n:
            # we received more then one packet, get the packet and put the rest
            # on a buffer
            self.buff = bytes_received[n:]
            ret = bytes_received[:n]
            log.debug("buffer overrrun")
        else:
            ret = bytes_received

        # log.debug("> framing retries %d (return length %d)" %
        #               (retries, len(ret)))

        return ret

    def executeCommand(self, cmd, noAck=False):
        """
        Execute a CameraCommand command.

        This method sends the CameraCommand command to the server and waits
        for the server to respond. If the server responds with an Ack packet,
        we continue to listen on the socket (using select polling) waiting for
        Data or Image packets.
        """

        if not self.sk:
            try:
                self.connect()
            except socket.error, e:
                raise e

        cmd_to_send = cmd.command()
        log.debug("cmd is: {}".format(cmd_to_send))

        bytes_sent = self.sk.send(cmd_to_send.toStruct())
        log.debug("%d bytes sent" % bytes_sent)

        while True:

            ret = select.select([self.sk], [], [])

            if not ret[0]:
                break

            if ret[0][0] == self.sk:

                header = Packet()
                header_data = self.recv(len(header))
                header.fromStruct(header_data)

                if header.id == 129:
                    ack = Ack()
                    ack.fromStruct(
                        header_data + self.recv(header.length - len(header)))
                    log.debug(ack)
                    # TODO: Figure out why do I need this sleep here. If Idon't do this, some commands are not
                    # TODO: performed. I really don't know why!
                    time.sleep(0.1)
                    # return ack
                    if not ack.accept:
                        raise AckException(
                            "Camera did not accepted command...")

                if header.id == 131:  # incoming data pkt
                    data = cmd.result()  # data structure as defined in data.py
                    data.fromStruct(
                        header_data + self.recv(header.length - len(header)))
                    #data.fromStruct (header_data + self.recv (header.length))
                    # log.debug(data)
                    log.debug("data type is {}".format(data.data_type))
                    if data.data_type == 2006:  # image header
                        return data.header
                    elif data.data_type == 2004:  # acquisition status structure
                        return data
                    elif data.data_type == 2007:  # command done structure
                        return data
                    elif data.data_type == 2008:  # SGLII settings structure
                        return data
                    elif data.data_type == 2010:  # camera parameter structure
                        return data
                    elif data.data_type == 2011:  # camera XML file structure
                        return data
                    elif data.data_type == 2012:  # camera status structure
                        return data
                    elif data.data_type == 2013:  # menu information structure
                        # print(data.data_type)
                        return data
                    break

                if header.id == 132:

                    #tmp_array = np.array([])

                    img = cmd.result()
                    img.fromStruct(
                        header_data + self.recv(len(img) - len(header)))

                    # TODO: Needs better mapping of types here!
                    tmp_array = np.fromstring(
                        self.recv(img.img_bytes), np.uint16)
                    log.debug(img)

                    packets = img.total_packets - 1

                    for i in range(packets):

                        data = self.recv(len(img))
                        img.fromStruct(data)
                        log.debug (img)
                        data = self.recv(img.img_bytes)
                        tmp_array = np.append(
                            tmp_array, np.fromstring(data, np.uint16))

                    return (img.serial_length, img.parallel_length, tmp_array)
