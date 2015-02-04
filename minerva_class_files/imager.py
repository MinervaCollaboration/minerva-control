from configobj import ConfigObj
from win32com.client import Dispatch
import logging, datetime, ipdb

class imager:

    def __init__(self,camera_num, configfile=''):

        self.num = camera_num

        #set appropriate parameter based on aqawan_num
        #create configuration file object 
        configObj = ConfigObj(configfile)
        
        try:
            imagerconfig = configObj[self.num]
        except:
            print('ERROR accessing ', self.num, ".", 
                self.num, " was not found in the configuration file", configfile)
            return 

        self.platescale = float(imagerconfig['Setup']['PLATESCALE'])
        self.filters = imagerconfig['FILTERS']
        self.setTemp = float(imagerconfig['Setup']['SETTEMP'])
        self.maxcool = float(imagerconfig['Setup']['MAXCOOLING'])
        self.maxdiff = float(imagerconfig['Setup']['MAXTEMPERROR'])
        self.xbin = int(imagerconfig['Setup']['XBIN'])
        self.ybin = int(imagerconfig['Setup']['YBIN'])
        self.x1 = int(imagerconfig['Setup']['X1'])
        self.x2 = int(imagerconfig['Setup']['X2'])
        self.y1 = int(imagerconfig['Setup']['Y1'])
        self.y2 = int(imagerconfig['Setup']['Y2'])
        self.xcenter = int(imagerconfig['Setup']['XCENTER'])
        self.ycenter = int(imagerconfig['Setup']['YCENTER'])
        self.pointingModel = imagerconfig['Setup']['POINTINGMODEL']
        self.port = int(imagerconfig['Setup']['PORT'])
        
        logger_name = imagerconfig['Setup']['LOGNAME']
        log_file = imagerconfig['Setup']['LOGFILE']
			
	# setting up aqawan logger
	self.logger = logging.getLogger(logger_name)
        formatter = logging.Formatter(fmt="%(asctime)s [%(filename)s:%(lineno)s - %(funcName)20s()] %(levelname)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
	fileHandler = logging.FileHandler(log_file, mode='w')
	fileHandler.setFormatter(formatter)
	streamHandler = logging.StreamHandler()
	streamHandler.setFormatter(formatter)

	self.logger.setLevel(logging.DEBUG)
	self.logger.addHandler(fileHandler)
	self.logger.addHandler(streamHandler)

        self.cam = Dispatch("MaxIm.CCDCamera")

    def connect(self):
        settleTime = 900

        # Connect to an instance of Maxim's camera control.
        # (This launches the app if needed)
        self.logger.info('Connecting to Maxim') 
        self.cam = Dispatch("MaxIm.CCDCamera")

        # Connect to the camera 
        self.logger.info('Connecting to camera') 
        self.cam.LinkEnabled = True

        # Prevent the camera from disconnecting when we exit
        self.logger.info('Preventing the camera from disconnecting when we exit') 
        self.cam.DisableAutoShutdown = True

        # If we were responsible for launching Maxim, this prevents
        # Maxim from closing when our application exits
        self.logger.info('Preventing maxim from closing upon exit')
        maxim = Dispatch("MaxIm.Application")
        maxim.LockApp = True

        # Set binning
        self.logger.info('Setting binning to ' + str(self.xbin) + ',' + str(self.ybin) )
        self.cam.BinX = self.xbin
        self.cam.BinY = self.ybin

        # Set to full frame
        xsize = self.x2-self.x1+1
        ysize = self.y2-self.y1+1
        logging.info('Setting subframe to [' + str(self.x1) + ':' + str(self.x1 + xsize -1) + ',' +
                     str(self.y1) + ':' + str(self.y1 + ysize -1) + ']')

        self.cam.StartX = self.x1 #int((cam.CameraXSize/cam.BinX-CENTER_SUBFRAME_WIDTH)/2)
        self.cam.StartY = self.y1 #int((cam.CameraYSize/cam.BinY-CENTER_SUBFRAME_HEIGHT)/2)
        self.cam.NumX = xsize # CENTER_SUBFRAME_WIDTH
        self.cam.NumY = ysize # CENTER_SUBFRAME_HEIGHT

        self.logger.info('Turning cooler on')
        self.cam.TemperatureSetpoint = self.setTemp
        self.cam.CoolerOn = True
        start = datetime.datetime.utcnow()
        currentTemp = self.cam.Temperature
        elapsedTime = (datetime.datetime.utcnow() - start).total_seconds()

        # Wait for temperature to settle (timeout of 10 minutes)
        while elapsedTime < settleTime and (abs(self.setTemp - currentTemp) > self.maxdiff):    
            logging.info('Current temperature (' + str(currentTemp) + ') not at setpoint (' + str(self.setTemp) +
                         '); waiting for CCD Temperature to stabilize (Elapsed time: ' + str(elapsedTime) + ' seconds)')
            time.sleep(10)
            currentTemp = self.cam.Temperature
            elapsedTime = (datetime.datetime.utcnow() - start).total_seconds()

        # Failed to reach setpoint
        if (abs(self.setTemp - currentTemp)) > self.maxdiff:
            logging.error('The camera was unable to reach its setpoint (' + str(self.setTemp) + ') in the elapsed time (' + str(elapsedTime) + ' seconds)')
      
