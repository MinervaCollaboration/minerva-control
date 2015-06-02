import serial
from configobj import ConfigObj
import logging, ipdb
import sys
import time

class CellHeater:

    def __init__(self, id, night, configfile):

        self.id = id

        configObj = ConfigObj(configfile)

        try:
            CellHeaterconfig = configObj[self.id]
        except:
            print('ERROR accessing ', self.id, ".", 
                self.id, " was not found in the configuration file", configfile)
            return 

        self.port = str(CellHeaterconfig['Setup']['PORT'])
        self.baudrate = int(CellHeaterconfig['Setup']['BAUDRATE'])
        self.databits = int(CellHeaterconfig['Setup']['DATABITS'])
        self.party = str(CellHeaterconfig['Setup']['PARTY'])
        self.stopbits = int(CellHeaterconfig['Setup']['STOPBITS'])
        self.flowcontrol = str(CellHeaterconfig['Setup']['FLOWCONTROL'])
        #self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
       
        logger_name = CellHeaterconfig['Setup']['LOGNAME']
        log_file = 'logs/' + night + '/' + CellHeaterconfig['Setup']['LOGFILE']
			
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

    def connect(self):
        ser = serial.Serial()
        ser.baudrate = self.baudrate
        ser.port = self.port
        ser.open()
        ipdb.set_trace()
        ser.isOpen()

if __name__ == "__main__":
    com1 = CellHeater('COM3', 'n20150522', configfile = 'CellHeater.ini')
    com1.connect()
    ipdb.set_trace()
        
