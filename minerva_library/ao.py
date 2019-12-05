import com
import ipdb
import math
from configobj import ConfigObj
import serial
import utils
import datetime, time
import sys

class ao:

    def __init__(self, config, base="C:/minerva-control/"):

        self.config_file = config
        self.base_directory = base
        self.load_config()

        # current steps         
        self.North = 0
        self.East = 0
        
        self.logger = utils.setup_logger(self.base_directory,self.night,self.logger_name)

        self.connect()

        self.home()


    def load_config(self):
        config = ConfigObj(self.base_directory + '/config/' + self.config_file)

        try:       
            self.platescale = float(config['Setup']['PLATESCALE'])
            self.rotoffset = math.radians(float(config['Setup']['ROTOFFSET']))
            self.gain = float(config['Setup']['GAIN'])
            self.xmin = float(config['Setup']['XMIN'])
            self.xmax = float(config['Setup']['XMAX'])
            self.ymin = float(config['Setup']['YMIN'])
            self.ymax = float(config['Setup']['YMAX'])
            self.logger_name = config['Setup']['LOGNAME']

            # set up the serial port to the AO Guider
            self.ser = serial.Serial(timeout=None)
            #self.ser = serial.Serial()
            self.ser.port = config['Setup']['PORT']
            self.ser.baudrate = config['Setup']['BAUDRATE']
            self.ser.databits = int(config['Setup']['DATABITS'])
            self.ser.stopbits = int(config['Setup']['STOPBITS'])
            #self.ser.parity = config['Setup']['PARITY']
            #self.flowcontrol = config['Setup']['FLOWCONTROL']
            self.termstr = config['Setup']['TERMSTR']
        except:
            print('ERROR accessing config file: ' + self.config_file)
            sys.exit()

        today = datetime.datetime.utcnow()
        if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
                today = today + datetime.timedelta(days=1)
        self.night = 'n' + today.strftime('%Y%m%d')

    def connect(self):
        try:
            self.ser.open()
        except serial.serialutil.SerialException as e:
            print e.errno, e.filename, e.strerror
            self.logger.error("Could not open serial port ({0}): {1}".format(e.errno, e.strerror))
        return self.ser.isOpen()

    def home(self):
        if self.ser.isOpen():
            self.ser.write("K" + self.termstr)
            response = ''
            t0 = datetime.datetime.utcnow()
            while response == '':
                if (datetime.datetime.utcnow() - t0).total_seconds() > 10: break
                response = self.ser.read(self.ser.inWaiting())
                time.sleep(0.001)

            if response == "K": return "success " + response
            return "failed " + response
        return "failed; serial connection not open"

    def move(self,north,east):        
        # https://www.sxccd.com/handbooks/Starlight%20Xpress%20SXV%20AOL%20unit.pdf
        # pg 12

        # the magnitudes of the corrections for the Starlight Xpress
        # converted to their definitions of North and East
        slxNorth = -self.gain*self.platescale*(east*math.cos(self.rotoffset) - north*math.sin(self.rotoffset))
        slxEast  =  self.gain*self.platescale*(east*math.sin(self.rotoffset) + north*math.cos(self.rotoffset))

        cmdN = 'G'
        if slxNorth > 0: cmdN += 'N'
        else: cmdN += 'S'
        cmdN += str(abs(int(slxNorth))).zfill(5)

        cmdE = 'G'
        if slxEast > 0: cmdE += 'T'
        else: cmdE += 'W'
        cmdE += str(abs(int(slxEast))).zfill(5)

        self.North += slxNorth
        self.East += slxEast

        if self.North > self.ymax or self.North < self.ymin or self.East > self.xmax or self.East < self.xmin:
            # TODO: Move telescope to compensate
            return "failed; request outside of limits"
        
        if self.ser.isOpen():
            cmd = cmdN + self.termstr + cmdE + self.termstr
            self.logger.info("sending serial command: " + cmd)
            self.ser.write(cmd)

            response = ''
            t0 = datetime.datetime.utcnow()
            while response != "GG" and response != "GL" and response != "LL" and response != "LG":
                if (datetime.datetime.utcnow() - t0).total_seconds() > 10: break
                response += self.ser.read(self.ser.inWaiting())
                time.sleep(0.001)
            #print (datetime.datetime.utcnow() - t0).total_seconds()
            
            if "L" in response: return "Limits Reached " + response
            if response == "GG": return "success " + response
            return "failed " + response
        return "failed; serial connection not open"
