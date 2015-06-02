from configobj import ConfigObj
from win32com.client import Dispatch
import logging, datetime, ipdb, time, json
import sys
import socket 
import time
class PT100:

    def __init__(self, id, night, configfile):

        self.id = id

        #set appropriate parameter based on aqawan_num
        #create configuration file object 
        configObj = ConfigObj(configfile)
        
        try:
            PT100config = configObj[self.id]
        except:
            print('ERROR accessing ', self.id, ".", 
                self.id, " was not found in the configuration file", configfile)
            return 

        self.port = int(PT100config['Setup']['PORT'])
        self.ip = str(PT100config['Setup']['IP'])
        self.description = str(PT100config['Setup']['DESCRIPTION'])
        #self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
       
        logger_name = PT100config['Setup']['LOGNAME']
        log_file = 'logs/' + night + '/' + PT100config['Setup']['LOGFILE']
			
	# setting up PT100 logger
        fmt = "%(asctime)s [%(filename)s:%(lineno)s - %(funcName)s()] %(levelname)s: %(message)s"
        datefmt = "%Y-%m-%dT%H:%M:%S"

        self.logger = logging.getLogger(logger_name)
        formatter = logging.Formatter(fmt,datefmt=datefmt)
        formatter.converter = time.gmtime
        
        fileHandler = logging.FileHandler(log_file, mode='a')
        fileHandler.setFormatter(formatter)

        console = logging.StreamHandler()
        console.setFormatter(formatter)
        console.setLevel(logging.INFO)
        
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(fileHandler)
        self.logger.addHandler(console)

    def createSocket(self);
        #!/usr/bin/env python

        # server listens on a specified port, prints out msg, and sends an # acknowledgment.

        port = 6129

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        s.bind(("",self.port))

        print "Waiting on port ",port

        while 1 : data, addr = s.recvfrom(1024) print "socketprac.py received:",data print "addr was ",addr time.sleep(1.0) s.sendto("Got it.",addr);


        #!/usr/bin/env python

        # client sends a message and waits for a reply

        ds = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        ds.sendto("Hello there!",(self.ip,self.port))

        data, addr = ds.recvfrom(1024)

        print "reply received:",data," from ",addr


    """
    def connect(self):
         self.sock.connect((self.ip, self.port))

    def send(self, msg):
        totalsent = 0
        while totalsent < MSGLEN:
            sent = self.sock.send(msg[totalsent:])
            if sent == 0:
                raise RuntimeError("socket connection broken")
            totalsent = totalsent + sent

    def receive(self):
        chunks = []
        bytes_recd = 0
        while bytes_recd < MSGLEN:
            chunk = self.sock.recv(min(MSGLEN - bytes_recd, 2048))
            if chunk == '':
                raise RuntimeError("socket connection broken")
            chunks.append(chunk)
            bytes_recd = bytes_recd + len(chunk)
        return ''.join(chunks) """
        
if __name__ == "__main__":
    p3 = PT100('P3', 'n20150522', configfile = 'PT100.ini')
    p3.connect()
    ipdb.set_trace()
