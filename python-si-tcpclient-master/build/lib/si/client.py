# -*- encoding: iso-8859-1 -*-

# pH @ LNA 06/04/2007

import struct
import socket
import select
import time
import numpy as np
import os
import time

import logging

#import array

from si.packet import Packet
from si.packets import *
from si.commands import *

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

    SIClient communicates with the SI server. SIClient execute CameraCommand´s using the executeCommand method.
    """


    def __init__ (self, host, port):

        self.host = host
        self.port = port


        self.buff = ""

        self.sk = None

    def connect (self):

        try:
            self.sk = socket.socket (socket.AF_INET, socket.SOCK_STREAM)
            self.sk.connect ((self.host, self.port))
            self.sk.settimeout (10)
        except socket.error, e:
            raise e

    def disconnect (self):

        if not self.sk:
            return

        self.sk.close ()

    def recv (self, n):
        """
        Receive n bytes from the server.

        This method takes care of underrrun and overrun conditions and assure correct framing. The method will
        ask socket for n bytes and make sure that the return value contain exactly this amount of bytes.
        """

        if len(self.buff) > 0:
            logging.warning("Buffer not empty...")

        # if buffer isn't empty, return it and clear it
        bytes_to_receive = n - len(self.buff)

        bytes_received = self.buff
        self.buff = ""

        retries = 0

        logging.debug("bytes to receive %d (received %d)"%(bytes_to_receive,len(bytes_received)))

        while bytes_to_receive > 0:

            logging.debug ("bytes to receive %d" % bytes_to_receive)
            this_try = self.sk.recv (bytes_to_receive)
            
            logging.debug ("bytes received on this try %d" % len(this_try))
            bytes_to_receive -= len (this_try)

            bytes_received += this_try
            retries += 1

        ret = ""

        if len(bytes_received) > n:
            # we received more then one packet, get the packet and put the rest on a buffer
            self.buff = bytes_received[n:]
            ret = bytes_received[:n]
            logging.debug ("buffer overrrun")
        else:
            ret = bytes_received

        logging.debug ("> framing retries %d (return length %d)" % (retries, len(ret)))

        return ret
        
        
    def executeCommand (self, cmd, noAck=False):
        """
        Execute a CameraCommand command.

        This method send the CameraCommand command to the server and wait the server responds. If the server reponds
        with an Ack packet, we continue to listen on the socket (using select polling) waiting for Data or Image packets.

        """

        if not self.sk:
            try:
                self.connect ()
            except socket.error, e:
                raise e

        cmd_to_send = cmd.command ()
        logging.debug (cmd_to_send)

        bytes_sent = self.sk.send (cmd_to_send.toStruct())
        logging.debug ("%d bytes sent" % bytes_sent)
     
        while True:
            
            ret = select.select ([self.sk], [], [])

            if not ret[0]:
                break

            if ret[0][0] == self.sk:

                header = Packet ()
                header_data = self.recv (len(header))
                header.fromStruct (header_data)

                if header.id == 129:
                    ack = Ack ()                  
                    ack.fromStruct (header_data + self.recv (header.length - len(header)))                    
                    logging.debug (ack)
                    # TODO: Figure out why do I need this sleep here. If I don't do this, some commands are not
                    # TODO: performed. I really don't know why!
                    time.sleep(0.1)
                    #return ack
                    if not ack.accept:
                         raise AckException("Camera did not accepted command...")

                if header.id == 131:
                    data = cmd.result ()
                    data.fromStruct (header_data + self.recv (header.length - len(header)))
                    #data.fromStruct (header_data + self.recv (header.length))
                    logging.debug (data)

                    if data.data_type == 2006: # image header
                        return data.header
                    if data.data_type == 2010: # camera parameter structure
                        return data
                    break

                if header.id == 132:

                    #tmp_array = np.array([])

                    img = cmd.result ()
                    img.fromStruct (header_data + self.recv (len(img) - len(header)))

                    # TODO: Needs better mapping of types here!
                    tmp_array = np.fromstring(self.recv(img.img_bytes),np.uint16)
                    logging.debug (img)

                    packets = img.total_packets - 1
                   
                    for i in range (packets):

                        data = self.recv (len(img))
                        img.fromStruct (data)
                        #logging.debug (img)
                        data = self.recv(img.img_bytes)
                        tmp_array = np.append(tmp_array,np.fromstring(data,np.uint16))

                    return (img.serial_length, img.parallel_length, tmp_array)
