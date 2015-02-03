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
        self.cam.StartY = self.x2 #int((cam.CameraYSize/cam.BinY-CENTER_SUBFRAME_HEIGHT)/2)
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
      
    def takeImage(cam, exptime, filterInd, objname):

        exptypes = {
            'Dark' : 0,
            'Bias' : 0,
            'SkyFlat' : 1,
            }

        if objname in exptypes.keys():
            exptype = exptypes[objname]
        else: exptype = 1 # science exposure

        filters = {
            'B' : 0,
            'V' : 1,
            'gp' : 2,
            'rp' : 3,
            'ip' : 4,
            'zp' : 5,
            'air' : 6,
            }   
       
        # Take flat fields
        cam.Expose(exptime, exptype, filters[filterInd])

        # Get status info for headers while exposing/reading out
        # (needs error handling)
        weather = -1
        while weather == -1: weather = getWeather()
        telescopeStatus = getStatus()
        aqStatus = aqawanStatus()
        gitNum = subprocess.check_output(["C:/Users/pwi/AppData/Local/GitHub/PortableGit_c2ba306e536fdf878271f7fe636a147ff37326ad/bin/git.exe", "rev-list", "HEAD", "--count"]).strip()
        obs = setObserver()

        while not cam.ImageReady: time.sleep(0.1)

        # Save the image
        filename = datapath + "/" + night + ".T3." + objname + "." + getIndex(datapath) + ".fits"
        logging.info('Saving image: ' + filename)
        cam.SaveImage(filename)

        # faster way?
        t0=datetime.datetime.utcnow()
        f = pyfits.open(filename, mode='update')

        # Static Keywords
        f[0].header['SITELAT'] = str(obs.lat)
        f[0].header['SITELONG'] = (str(obs.lon),"East Longitude of the imaging location")
        f[0].header['SITEALT'] = (obs.elevation,"Site Altitude (m)")
        f[0].header['OBSERVER'] = ('MINERVA Robot',"Observer")
        f[0].header['TELESCOP'] = "CDK700"
        f[0].header['OBJECT'] = objname
        f[0].header['APTDIA'] = 700
        f[0].header['APTAREA'] = 490000
        f[0].header['ROBOVER'] = (gitNum,"Git commit number for robotic control software")

        # Site Specific
        f[0].header['LST'] = (telescopeStatus.status.lst,"Local Sidereal Time")

        # Enclosure Specific
        f[0].header['AQSOFTV'] = (aqStatus['SWVersion'],"Aqawan software version number")
        f[0].header['AQSHUT1'] = (aqStatus['Shutter1'],"Aqawan shutter 1 state")
        f[0].header['AQSHUT2'] = (aqStatus['Shutter2'],"Aqawan shutter 2 state")
        f[0].header['INHUMID'] = (aqStatus['EnclHumidity'],"Humidity inside enclosure")
        f[0].header['DOOR1'] = (aqStatus['EntryDoor1'],"Door 1 into aqawan state")
        f[0].header['DOOR2'] = (aqStatus['EntryDoor2'],"Door 2 into aqawan state")
        f[0].header['PANELDR'] = (aqStatus['PanelDoor'],"Aqawan control panel door state")
        f[0].header['HRTBEAT'] = (aqStatus['Heartbeat'],"Heartbeat timer")
        f[0].header['AQPACUP'] = (aqStatus['SystemUpTime'],"PAC uptime (seconds)")
        f[0].header['AQFAULT'] = (aqStatus['Fault'],"Aqawan fault present?")
        f[0].header['AQERROR'] = (aqStatus['Error'],"Aqawan error present?")
        f[0].header['PANLTMP'] = (aqStatus['PanelExhaustTemp'],"Aqawan control panel exhaust temp (C)")
        f[0].header['AQTEMP'] = (aqStatus['EnclTemp'],"Enclosure temperature (C)")
        f[0].header['AQEXTMP'] = (aqStatus['EnclExhaustTemp'],"Enclosure exhaust temperature (C)")
        f[0].header['AQINTMP'] = (aqStatus['EnclIntakeTemp'],"Enclosure intake temperature (C)")
        f[0].header['AQLITON'] = (aqStatus['LightsOn'],"Aqawan lights on?")

        # Mount specific
        f[0].header['TELRA'] = (telescopeStatus.mount.ra_2000,"Telescope RA (J2000)")
        f[0].header['TELDEC'] = (telescopeStatus.mount.dec_2000,"Telescope Dec (J2000)")
        f[0].header['RA'] = (telescopeStatus.mount.ra_target, "Target RA (J2000)")
        f[0].header['DEC'] =  (telescopeStatus.mount.dec_target, "Target Dec (J2000)")
        f[0].header['PMODEL'] = (telescopeStatus.mount.pointing_model,"Pointing Model File")

        # Focuser Specific
        f[0].header['FOCPOS'] = (telescopeStatus.focuser.position,"Focus Position (microns)")

        # Rotator Specific
        f[0].header['ROTPOS'] = (telescopeStatus.rotator.position,"Rotator Position (degrees)")

        # WCS
        platescale = 0.61/3600.0*cam.BinX # deg/pix
        PA = float(telescopeStatus.rotator.position)*math.pi/180.0
        f[0].header['CTYPE1'] = ("RA---TAN","TAN projection")
        f[0].header['CTYPE2'] = ("DEC--TAN","TAN projection")
        f[0].header['CUNIT1'] = ("deg","X pixel scale units")
        f[0].header['CUNIT2'] = ("deg","Y pixel scale units")
        f[0].header['CRVAL1'] = (float(telescopeStatus.mount.ra_radian)*180.0/math.pi,"RA of reference point")
        f[0].header['CRVAL2'] = (float(telescopeStatus.mount.dec_radian)*180.0/math.pi,"DEC of reference point")
        f[0].header['CRPIX1'] = (cam.CameraXSize/2.0,"X reference pixel")
        f[0].header['CRPIX2'] = (cam.CameraYSize/2.0,"Y reference pixel")
        f[0].header['CD1_1'] = -platescale*math.cos(PA)
        f[0].header['CD1_2'] = platescale*math.sin(PA)
        f[0].header['CD2_1'] = platescale*math.sin(PA)
        f[0].header['CD2_2'] = platescale*math.cos(PA)

        # M3 Specific
        f[0].header['PORT'] = (telescopeStatus.m3.port,"Selected port")    
        
        # Fans
        f[0].header['OTAFAN'] = (telescopeStatus.fans.on,"OTA Fans on?")    

        # Telemetry
        f[0].header['M1TEMP'] = (telescopeStatus.temperature.primary,"Primary Mirror Temp (C)")
        f[0].header['M2TEMP'] = (telescopeStatus.temperature.secondary,"Secondary Mirror Temp (C)")
        f[0].header['M3TEMP'] = (telescopeStatus.temperature.m3,"Tertiary Mirror Temp (C)")
        f[0].header['AMBTMP'] = (telescopeStatus.temperature.ambient,"Ambient Temp (C)")
        f[0].header['BCKTMP'] = (telescopeStatus.temperature.backplate,"Backplate Temp (C)")
        f[0].header['WJD'] = (weather['date'],"Last update of weather (UTC)")
        f[0].header['RAIN'] = (weather['wxt510Rain'],"Current Rain (mm?)")
        f[0].header['TOTRAIN'] = (weather['totalRain'],"Total Rain (mm?)")
        f[0].header['OUTTEMP'] = (weather['outsideTemp'],"Outside Temperature (C)")
        f[0].header['SKYTEMP'] = (weather['relativeSkyTemp'],"Sky - Ambient (C)")
        f[0].header['DEWPOINT'] = (weather['outsideDewPt'],"Dewpoint (C)")
        f[0].header['WINDSPD'] = (weather['windSpeed'],"Wind Speed (mph)")
        f[0].header['WINDGUST'] = (weather['windGustSpeed'],"Wind Gust Speed (mph)")
        f[0].header['WINDIR'] = (weather['windDirectionDegrees'],"Wind Direction (Deg E of N)")
        f[0].header['PRESSURE'] = (weather['barometer'],"Outside Pressure (mmHg?)")
        f[0].header['SUNALT'] = (weather['sunAltitude'],"Sun Altitude (deg)")

        f.flush()
        f.close()
        print (datetime.datetime.utcnow()-t0).total_seconds()
        
        return filename
