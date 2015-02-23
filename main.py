import minerva_class_files.site as minervasite
import minerva_class_files.imager as minervaimager
import minerva_class_files.cdk700 as minervatelescope
import minerva_class_files.aqawan as minervaaqawan

import datetime, logging, os, sys, time, subprocess, glob, math, json
import ipdb
import socket, threading
import pyfits, ephem

def aqawanOpen(site, aqawan):
    response = -1
    if site.oktoopen and aqawan.lastClose < (datetime.datetime.utcnow() - datetime.timedelta(minutes=20)):
        response = aqawan.open_both()
    return response

def parseCalib(line):
    try:
        calibinfo = json.loads(line)
    except ValueError:
        logger.error('Not a valid JSON line: ' + line)
        return -1
    return calibinfo

def parseTarget(line):
    try:
        target = json.loads(line)
    except ValueError:
        logger.error('Not a valid JSON line: ' + line)
        return -1
    
    # convert strings to datetime objects
    target['starttime'] = datetime.datetime.strptime(target['starttime'],'%Y-%m-%d %H:%M:%S')
    target['endtime'] = datetime.datetime.strptime(target['endtime'],'%Y-%m-%d %H:%M:%S')
    return target

# should do this asychronously and continuously
def heartbeat(site, aqawan):
    
    while site.observing:
        logger.info(aqawan.heartbeat())
        if not site.oktoopen(open=True):
            aqawan.close_both()
        time.sleep(15)

def endNight(site, aqawan, telescope, imager):

    # park the scope
    telescope.park()

    # Close the aqawan
    aqawan.close_both()
    
    # Compress the data
    compressData(imager.dataPath)

    #TODO: Back up the data
#    site.backup()

def compressData(dataPath):
    files = glob.glob(dataPath + "/*.fits")
    for filename in files:
        logging.info('Compressing ' + filename)
        subprocess.call(['cfitsio/fpack.exe','-D',filename])

def prepNight():

    # reset the night at 10 am local
    today = datetime.datetime.utcnow()
    if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
        today = today + datetime.timedelta(days=1)
    night = 'n' + today.strftime('%Y%m%d')

    # make sure the log path exists
    logpath = 'logs/' + night + '/'
    if not os.path.exists(logpath):
        os.makedirs(logpath)
        
    hostname = socket.gethostname()

    # Select the config files based on the computer name
    if hostname == 't1-PC' or hostname == 't2-PC':
        site = minervasite.site('Pasadena',night,configfile='minerva_class_files/site.ini')
    elif hostname == 'pwi-PC' or hostname == 't4-PC':
        site = minervasite.site('Mount_Hopkins',night,configfile='minerva_class_files/site.ini')
    site.night = night

    site.startNightTime = datetime.datetime(today.year, today.month, today.day, 17) - datetime.timedelta(days=1)

    # initialize the first of everything
    aqawan = minervaaqawan.aqawan(site.enclosures[0],night,configfile='minerva_class_files/aqawan.ini')
    telescope = minervatelescope.CDK700(aqawan.telescopes[0],night,configfile='minerva_class_files/telescope.ini')
    imager = minervaimager.imager(telescope.imager,night,configfile='minerva_class_files/imager.ini')

    if hostname == 't1-PC':
        imager.dataPath = "C:/minerva/data/" + night + "/"
        imager.gitPath = "C:/Users/t1/AppData/Local/GitHub/PortableGit_c2ba306e536fdf878271f7fe636a147ff37326ad/bin/git.exe"
    elif hostname == 't2-PC':    
        imager.dataPath = "C:/minerva/data/" + night + "/"
        imager.gitPath = "C:/Users/t2/AppData/Local/GitHub/PortableGit_c2ba306e536fdf878271f7fe636a147ff37326ad/bin/git.exe"
    elif hostname == 'pwi-PC':
        imager.dataPath = "E:/minerva/data/" + night + "/"
        imager.gitPath = "C:/Users/pwi/AppData/Local/GitHub/PortableGit_c2ba306e536fdf878271f7fe636a147ff37326ad/bin/git.exe"
    elif hostname == 't4-PC':    
        imager.dataPath = "E:/minerva/data/" + night + "/"
        imager.gitPath = "C:/Users/t4/AppData/Local/GitHub/PortableGit_c2ba306e536fdf878271f7fe636a147ff37326ad/bin/git.exe"

    if not os.path.exists(imager.dataPath):
        os.makedirs(imager.dataPath)

    return site, aqawan, telescope, imager

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
    site.weather = -1
    while site.weather == -1: site.getWeather()
    telescopeStatus = telescope.getStatus()
    aqStatus = aqawan.status()    
    gitNum = subprocess.check_output([imager.gitPath, "rev-list", "HEAD", "--count"]).strip()

    while not imager.cam.ImageReady: time.sleep(0.01)

    # Save the image
    filename = imager.dataPath + "/" + site.night + "." + telescope.name + "." + objname + "." + filterInd + "." + getIndex(imager.dataPath) + ".fits"
    logger.info('Saving image: ' + filename)
    imager.cam.SaveImage(filename)

    # This only takes 15 ms
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
    if telescopeStatus.temperature == None:
        f[0].header['M1TEMP'] = ("N/A","Primary Mirror Temp (C)")
        f[0].header['M2TEMP'] = ("N/A","Secondary Mirror Temp (C)")
        f[0].header['M3TEMP'] = ("N/A","Tertiary Mirror Temp (C)")
        f[0].header['AMBTMP'] = ("N/A","Ambient Temp (C)")
        f[0].header['BCKTMP'] = ("N/A","Backplate Temp (C)")
    else:    
        f[0].header['M1TEMP'] = (telescopeStatus.temperature.primary,"Primary Mirror Temp (C)")
        f[0].header['M2TEMP'] = (telescopeStatus.temperature.secondary,"Secondary Mirror Temp (C)")
        f[0].header['M3TEMP'] = (telescopeStatus.temperature.m3,"Tertiary Mirror Temp (C)")
        f[0].header['AMBTMP'] = (telescopeStatus.temperature.ambient,"Ambient Temp (C)")
        f[0].header['BCKTMP'] = (telescopeStatus.temperature.backplate,"Backplate Temp (C)")

    # Weather station
    f[0].header['WJD'] = (str(site.weather['date']),"Last update of weather (UTC)")
    f[0].header['RAIN'] = (site.weather['wxt510Rain'],"Current Rain (mm?)")
    f[0].header['TOTRAIN'] = (site.weather['totalRain'],"Total rain since ?? (mm?)")
    f[0].header['OUTTEMP'] = (site.weather['outsideTemp'],"Outside Temperature (C)")
    f[0].header['SKYTEMP'] = (site.weather['relativeSkyTemp'],"Sky - Ambient (C)")
    f[0].header['DEWPOINT'] = (site.weather['outsideDewPt'],"Dewpoint (C)")
    f[0].header['WINDSPD'] = (site.weather['windSpeed'],"Wind Speed (mph)")
    f[0].header['WINDGUST'] = (site.weather['windGustSpeed'],"Wind Gust Speed (mph)")
    f[0].header['WINDIR'] = (site.weather['windDirectionDegrees'],"Wind Direction (Deg E of N)")
    f[0].header['PRESSURE'] = (site.weather['barometer'],"Outside Pressure (mmHg?)")
    f[0].header['SUNALT'] = (site.weather['sunAltitude'],"Sun Altitude (deg)")

    f.flush()
    f.close()
    
    return filename


def doBias(site, aqawan, telescope, imager, num=11):
    doDark(site, aqawan, telescope, imager,exptime=0,num=num)

def doDark(site, aqawan, telescope, imager, exptime=60, num=11):

    DARK = 0
    if exptime == 0:
        objectName = 'Bias'
        for x in range(num):    
            logger.info('Taking ' + objectName + ' ' + str(x+1) + ' of ' + str(num) + ' (exptime = ' + str(exptime) + ')')
            takeImage(site, aqawan, telescope, imager, exptime,'V',objectName)
    else:
        objectName = 'Dark'
    # Take num Dark frames and loop over more than one exptime
        for time in exptime:
            for x in range(num):    
                logger.info('Taking ' + objectName + ' ' + str(x+1) + ' of ' + str(num) + ' (exptime = ' + str(time) + ')')
                takeImage(site, aqawan, telescope, imager, time,'V',objectName)

def getMean(filename):
    image = pyfits.getdata(filename,0)
    return image.mean()

def doSkyFlat(site, aqawan, telescope, imager, filters, morning=False, num=11):

    minSunAlt = -12
    maxSunAlt = -2

    biasLevel = 300
    targetCounts = 30000
    saturation = 55000
    maxExpTime = 60
    minExpTime = 10
   
    # can we actually do flats right now?
    if datetime.datetime.now().hour > 12:
        # Sun setting (evening)
        if morning:
            logger.info('Sun setting and morning flats requested; skipping')
            return
        if site.sunalt() < minSunAlt:
            logger.info('Sun setting and already too low; skipping')
            return               
        site.obs.horizon = str(maxSunAlt)
        flatStartTime = site.obs.next_setting(ephem.Sun(),start=site.startNightTime, use_center=True).datetime()
        secondsUntilTwilight = (flatStartTime - datetime.datetime.utcnow()).total_seconds() - 300.0
    else:
        # Sun rising (morning)
        if not morning:
            logger.info('Sun rising and evening flats requested; skipping')
            return
        if site.sunalt() > maxSunAlt:
            logger.info('Sun rising and already too high; skipping')
            return  
        site.obs.horizon = str(minSunAlt)
        flatStartTime = site.obs.next_rising(ephem.Sun(),start=site.startNightTime, use_center=True).datetime()
        secondsUntilTwilight = (flatStartTime - datetime.datetime.utcnow()).total_seconds() - 300.0

    if secondsUntilTwilight > 7200:
        logger.info('Twilight too far away (' + str(secondsUntilTwilight) + " seconds)")
        return

#    ipdb.set_trace()
    # wait for twilight
    if secondsUntilTwilight > 0 and (site.sunalt() < minSunAlt or site.sunalt() > maxSunAlt):
        logger.info('Waiting ' +  str(secondsUntilTwilight) + ' seconds until Twilight')
        time.sleep(secondsUntilTwilight)

    # Now it's within 5 minutes of twilight flats
    logger.info('Beginning twilight flats')

    # make sure the telescope/dome is ready for obs
    telescope.initialize()
    
    # start off with the extreme exposure times
    if morning: exptime = maxExpTime
    else: exptime = minExpTime
  
    # filters ordered from least transmissive to most transmissive
    # flats will be taken in this order (or reverse order in the evening)
    masterfilters = ['H-Beta','H-Alpha','Ha','Y','U','up','zp','zs','B','I','ip','V','rp','R','gp','w','solar','air']
    if morning: masterfilters.reverse()

    for filterInd in masterfilters:
        if filterInd in filters and filterInd in imager.filters:

            i = 0
            while i < num:
                
                # Slew to the optimally flat part of the sky (Chromey & Hasselbacher, 1996)
                Alt = 75.0 # degrees (somewhat site dependent)
                Az = site.sunaz() + 180.0 # degrees
                if Az > 360.0: Az = Az - 360.0
            
                # keep slewing to the optimally flat part of the sky (dithers too)
                logger.info('Slewing to the optimally flat part of the sky (alt=' + str(Alt) + ', az=' + str(Az) + ')')
                telescope.mountGotoAltAz(Alt,Az)

                if telescope.inPosition():
                    logger.info("Finished slew to alt=" + str(Alt) + ', az=' + str(Az) + ')')
                else:
                    logger.error("Slew failed to alt=" + str(Alt) + ', az=' + str(Az) + ')')
                    # now what?
            
                # Take flat fields
                filename = takeImage(site, aqawan, telescope, imager, exptime, filterInd, 'SkyFlat')
                
                # determine the mode of the image (mode requires scipy, use mean for now...)
                mode = getMean(filename)
                logger.info("image " + str(i+1) + " of " + str(num) + " in filter " + filterInd + "; " + filename + ": mode = " + str(mode) + " exptime = " + str(exptime) + " sunalt = " + str(site.sunalt()))
                if mode > saturation:
                    # Too much signal
                    logger.info("Flat deleted: exptime=" + str(exptime) + " Mode=" + str(mode) +
                                '; sun altitude=' + str(site.sunalt()) +
                                 "; exptime=" + str(exptime) + '; filter = ' + filterInd)
                    os.remove(filename)
                    i-=1
                    if exptime == minExpTime and morning:
                        logger.info("Exposure time at minimum, image saturated, and getting brighter; skipping remaining exposures in filter " + filterInd)
                        break
                elif mode < 2.0*biasLevel:
                    # Too little signal
                    logger.info("Flat deleted: exptime=" + str(exptime) + " Mode=" + str(mode) + '; sun altitude=' + str(site.sunalt()) +
                                 "; exptime=" + str(exptime) + '; filter = ' + filterInd)
                    os.remove(filename)
                    i -= 1

                    if exptime == maxExpTime and not morning:
                        logger.info("Exposure time at maximum, not enough counts, and getting darker; skipping remaining exposures in filter " + filterInd)
                        break
                elif morning and site.sunalt() > maxSunAlt:
                    logger.info("Sun rising and greater than maxsunalt; skipping")
                    break
                elif not morning and site.sunalt() < minSunAlt:
                    logger.info("Sun setting and less than minsunalt; skipping")
                    break                    

 #              else:
 #                  just right...
        
                # Scale exptime to get a mode of targetCounts in next exposure
                if mode-biasLevel <= 0:
                    exptime = maxExpTime
                else:
                    exptime = exptime*(targetCounts-biasLevel)/(mode-biasLevel)
                    # do not exceed limits
                    exptime = max([minExpTime,exptime])
                    exptime = min([maxExpTime,exptime])
                    logger.info("Scaling exptime to " + str(exptime))
                i += 1

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
                while not aqawan.isOpen:
                    response = aqawanOpen(site,aqawan)
                    if response == -1:
                        logger.info('Enclosure closed; waiting for conditions to improve') 
                        time.sleep(60)
                    if datetime.datetime.utcnow() > target['endtime']: return
                    # reacquire the target
                    if aqawan.isOpen: telescope.acquireTarget(target['ra'],target['dec'])

                if datetime.datetime.utcnow() > target['endtime']: return
                if i < target['num'][j]:
                        logger.info('Beginning ' + str(i+1) + " of " + str(target['num'][j]) + ": " + str(target['exptime'][j]) + ' second exposure of ' + target['name'] + ' in the ' + target['filter'][j] + ' band') 
                        takeImage(site, aqawan, telescope, imager, target['exptime'][j], target['filter'][j], target['name'])
                
    else:
        # take all in each band, then loop over filters (e.g., B,B,B,V,V,V,R,R,R) 
        for j in range(len(target['filter'])):
            # cycle by number
            for i in range(target['num'][j]):

                # if the enclosure is not open, wait until it is
                while not aqawan.isOpen:
                    response = aqawanOpen(site,aqawan)
                    if response == -1:
                        logger.info('Enclosure closed; waiting for conditions to improve') 
                        time.sleep(60)
                    if datetime.datetime.utcnow() > target['endtime']: return
                    # reacquire the target
                    if aqawan.isOpen: telescope.acquireTarget(target['ra'],target['dec'])
                
                if datetime.datetime.utcnow() > target['endtime']: return
                logger.info('Beginning ' + str(i+1) + " of " + str(target['num'][j]) + ": " + str(target['exptime'][j]) + ' second exposure of ' + target['name'] + ' in the ' + target['filter'][j] + ' band') 
                takeImage(site, aqawan, telescope, imager, target['exptime'][j], target['filter'][j], target['name'])

if __name__ == '__main__':

    site, aqawan, telescope, imager = prepNight()
        
    # setting up site logger
    logger = logging.getLogger('main')
    formatter = logging.Formatter(fmt="%(asctime)s [%(filename)s:%(lineno)s - %(funcName)20s()] %(levelname)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
    fileHandler = logging.FileHandler('logs/' + site.night + '/main.log', mode='a')
    fileHandler.setFormatter(formatter)
    streamHandler = logging.StreamHandler()
    streamHandler.setFormatter(formatter)

    logger.setLevel(logging.DEBUG)
    logger.addHandler(fileHandler)
    logger.addHandler(streamHandler)

    # run the aqawan heartbeat and weather checking asynchronously
    aqawanThread = threading.Thread(target=heartbeat, args=(site, aqawan), kwargs={})
    aqawanThread.start()

    # ipdb.set_trace()
    
    imager.connect()
    telescope.initialize()

    ipdb.set_trace()

    # Open the target file and read the first line for calibration info
    # then close the file
    with open('schedule/' + site.night + '.txt', 'r') as calibfile:
        calibline = calibfile.readline()
        CalibInfo = parseCalib(calibline)

    # Take biases and darks
   	doBias(site, aqawan, telescope, imager, num=CalibInfo['nbias'])
    doDark(site, aqawan, telescope, imager, num=CalibInfo['ndark'], exptime=CalibInfo['darkexptime'])

    # Wait until sunset   
    timeUntilSunset = (site.sunset() - datetime.datetime.utcnow()).total_seconds()
    if timeUntilSunset > 0:
        logger.info('Waiting for sunset (' + str(timeUntilSunset) + 'seconds)')
        time.sleep(timeUntilSunset)

    # keep trying to open the aqawan every minute
    # (probably a stupid way of doing this)
    response = -1
    while response == -1:
        response = aqawanOpen(site, aqawan)
        if response == -1: time.sleep(60)

   # ipdb.set_trace() # stop execution until we type 'cont' so we can keep the dome open 

    flatFilters = CalibInfo['flatFilters']

    # Take Evening Sky flats
    doSkyFlat(site, aqawan, telescope, imager, flatFilters, num=CalibInfo['nflat'])
   
    # find the best focus for the night
    telescope.autoFocus()

    # Wait until nautical twilight ends 
    timeUntilTwilEnd = (site.NautTwilEnd() - datetime.datetime.utcnow()).total_seconds()
    if timeUntilTwilEnd > 0:
        logger.info('Waiting for nautical twilight to end (' + str(timeUntilTwilEnd) + 'seconds)')
        time.sleep(timeUntilTwilEnd)

    # read the target list
    with open('schedule/' + site.night + '.txt', 'r') as targetfile:
        next(targetfile) # skip the calibration header
        for line in targetfile:
            target = parseTarget(line)

            if target <> -1:
            
                # check if the end is after morning twilight begins
                if target['endtime'] > site.NautTwilBegin(): 
                    target['endtime'] = site.NautTwilBegin()
                # check if the start is after evening twilight ends
                if target['starttime'] < site.NautTwilEnd(): 
                    target['starttime'] = site.NautTwilEnd()

                # Start Science Obs
                doScience(site, aqawan, telescope, imager, target)
    
    # Take Morning Sky flats
    # Check if we want to wait for these
    if CalibInfo['WaitForMorning']:
    	doSkyFlat(site, aqawan, telescope, imager, flatFilters, num=CalibInfo['nflat'], morning=True)

    # Want to close the aqawan before darks and biases
    # closeAqawan in endNight just a double check
    telescope.park()
    aqawan.close_both()

    # Take biases and darks
    doBias(site, aqawan, telescope, imager, num=CalibInfo['nbias'])
    doDark(site, aqawan, telescope, imager, num=CalibInfo['ndark'], exptime=CalibInfo['darkexptime'])

    endNight(site, aqawan, telescope, imager)
    
    # Stop the aqawan thread
    site.observing = False
    
