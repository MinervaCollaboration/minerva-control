import serial
import datetime
import time
from configobj import ConfigObj
import ipdb
import socket

class chiller:

    def __init__(self,config,base=''):
        self.config_file = config
        self.base_directory = base
        self.load_config()


    def load_config(self):
        config = ConfigObj(self.base_directory + '/config/' + self.config_file)
        self.com = config['COM']
        self.baudrate = long(config['BAUDRATE'])
        self.timeout = float(config['TIMEOUT'])

    def send(self, cmd, parameter=None):

        # make sure the command sent is an allowed string
        allowedcmds = ['ALL?','IDN?','RUN?','TEMP?','SETTEMP?','WIDTH?','OFFSET?',
                        'PUMPTEMP?','PWM?','STAT1A?','FLTS1A?','LOCAL','RUN','STOP',
                        'SETTEMP','WIDTH','OFFSET','BLON','BLOFF','RESTART']
        if cmd not in allowedcmds:
            return

        # construct the command with arguments
        if parameter != None:
            cmdtosend = cmd + ' ' + str(parameter)
        else:
            cmdtosend = cmd

        # open the serial port
        ser = serial.Serial(self.com, baudrate = self.baudrate, bytesize = serial.EIGHTBITS, parity = serial.PARITY_NONE, stopbits= serial.STOPBITS_ONE, timeout = self.timeout)
        ser.write(cmdtosend + "\r\n")

        # wait for latency
        timeElapsed = 0.0
        t0 = datetime.datetime.utcnow()
        while ser.inWaiting() == 0 or timeElapsed > self.timeout:
            time.sleep(0.01)
            timeElapsed = (datetime.datetime.utcnow() - t0).total_seconds()

        # wait for data transfer
        inWaiting = ser.inWaiting()
        time.sleep(0.1)
        while inWaiting != ser.inWaiting():
            inWaiting = ser.inWaiting()
            time.sleep(0.1)

        # read the return string
        out = ''
        while ser.inWaiting() > 0:
            out = out + ser.read(1)

        # close the serial port
        ser.close()

        # return the output
        return out    

    def status(self):
        statstr = self.send("ALL?")
        statlist = statstr.split("\r")
        status = {}
        for entry in statlist:
            if entry != '':
                entries = entry.split()
                status[entries[0]] = float(entries[1])
        return status

    def gettemp(self):
        return float(self.send("TEMP?"))

    def getsettemp(self):
        return float(self.send("SETTEMP?"))

    def getpumptemp(self):
        return float(self.send("PUMPTEMP?"))

    def settemp(self, temp):
        return self.send("SETTEMP",parameter=temp)

if __name__ == "__main__":

    if socket.gethostname() == 'Main':
        base_directory = '/home/minerva/minerva-control'
    else:
       	base_directory = 'C:/minerva-control/'

    chiller = chiller('chiller.ini',base_directory)

    ipdb.set_trace()
