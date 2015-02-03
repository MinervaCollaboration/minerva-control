import minerva_class_files.site as minervasite
import minerva_class_files.imager as minervaimager
import minerva_class_files.cdk700 as minervatelescope
import minerva_class_files.aqawan as minervaaqawan

import datetime, logging, os, sys, time, subprocess, glob, math
import ipdb
import socket, threading
import pyfits

def aqawanOpen(aqawan):
    pass

def parseTarget(line):

    target = json.loads(line)
    # convert strings to datetime objects
    target['starttime'] = datetime.datetime.strptime(target['starttime'],'%Y-%m-%d %H:%M:%S')
    target['endtime'] = datetime.datetime.strptime(target['endtime'],'%Y-%m-%d %H:%M:%S')
    return target

# should do this asychronously and continuously
def heartbeat(site, aqawan):
    
    while site.observing:
        logger.info(aqawan.heartbeat())
        if not site.oktoopen(open=True):
            aqawan.close()
        time.sleep(15)

def prepNight(hostname, site):

    if hostname == 't3-PC':
        dirname = "E:/" + site.night + "/"
    elif hostname == 't1-PC':    
        dirname = "C:/minerva/data/" + site.night + "/"

    if not os.path.exists(dirname):
        os.makedirs(dirname)

    return dirname

def getIndex(dirname):
    files = glob.glob(dirname + "/*.fits")

    return str(len(files)+1).zfill(4)

    if len(files) == 0:
        return '0001'

    lastnum = (files[-1].split('.'))[-2]
    index = str(int(lastnum) + 1).zfill(4)
    return index


def takeImage(site, aqawan, telescope, imager, exptime, filterInd, objname):

    exptypes = {
        'Dark' : 0,
        'Bias' : 0,
        'SkyFlat' : 1,
        }

    if objname in exptypes.keys():
        exptype = exptypes[objname]
    else: exptype = 1 # science exposure

    if filterInd not in imager.filters:
        logger.error("Requested filter (" + filterInd + ") not present")
        return
   
    # Take flat fields
    imager.cam.Expose(exptime, exptype, imager.filters[filterInd])

    # Get status info for headers while exposing/reading out
    # (needs error handling)
#    site.weather = -1
#    while site.weather == -1: site.getWeather()
    telescopeStatus = telescope.getStatus()
    aqStatus = aqawan.status()

    # on T3
    gitPath = "C:/Users/pwi/AppData/Local/GitHub/PortableGit_c2ba306e536fdf878271f7fe636a147ff37326ad/bin/git.exe"
    # on T1
    gitPath = 'C:/Users/t1/AppData/Local/GitHub/PortableGit_c2ba306e536fdf878271f7fe636a147ff37326ad/bin/git.exe'
    
    gitNum = subprocess.check_output([gitPath, "rev-list", "HEAD", "--count"]).strip()

    while not imager.cam.ImageReady: time.sleep(0.1)

    # Save the image
    filename = datapath + "/" + site.night + ".T3." + objname + "." + getIndex(datapath) + ".fits"
    logger.info('Saving image: ' + filename)
    imager.cam.SaveImage(filename)

    # faster way?
    t0=datetime.datetime.utcnow()
    f = pyfits.open(filename, mode='update')

    # Static Keywords
    f[0].header['SITELAT'] = str(site.obs.lat)
    f[0].header['SITELONG'] = (str(site.obs.lon),"East Longitude of the imaging location")
    f[0].header['SITEALT'] = (site.obs.elevation,"Site Altitude (m)")
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
    platescale = imager.platescale/3600.0*imager.xbin # deg/pix
    PA = float(telescopeStatus.rotator.position)*math.pi/180.0
    f[0].header['CTYPE1'] = ("RA---TAN","TAN projection")
    f[0].header['CTYPE2'] = ("DEC--TAN","TAN projection")
    f[0].header['CUNIT1'] = ("deg","X pixel scale units")
    f[0].header['CUNIT2'] = ("deg","Y pixel scale units")
    f[0].header['CRVAL1'] = (float(telescopeStatus.mount.ra_radian)*180.0/math.pi,"RA of reference point")
    f[0].header['CRVAL2'] = (float(telescopeStatus.mount.dec_radian)*180.0/math.pi,"DEC of reference point")
    f[0].header['CRPIX1'] = (imager.xcenter,"X reference pixel")
    f[0].header['CRPIX2'] = (imager.ycenter,"Y reference pixel")
    f[0].header['CD1_1'] = -platescale*math.cos(PA)
    f[0].header['CD1_2'] = platescale*math.sin(PA)
    f[0].header['CD2_1'] = platescale*math.sin(PA)
    f[0].header['CD2_2'] = platescale*math.cos(PA)

    # M3 Specific
    f[0].header['PORT'] = (telescopeStatus.m3.port,"Selected port")    
    
    # Fans
    f[0].header['OTAFAN'] = (telescopeStatus.fans.on,"OTA Fans on?")    

    # Telemetry
#    f[0].header['M1TEMP'] = (telescopeStatus.temperature.primary,"Primary Mirror Temp (C)")
#    f[0].header['M2TEMP'] = (telescopeStatus.temperature.secondary,"Secondary Mirror Temp (C)")
#    f[0].header['M3TEMP'] = (telescopeStatus.temperature.m3,"Tertiary Mirror Temp (C)")
#    f[0].header['AMBTMP'] = (telescopeStatus.temperature.ambient,"Ambient Temp (C)")
#    f[0].header['BCKTMP'] = (telescopeStatus.temperature.backplate,"Backplate Temp (C)")
    
#    f[0].header['WJD'] = (site.weather['date'],"Last update of weather (UTC)")
#    f[0].header['RAIN'] = (site.weather['wxt510Rain'],"Current Rain (mm?)")
#    f[0].header['TOTRAIN'] = (site.weather['totalRain'],"Total rain since ?? (mm?)")
#    f[0].header['OUTTEMP'] = (site.weather['outsideTemp'],"Outside Temperature (C)")
#    f[0].header['SKYTEMP'] = (site.weather['relativeSkyTemp'],"Sky - Ambient (C)")
#    f[0].header['DEWPOINT'] = (site.weather['outsideDewPt'],"Dewpoint (C)")
#    f[0].header['WINDSPD'] = (site.weather['windSpeed'],"Wind Speed (mph)")
#    f[0].header['WINDGUST'] = (site.weather['windGustSpeed'],"Wind Gust Speed (mph)")
#    f[0].header['WINDIR'] = (site.weather['windDirectionDegrees'],"Wind Direction (Deg E of N)")
#    f[0].header['PRESSURE'] = (site.weather['barometer'],"Outside Pressure (mmHg?)")
#    f[0].header['SUNALT'] = (site.weather['sunAltitude'],"Sun Altitude (deg)")

    f.flush()
    f.close()
    print (datetime.datetime.utcnow()-t0).total_seconds()
    
    return filename


def doBias(site, aqawan, telescope, imager, num=11):
    doDark(site, aqawan, telescope, imager,exptime=0,num=num)

def doDark(site, aqawan, telescope, imager, exptime=60, num=11):

    DARK = 0
    if exptime == 0:
        objectName = 'Bias'
    else:
        objectName = 'Dark'

    # Take num Dark frames
    for x in range(num):
        logger.info('Taking ' + objectName + ' ' + str(x+1) + ' of ' + str(num) + ' (exptime = ' + str(exptime) + ')')
        takeImage(site, aqawan, telescope, imager, exptime,'V',objectName)


def doScience(site, aqawan, telescope, imager, target):

    # if after end time, return
    if datetime.datetime.utcnow() > target['endtime']:
        logger.info("Target " + target['name'] + " past its endtime (" + str(target['endtime']) + "); skipping")
        return

    # if before start time, wait
    if datetime.datetime.utcnow() < target['starttime']:
        waittime = (target['starttime']-datetime.datetime.utcnow()).total_seconds()
        logger.info("Target " + target['name'] + " is before its starttime (" + str(target['starttime']) + "); waiting " + str(waittime) + " seconds")
        time.sleep(waittime)

    # slew to the target
    telescope.acquireTarget(target['ra'],target['dec'])

    if target['defocus'] <> 0.0:
        logger.info("Defocusing Telescope by " + str(target['defocus']) + ' mm')
        telescope.focuserIncrement(target['defocus']*1000.0)

    # take one in each band, then loop over number (e.g., B,V,R,B,V,R,B,V,R)
    if target['cycleFilter']:
        for i in range(max(target['num'])):
            for j in range(len(target['filter'])):

                # if the enclosure is not open, wait until it is
                while not enclosure.isOpen():
                    response = enclosure.open()
                    if response == -1:
                        logger.info('Enclosure closed; waiting for conditions to improve') 
                        time.sleep(60)
                    if datetime.datetime.utcnow() > target['endtime']: return
                    # reacquire the target
                    if aqawan.isOpen(): telescope.acquireTarget(target['ra'],target['dec'])

                if datetime.datetime.utcnow() > target['endtime']: return
                if i < target['num'][j]:
                        logger.info('Beginning ' + str(i+1) + " of " + str(target['num'][j]) + ": " + str(target['exptime'][j]) + ' second exposure of ' + target['name'] + ' in the ' + target['filter'][j] + ' band') 
                        camera.takeImage(site, aqawan, telescope, imager, target['exptime'][j], target['filter'][j], target['name'])
                
    else:
        # take all in each band, then loop over filters (e.g., B,B,B,V,V,V,R,R,R) 
        for j in range(len(target['filter'])):
            # cycle by number
            for i in range(target['num'][j]):

                # if the enclosure is not open, wait until it is
                while not enclosure.isOpen():
                    response = enclosure.open()
                    if response == -1:
                        logger.info('Enclosure closed; waiting for conditions to improve') 
                        time.sleep(60)
                    if datetime.datetime.utcnow() > target['endtime']: return
                    # reacquire the target
                    if aqawan.isOpen(): telescope.acquireTarget(target['ra'],target['dec'])
                
                if datetime.datetime.utcnow() > target['endtime']: return
                logger.info('Beginning ' + str(i+1) + " of " + str(target['num'][j]) + ": " + str(target['exptime'][j]) + ' second exposure of ' + target['name'] + ' in the ' + target['filter'][j] + ' band') 
                camera.takeImage(site, aqawan, telescope, imager, target['exptime'][j], target['filter'][j], target['name'])

 

if __name__ == '__main__':

    hostname = socket.gethostname()

    if hostname == 't1-PC' or hostname == 't2-PC':
        site = minervasite.site('Pasadena', configfile='minerva_class_files/site.ini')
        aqawan = minervaaqawan.aqawan('A1', configfile='minerva_class_files/aqawan.ini')
        if hostname == 't1-PC':
            telescope = minervatelescope.CDK700('T1', configfile='minerva_class_files/telescope.ini')
            imager = minervaimager.imager('C1', configfile='minerva_class_files/imager.ini')
        else:
            telescope = minervatelescope.CDK700('T2', configfile='minerva_class_files/telescope.ini')
            imager = minervaimager.imager('C2', configfile='minerva_class_files/imager.ini')
    elif hostname == 't3-PC' or hostname == 't4-PC':
        site = minervasite.site('Mount_Hopkins', configfile='minerva_class_files/site.ini')
        aqawan = minervaaqawan.aqawan('A2', configfile='minerva_class_files/aqawan.ini')
        if hostname == 't3-PC':
            telescope = minervatelescope.telescope('T3', configfile='minerva_class_files/telescope.ini')
            imager = minervaimager.imager('C3', configfile='minerva_class_files/imager.ini')
        else:
            telescope = minervatelescope.telescope('T4', configfile='minerva_class_files/telescope.ini')
            imager = minervaimager.imager('C4', configfile='minerva_class_files/imager.ini')

    # Prepare for the night (define data directories, etc)
    datapath = prepNight(hostname, site)

    # setting up site logger
    logger = logging.getLogger('main')
    formatter = logging.Formatter(fmt="%(asctime)s [%(filename)s:%(lineno)s - %(funcName)20s()] %(levelname)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
    fileHandler = logging.FileHandler('main.log', mode='w')
    fileHandler.setFormatter(formatter)
    streamHandler = logging.StreamHandler()
    streamHandler.setFormatter(formatter)

    logger.setLevel(logging.DEBUG)
    logger.addHandler(fileHandler)
    logger.addHandler(streamHandler)
    
#    # Start a logger
#    logging.basicConfig(filename=datapath + site.night + '.log', format="%(asctime)s [%(filename)s:%(lineno)s - %(funcName)20s()] %(levelname)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S", level=logging.DEBUG)  
#    logging.Formatter.converter = time.gmtime
#
#    # define a Handler which writes INFO messages or higher to the sys.stderr
#    console = logging.StreamHandler()
#    console.setLevel(logging.INFO)
#    logging.getLogger('').addHandler(console)

    # run the aqawan heartbeat and weather checking asynchronously
#    aqawanThread = threading.Thread(target=heartbeat, args=(site, aqawan), kwargs={})
#    aqawanThread.start()

    imager.connect()
    telescope.initialize()

    # Take biases and darks
    doBias(site, aqawan, telescope, imager)
    doDark(site, aqawan, telescope, imager)

    ipdb.set_trace()

    # DO NOT GO BEYOND THIS POINT WITHOUT WEATHER STATION
    sys.exit()

    # keep trying to open the aqawan every minute
    # (probably a stupid way of doing this)
    response = -1
    while response == -1:
        response = aqawan.open()
        if response == -1: time.sleep(60)

   # ipdb.set_trace() # stop execution until we type 'cont' so we can keep the dome open 

    flatFilters = ['V']

    # Take Evening Sky flats
    doSkyFlat(imager, flatFilters)

    # Wait until sunset   
    timeUntilSunset = (site.sunset() - datetime.datetime.utcnow()).total_seconds()
    if timeUntilSunset > 0:
        logging.info('Waiting for sunset (' + str(timeUntilSunset) + 'seconds)')
        time.sleep(timeUntilSunset)
    
    # find the best focus for the night
    telescope.autoFocus()

    # read the target list
    with open(site.night + '.txt', 'r') as targetfile:
        for line in targetfile:
            target = parseTarget(line)
            
            # check if the end is before sunrise
            if target['endtime'] > sunrise: 
                target['endtime'] = sunrise
            # check if the start is after sunset
            if target['starttime'] < sunset: 
                target['starttime'] = sunset

            # Start Science Obs
            doScience(imager, target)
    
    # Take Morning Sky flats
    doSkyFlat(imager, flatFilters, morning=True)

    # Want to close the aqawan before darks and biases
    # closeAqawan in endNight just a double check
    aqawan.close()

    # Take biases and darks
    doDark(cam)
    doBias(cam)

    endNight(datapath)
    
    # Stop the aqawan thread
    site.observing = False
    
