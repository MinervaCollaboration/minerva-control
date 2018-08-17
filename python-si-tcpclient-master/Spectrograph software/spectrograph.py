#import minerva_class_files
from configobj import ConfigObj
import logging, ipdb
import time, datetime, subprocess, pyfits, glob, sys, copy
import mysite as minervasite
import vacuumgauge



class spectrograph():

    def __init__(self, id, night, configfile='minerva_class_files/spectrograph.ini'):

        self.night = night
        configObj = ConfigObj(configfile)

        try:
            config = configObj[id]
        except:
            print('ERROR accessing ', id, ".", 
                id, " was not found in the configuration file", configfile)
            return 
    
        
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

        # initialize all the hardware
        self.specgauge = vacuumgauge.vacuumgauge('specgauge',night)
        '''
        self.expmeter = expmeter('expmeter',night)
        self.iodinestage = stage('iodinestage',night)
        self.imager = imager('SI',night)
        self.heater = heater('heater',night)
        '''

    def configure(self,ThArOn=False, FlatOn=False, iodinePos='science',HeaterOn=True,\
                  ShutterOpen=False, FilterPos='air' ):
        # iodine cell position
        self.iodinestage.move(iodinePos)

        # cell heater
        if HeaterOn: self.heater.on()
        else: self.heater.off()

        # ThAr lamp
        if ThArOn: self.tharlamp.on()
        else: self.tharlamp.off()

        # Flat lamp
        if FlatOn: self.flatlamp.on()
        else: self.flatlamp.off()

        # Vacuum Pressure

        # Calibration Shutter

        # Filter Wheel

        # Thermal enclosure

        


    # configures the spectrograph to take a stellar template
    def takeTemplate(self):
        # move iodine cell out of beam
        self.configure(iodinePos='template')

    def takeScience(self):
        # turn the cell heater on
        self.configure()

    def takeArc(self):
        self.configure(ThArOn=True,iodinePos='template',ShutterOpen=True)

    def takeFlat(self):
        # move iodine cell out of beam
        self.configure(FlatOn=True,iodinePos='template',ShutterOpen=True)

    def takeDark(self):
        self.configure()

    

    def takeImage(self):#, site, aqawans, telescopes, exptime, objnames, signal):

        # start the exposure asynchronously

        site = minervasite.site('Wellington',self.night,configfile='minerva_class_files/site.ini')
        aqawans = []
        telescopes = []
        gitPath = "C:/Users/Kiwispec/AppData/Local/GitHub/PortableGit_c2ba306e536fdf878271f7fe636a147ff37326ad/bin/git.exe"


        # Get status info for headers while exposing/reading out
        # (needs error handling)
        weather = -1
        while weather == -1:
            site.getWeather()
            weather = copy.deepcopy(site.weather)

        moonpos = site.moonpos()
        moonra = moonpos[0]
        moondec = moonpos[1]
        moonphase = site.moonphase()

        gitNum = subprocess.check_output([gitPath, "rev-list", "HEAD", "--count"]).strip()

        # emulate MaximDL header for consistency
        hdr = pyfits.Header([('SIMPLE',True),
                             ('BITPIX',16,'8 unsigned int, 16 & 32 int, -32 & -64 real'),
                             ('NAXIS',2,'number of axes'),
                             ('NAXIS1',0,'Length of Axis 1 (Columns)'),
                             ('NAXIS2',0,'Length of Axis 2 (Rows)'),
                             ('BSCALE',1,'physical = BZERO + BSCALE*array_value'),
                             ('BZERO',0,'physical = BZERO + BSCALE*array_value'),
                             ('DATE-OBS',"","UTC at exposure start"),
                             ('EXPTIME',"","Exposure time in seconds"), # PARAM24/1000
#                             ('EXPSTOP',"","UTC at exposure end"),
                             ('SET-TEMP',"",'CCD temperature setpoint in C'), # PARAM62 (in comments!)
                             ('CCD-TEMP',"",'CCD temperature at start of exposure in C'), #PARAM0
                             ('BACKTEMP',"","Backplace Temperature in C"), # PARAM1
                             ('XPIXSZ',"",'Pixel Width in microns (after binning)'),
                             ('YPIXSZ',"",'Pixel Height in microns (after binning)'),
                             ('XBINNING',"","Binning factor in width"), # PARAM18
                             ('YBINNING',"","Binning factor in height"), # PARAM22
                             ('XORGSUBF',0,'Subframe X position in binned pixels'), # PARAM16
                             ('YORGSUBF',0,'Subframe Y position in binned pixels'), # PARAM20
                             ('IMAGETYP',"",'Type of image'),
                             ('SITELAT',str(site.obs.lat),"Site Latitude"),
                             ('SITELONG',str(site.obs.lon),"East Longitude of the imaging location"),
                             ('SITEALT',site.obs.elevation,"Site Altitude (m)"),
                             ('JD',0.0,"Julian Date at the start of exposure"),
                             ('FOCALLEN',4560.0,"Focal length of the telescope in mm"),
                             ('APTDIA',700,""),
                             ('APTAREA',490000,""),
                             ('SWCREATE',"SI2479E 2011-12-02","Name of the software that created the image"),
                             ('INSTRUME','KiwiSpec','Name of the instrument'),
                             ('OBSERVER','MINERVA Robot',"Observer"),
                             ('SHUTTER',"","Shuter Status"),    # PARAM8
                             ('XIRQA',"",'XIRQA status'),          # PARAM9
                             ('COOLER',"","Cooler Status"),        # PARAM10
                             ('CONCLEAR',"","Continuous Clear"),#PARAM25
                             ('DSISAMP',"","DSI Sample Time"), # PARAM26
                             ('ANLGATT',"","Analog Attenuation"),  # PARAM27
                             ('PORT1OFF',"","Port 1 Offset"),             # PARAM28
                             ('PORT2OFF',"","Port 2 Offset"),             # PARAM29
                             ('TDIDELAY',"","TDI Delay,us"),              # PARAM32
                             ('CMDTRIG',"","Command on Trigger"), #PARAM39
                             ('ADCOFF1',"","Port 1 ADC Offset"),          # PARAM44
                             ('ADCOFF2',"","Port 2 ADC Offset"),          # PARAM45
                             ('MODEL',"","Instrument Model"),             # PARAM48
                             ('SN',"","Instrument SN"),                   # PARAM49
                             ('HWREV',"","Hardware Revision"),            # PARAM50
                             ('SERIALP',"","Serial Phasing"),    # PARAM51
                             ('SERIALSP',"","Serial Split"),     # PARAM52
                             ('SERIALS',"","Serial Size,Pixels"),         # PARAM53
                             ('PARALP',"","Parallel Phasing"),   # PARAM54
                             ('PARALSP',"","Parallel Split"),    # PARAM55
                             ('PARALS',"","Parallel Size,Pixels"),        # PARAM56
                             ('PARDLY',"","Parallel Shift Delay, ns"),    # PARAM57
                             ('NPORTS',"","Number of Ports"),    # PARAM58
                             ('SHUTDLY',"","Shutter Close Delay, ms"),    # PARAM59
                             ('ROBOVER',gitNum,"Git commit number for robotic control software"),
                             ('MOONRA',moonra,"Moon RA (J2000)"),
                             ('MOONDEC',moondec,"Moon DEC (J2000)"),
                             ('MOONPHAS', moonphase, "Moon Phase (Fraction)")])
                                
#PARAM60 =                   74 / CCD Temp. Setpoint Offset,0.1 C               
#PARAM61 =               1730.0 / Low Temp Limit,(-100.0 C)                      
#PARAM62 =               1830.0 / CCD Temperature Setpoint,(-90.0 C)             
#PARAM63 =               1880.0 / Operational Temp,(-85.0 C)                     
#PARAM65 =                    0 / Port Select,(A)                                
#PARAM73 =                    0 / Acquisition Mode,(Normal)                      
#PARAM76 =                    0 / UART 100 byte Ack,(Off)                        
#PARAM79 =                  900 / Pixel Clear,ns                                 
#COMMENT  Temperature is above set limit, Light Exposure, Exp Time= 10, Saved as:
#COMMENT   overscan.FIT                                
                             
                                 
        # need object for each telescope

        # loop over each telescope and insert the appropriate keywords
        for telescope in telescopes:
            telescop += telescope.name
            telnum = telescope.name[-1]
            telescopeStatus = telescope.getStatus()
            telra = ten(telescopeStatus.mount.ra_2000)*15.0
            teldec = ten(telescopeStatus.mount.dec_2000)
            ra = ten(telescopeStatus.mount.ra_target)*15.0
            dec = ten(telescopeStatus.mount.dec_target)
            if dec > 90.0: dec = dec-360 # fixes bug in PWI
            hdr.append(('TELRA' + telnum,telra,"Telescope RA (J2000 deg)"))
            hdr.append(('TELDEC' + telnum,teldec,"Telescope Dec (J2000 deg)"))
            hdr.append(('RA' + telnum,ra, "Target RA (J2000 deg)"))
            hdr.append(('DEC'+ telnum,dec,"Target Dec (J2000 deg)"))

            moonsep = ephem.separation((telra*math.pi/180.0,teldec*math.pi/180.0),moonpos)*180.0/math.pi
            hdr.append(('MOONDIS' + telnum, moonsep, "Distance between pointing and moon (deg)"))
            hdr.append(('PMODEL' + telnum, telescopeStatus.mount.pointing_model,"Pointing Model File"))
            
            hdr.append(('FOCPOS' + telnum, telescopeStatus.focuser.position,"Focus Position (microns)"))
            hdr.append(('ROTPOS' + telnum, telescopeStatus.rotator.position,"Rotator Position (degrees)"))

            # M3 Specific
            hdr.append(('PORT' + telnum,telescopeStatus.m3.port,"Selected port for " + telescope.name))
            hdr.append(('OTAFAN' + telnum, telescopeStatus.fans.on,"OTA Fans on?"))

            try: m1temp = telescopeStatus.temperature.primary
            except: m1temp = 'UNKNOWN'
            hdr.append(('M1TEMP'+telnum,m1temp,"Primary Mirror Temp (C)"))

            try: m2temp = telescopeStatus.temperature.secondary
            except: m2temp = 'UNKNOWN'
            hdr.append(('M2TEMP'+telnum,m2temp,"Secondary Mirror Temp (C)"))

            try: m3temp = telescopeStatus.temperature.m3
            except: m3temp = 'UNKNOWN'
            hdr.append(('M3TEMP'+telnum,m3temp,"Tertiary Mirror Temp (C)"))

            try: ambtemp = telescopeStatus.temperature.ambient
            except: ambtemp = 'UNKNOWN'
            hdr.append(('AMBTEMP'+telnum,ambtemp,"Ambient Temp (C)"))
                       
            try: bcktemp = telescopeStatus.temperature.backplate
            except: bcktemp = 'UNKNOWN'
            hdr.append(('BCKTEMP'+telnum,bcktemp,"Backplate Temp (C)"))

        # loop over each aqawan and insert the appropriate keywords
        for aqawan in aqawans:
            aqStatus = aqawan.status()
            aqnum = aqawan.name[-1]

            hdr.append(('AQSOFTV'+aqnum,aqStatus['SWVersion'],"Aqawan software version number"))
            hdr.append(('AQSHUT1'+aqnum,aqStatus['Shutter1'],"Aqawan shutter 1 state"))
            hdr.append(('AQSHUT2'+aqnum,aqStatus['Shutter2'],"Aqawan shutter 2 state"))
            hdr.append(('INHUMID'+aqnum,aqStatus['EnclHumidity'],"Humidity inside enclosure"))
            hdr.append(('DOOR1'  +aqnum,aqStatus['EntryDoor1'],"Door 1 into aqawan state"))
            hdr.append(('DOOR2'  +aqnum,aqStatus['EntryDoor2'],"Door 2 into aqawan state"))
            hdr.append(('PANELDR'+aqnum,aqStatus['PanelDoor'],"Aqawan control panel door state"))
            hdr.append(('HRTBEAT'+aqnum,aqStatus['Heartbeat'],"Heartbeat timer"))
            hdr.append(('AQPACUP'+aqnum,aqStatus['SystemUpTime'],"PAC uptime (seconds)"))
            hdr.append(('AQFAULT'+aqnum,aqStatus['Fault'],"Aqawan fault present?"))
            hdr.append(('AQERROR'+aqnum,aqStatus['Error'],"Aqawan error present?"))
            hdr.append(('PANLTMP'+aqnum,aqStatus['PanelExhaustTemp'],"Aqawan control panel exhaust temp (C)"))
            hdr.append(('AQTEMP' +aqnum,aqStatus['EnclTemp'],"Enclosure temperature (C)"))
            hdr.append(('AQEXTMP'+aqnum,aqStatus['EnclExhaustTemp'],"Enclosure exhaust temperature (C)"))
            hdr.append(('AQINTMP'+aqnum,aqStatus['EnclIntakeTemp'],"Enclosure intake temperature (C)"))
            hdr.append(('AQLITON'+aqnum,aqStatus['LightsOn'],"Aqawan lights on?"))

        # Weather station
        hdr.append(('WJD',str(weather['date']),"Last update of weather (UTC)"))
        hdr.append(('RAIN',weather['wxt510Rain'],"Current Rain (mm?)"))
        hdr.append(('TOTRAIN',weather['totalRain'],"Total rain since ?? (mm?)"))
        hdr.append(('OUTTEMP',weather['outsideTemp'],"Outside Temperature (C)"))
        hdr.append(('SKYTEMP',weather['relativeSkyTemp'],"Sky - Ambient (C)"))
        hdr.append(('DEWPOINT',weather['outsideDewPt'],"Dewpoint (C)"))
        hdr.append(('WINDSPD',weather['windSpeed'],"Wind Speed (mph)"))
        hdr.append(('WINDGUST',weather['windGustSpeed'],"Wind Gust Speed (mph)"))
        hdr.append(('WINDIR',weather['windDirectionDegrees'],"Wind Direction (Deg E of N)"))
        hdr.append(('PRESSURE',weather['barometer'],"Outside Pressure (mmHg?)"))
        hdr.append(('SUNALT',weather['sunAltitude'],"Sun Altitude (deg)"))

        '''
        # spectrograph information
        EXPTYPE = 'Time-Based'         / Exposure Type                                  
        DETECTOR= 'SI850'              / Detector Name                                  
        '''

        hdr.append(('CCDMODE',0,'CCD Readout Mode'))
        hdr.append(('FIBER','','Fiber Bundle Used'))
        hdr.append(('ATM_PRES','UNKNOWN','Atmospheric Pressure (mbar)'))
        hdr.append(('VAC_PRES',float(self.specgauge.pressure()),"Vacuum Tank Pressure (mbar)"))
        hdr.append(('SPECHMID','UNKNOWN','Spectrograph Room Humidity (%)'))
        for i in range(16)+1: hdr.append(('TEMP' + str(i),'UNKNOWN','UNKNOWN Temperature (C)'))
        hdr.append(('I2TEMPA','UNKNOWN','Iodine Cell Actual Temperature (C)'))
        hdr.append(('I2TEMPS','UNKNOWN','Iodine Cell Set Temperature (C)'))
        hdr.append(('I2POS','UNKNOWN','Iodine Stage Position'))
        hdr.append(('SFOCPOS','UNKNOWN','KiwiSpec Focus Stage Position'))


        objname = 'overscan'
        path = "C:/minerva/data/" + self.night + "/"
        images = glob.glob(path + "*.fits*")
        index = str(len(images)+1).zfill(4)
        filename = path + self.night + "." + objname + '.' + index + '.fits'

        # Wait for exposure to finish            

        t0 = datetime.datetime.utcnow()

        # Fill in values from SI header
        f = pyfits.open("C:/IMAGES/overscan.FIT")
        hdr['NAXIS'] = f[0].header['NAXIS']
        hdr['NAXIS1'] = f[0].header['NAXIS1']
        hdr['NAXIS2'] = f[0].header['NAXIS2']
        hdr['DATE-OBS'] = f[0].header['DATE-OBS']
        hdr['EXPTIME'] = float(f[0].header['PARAM24'])/1000.0
        hdr['SET-TEMP'] = float(f[0].header.comments['PARAM62'].split('(')[1].split('C')[0].strip())
        hdr['CCD-TEMP'] = float(f[0].header['PARAM0'])
        hdr['BACKTEMP'] = float(f[0].header['PARAM1'])
        hdr['XBINNING'] = float(f[0].header['PARAM18'])
        hdr['YBINNING'] = float(f[0].header['PARAM22'])
        hdr['XORGSUBF'] = float(f[0].header['PARAM16'])
        hdr['YORGSUBF'] = float(f[0].header['PARAM20'])
        hdr['SHUTTER'] = f[0].header.comments['PARAM8'].split('(')[-1].split(")")[0].strip()
        hdr['XIRQA'] = f[0].header.comments['PARAM9'].split('(')[-1].split(")")[0].strip()
        hdr['COOLER'] = f[0].header.comments['PARAM10'].split('(')[-1].split(")")[0].strip()
        hdr['CONCLEAR'] = f[0].header.comments['PARAM25'].split('(')[-1].split(")")[0].strip()
        hdr['DSISAMP'] = f[0].header.comments['PARAM26'].split('(')[-1].split(")")[0].strip()
        hdr['ANLGATT'] = f[0].header.comments['PARAM27'].split('(')[-1].split(")")[0].strip()
        hdr['PORT1OFF'] = f[0].header['PARAM28']
        hdr['PORT2OFF'] = f[0].header['PARAM29']
        hdr['TDIDELAY'] = f[0].header['PARAM32']
        hdr['CMDTRIG'] = f[0].header.comments['PARAM39'].split('(')[-1].split(")")[0].strip()
        hdr['ADCOFF1'] = f[0].header['PARAM44']
        hdr['ADCOFF2'] = f[0].header['PARAM45']
        hdr['MODEL'] = f[0].header['PARAM48']
        hdr['HWREV'] = f[0].header['PARAM50']
        hdr['SERIALP'] = f[0].header.comments['PARAM51'].split('(')[-1].split(")")[0].strip()
        hdr['SERIALSP'] = f[0].header.comments['PARAM52'].split('(')[-1].split(")")[0].strip()
        hdr['SERIALS'] = f[0].header['PARAM53']
        hdr['PARALP'] = f[0].header.comments['PARAM54'].split('(')[-1].split(")")[0].strip()
        hdr['PARALSP'] = f[0].header.comments['PARAM55'].split('(')[-1].split(")")[0].strip()
        hdr['PARALS'] = f[0].header['PARAM56']
        hdr['PARDLY'] = f[0].header['PARAM57']
        hdr['NPORTS'] = f[0].header.comments['PARAM58'].split('(')[-1].split(" ")[0].strip()
        hdr['SHUTDLY'] = f[0].header['PARAM59']

        # recast as 16 bit unsigned integer (2x smaller with no loss of information)
        data = f[0].data.astype('uint16')
        f.close()

        # Write final image
        pyfits.writeto(filename,data,hdr)
        
        print (datetime.datetime.utcnow() - t0).total_seconds()

if __name__ == "__main__":

    kiwispec = spectrograph('KiwiSpec','n20150615')
    kiwispec.takeImage()
    ipdb.set_trace()
