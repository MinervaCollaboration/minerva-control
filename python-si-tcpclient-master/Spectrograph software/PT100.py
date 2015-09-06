from configobj import ConfigObj
from win32com.client import Dispatch
import logging, datetime, ipdb, time, json
import sys
import socket 
import time
import struct
from scipy.interpolate import interp1d
import numpy as np

class PT100:

    def __init__(self, id, night, configfile):

        self.id = id

        #set appropriate parameter based on aqawan_num
        #create configuration file object 
        configObj = ConfigObj(configfile)
        
        try:
            PT100config = configObj[self.id]
        except:
            print 'ERROR accessing ' + self.id + ". " + self.id + " was not found in the configuration file", configfile
            return 

        self.port = int(PT100config['Setup']['PORT'])
        self.ip = str(PT100config['Setup']['IP'])
        self.description = str(PT100config['Setup']['DESCRIPTION'])
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
       
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

    '''
    def createSocket(self):
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



    def connect(self):
         self.sock.connect((self.ip, self.port))
    '''

    # interpolate the lookup table for a given resistance to derive the temp
    # https://www.picotech.com/download/manuals/USBPT104ProgrammersGuide.pdf
    def ohm2temp(self,ohm):
        reftemp = np.linspace(-50,200,num=251)
        refohm = np.loadtxt('minerva_class_files/pt100.dat')
        f = interp1d(refohm,reftemp)#,kind='cubic')
        temp = f(ohm)[()]
        return temp

    def resistance(self,calib,m):
        resistance = calib*(m[3]-m[2])/(m[1]-m[0])/1000000.0
        return resistance

    def temperature(self):
        return self.ohm2temp(self.resistance())
    
    def send(self, msg):
        self.sock.sendto(msg,(self.ip, self.port))
        
if __name__ == "__main__":
    p3 = PT100('P1', 'n20150521', configfile = 'minerva_class_files/PT100.ini')

    p3.sock.connect((p3.ip,p3.port))

    ipdb.set_trace()
#    p3.sock.bind((p3.ip,p3.port))
    time.sleep(1)
    
    '''
    p3.sock.send('0x310xff')
    time.sleep(2.0)
    val = p3.sock.recv(2048)
    print len(val), val
    '''
    
    p3.sock.send('0x300xff')
    time.sleep(2.0)
    val = p3.sock.recv(2048)
    print len(val), val

    p3.sock.send('0x32')
    time.sleep(2.0)
    val = p3.sock.recv(2048)
    print len(val), val
   

    m = struct.unpack_from('<qiiii',val,offset=36)
    print m
    ipdb.set_trace()
    
    p3.sock.send('0x310xff')
    time.sleep(1.0)
    ''''
    cmd = '0x31'
    data = '0xff'

    cmdhex = int(cmd,16)
    datahex = int(data,16)

    cmdstring = struct.pack('B',cmdhex)
    datastring = struct.pack('B',datahex)
    string = cmdstring + datastring
    
    p3.send(string)
    '''
    val = p3.sock.recv(2048)
    time.sleep(10.0)

    while True:
        val = p3.sock.recv(2048)

        m = struct.unpack('>cicicici',val)
        print m
        if True:#m[0] == '\x0c':
            t = [float(m[1]),float(m[3]),float(m[5]),float(m[7])]
            ohm = p3.resistance(1000000.0, t)
            print ohm
            temp = p3.ohm2temp(ohm)
            print temp
        time.sleep(10)


    print len(val)
    m = struct.unpack_from('qiiii',val,offset=36)
    print p3.resistance(1,m)

  #  p3.send('0x32')
  #  time.sleep(0.2)
  #  print p3.sock.recv(128)

    
    
#    p3.send(r'0x30x01')
#    p3.send('lock')
#    p3.sock.sendto('0xfff',(p3.ip,23))

#    p3.sock.bind('127.0.0.1')
#    p3.sock.setblocking(0)
#    p3.send(r'0x32')
#    print 
#    print p3.sock.recv(128)
#    print p3.sock.recv(128)

#    print p3.ohm2temp(100)
    ipdb.set_trace()
