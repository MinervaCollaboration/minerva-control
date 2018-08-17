import serial
from configobj import ConfigObj
import logging, ipdb
import sys
import time, struct, datetime

class com:

    def __init__(self, id, night, configfile='minerva_class_files/com.ini'):

        self.id = id

        configObj = ConfigObj(configfile)

        try:
            config = configObj[self.id]
        except:
            print('ERROR accessing ', self.id, ".", 
                self.id, " was not found in the configuration file", configfile)
            return 

        self.flowcontrol = str(config['Setup']['FLOWCONTROL'])
        #self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.allowedCmds = config['Setup']['ALLOWEDCMDS']

        if config['Setup']['TERMSTR'] == r"\r":
            self.termstr = "\r"
        elif config['Setup']['TERMSTR'] == r"\r\n":
            self.termstr = "\r\n"
        elif config['Setup']['TERMSTR'] == r"\n\r":
            self.termstr = "\n\r"
        elif config['Setup']['TERMSTR'] == r"\n":
            self.termstr = "\n"
        
        self.ser = serial.Serial()
        self.ser.port = str(config['Setup']['PORT'])
        self.ser.baudrate = int(config['Setup']['BAUDRATE'])
        self.ser.databits = int(config['Setup']['DATABITS'])
#        self.ser.parity = str(config['Setup']['PARITY'])
        self.ser.stopbits = int(config['Setup']['STOPBITS'])
        
        logger_name = config['Setup']['LOGNAME']
        log_file = 'logs/' + night + '/' + config['Setup']['LOGFILE']
			
	# setting up logger
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

    def open(self):
        
        try:
            self.ser.open()
        except serial.serialutil.SerialException as e:
            self.logger.error("Could not open serial port ({0}): {1}".format(e.errno, e.strerror))

    def close(self):
        
        self.ser.close()

    def send(self,cmd):
        
        if True:#cmd in self.allowedCmds:

            self.open()

            if self.ser.isOpen():
                self.ser.write(cmd + self.termstr)

                # let's wait one second before reading output (let's give device time to answer)
                time.sleep(1)
                out = ''
                while self.ser.inWaiting() > 0:
                    byte = self.ser.read(1)
                    out = out + byte

                self.close()
                return out
                
            else:
                self.logger.error("Serial port not open")
        else:
            self.logger.error("Command " + cmd + " not in allowed commands")

if __name__ == "__main__":

#    specgauge = com('specgauge','n20150521')
#    print specgauge.send('RD')
#    ipdb.set_trace()

    expmeter = com('expmeter','n20150521')
    ipdb.set_trace()
    expmeter.send('R' + chr(1))
    expmeter.send('P' + chr(100))
    expmeter.send('D')

    measurementspersec = 2.0
    
    expmeter.send('P' + chr(int(100.0/measurementspersec)))

    expmeter.open()
    expmeter.ser.write('C' + expmeter.termstr)
    while True:
        try:
            while expmeter.ser.inWaiting() < 4:
                time.sleep(0.01)
            print str(datetime.datetime.utcnow()), struct.unpack('I',expmeter.ser.read(4))[0]
        except:  
            break
        
    expmeter.ser.write("\r") # stop measurements
    expmeter.ser.write('V'+ chr(0) + chr(0) + expmeter.termstr) # turn off voltage
    expmeter.close() # close connection
    ipdb.set_trace()
    
    com1 = CellHeater('COM3', 'n20150521', configfile = 'CellHeater.ini')
    com1.connect()
    ipdb.set_trace()
        
