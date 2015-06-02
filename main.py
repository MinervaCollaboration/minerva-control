import minerva_class_files.site as minervasite
import minerva_class_files.imager as minervaimager
import minerva_class_files.cdk700 as minervatelescope
import minerva_class_files.aqawan as minervaaqawan
import minerva_class_files.segments as segments
import minerva_class_files.mail as mail
import numpy as np
from minerva_class_files.get_all_centroids import *
import shutil

import datetime, logging, os, sys, time, subprocess, glob, math, json, copy
import ipdb
import socket, threading
import pyfits, ephem
from scipy import stats

def ten(string):
    array = string.split()
    if "-" in array[0]:
        return float(array[0]) - float(array[1])/60.0 - float(array[2])/3600.0
    return float(array[0]) + float(array[1])/60.0 + float(array[2])/3600.0

def astrometry(imageName):

    hdr = pyfits.getheader(imageName)
    pixscale = float(hdr['PIXSCALE'])
    ra = float(hdr['RA'])
    dec = float(hdr['DEC'])
    radius = 3.0*pixscale*float(hdr['NAXIS1'])/3600.0

    cmd = 'solve-field --scale-units arcsecperpix' + \
                     ' --scale-low ' + str(0.99*pixscale) + \
                     ' --scale-high ' + str(1.01*pixscale) + \
                     ' --ra ' + str(ra) + \
                     ' --dec ' + str(dec) + \
                     ' --radius ' + str(radius) +\
                     ' --quad-size-min 0.5' + \
                     ' --quad-size-max 0.5' + \
                     ' --cpulimit 60' + \
                     ' --no-verify' + \
                     ' --crpix-center' + \
                     ' --no-fits2fits' + \
                     ' --no-plots' + \
                     ' --overwrite ' + \
                      imageName
    #                     ' --use-sextractor' + \ #need to install sextractor

    cmd = r'C:\cygwin\bin\bash --login -c "' + cmd + '"'
    print cmd
    os.system(cmd)

def getPA(imageName):

    logger.info('Finding PA for ' + imageName)
    astrometry(imageName)

    baseName = os.path.splitext(imageName)[0]
    if os.path.exists(baseName + '.solved'):
        hdr = pyfits.getheader(baseName + '.wcs')
        cd11 = float(hdr['CD1_1'])
        cd12 = float(hdr['CD1_2'])
        racen = float(hdr['CRVAL1'])*math.pi/180.0
        deccen = float(hdr['CRVAL2'])*math.pi/180.0
        
        PA = 180.0/math.pi*math.atan2(-cd12,-cd11) # this one?
        PA = 180.0/math.pi*math.atan2(cd12,-cd11) # or this one?

        # is it close to what we thought?
        orighdr = pyfits.getheader(imageName)
        origcd11 = float(orighdr['CD1_1'])
        origcd12 = float(orighdr['CD1_2'])
        origPA = 180.0/math.pi*math.atan2(origcd12,-origcd11)
        origracen = float(orighdr['CRVAL1'])*math.pi/180.0
        origdeccen = float(orighdr['CRVAL2'])*math.pi/180.0

        dPA = 180.0/math.pi*math.atan2(math.sin((PA-origPA)*math.pi/180.0), math.cos((PA-origPA)*math.pi/180.0))
        dRA = 648000.0/math.pi*(racen-origracen)/math.cos(deccen)
        dDec = 648000.0/math.pi*(deccen-origdeccen)
        dtheta = 648000.0/math.pi*math.acos(math.sin(deccen)*math.sin(origdeccen) + math.cos(deccen)*math.cos(origdeccen)*math.cos(racen-origracen))

        logger.info("Telescope PA = " + str(origPA) + '; solved PA = ' + str(PA) + '; offset = ' + str(dPA) + ' degrees')
        logger.info("Telescope RA = " + str(origracen) + '; solved RA = ' + str(racen) + '; offset = ' + str(dRA) + ' arcsec')
        logger.info("Telescope Dec = " + str(origdeccen) + '; solved Dec = ' + str(deccen) + '; offset = ' + str(dDec) + ' arcsec')
        logger.info("Total pointing error = " + str(dtheta) + ' arcsec')

        if abs(dPA) > 5:
            logger.error("PA out of range")
            if not os.path.exists("disableGuiding.txt"):
                mail.send("PA error too large","The PA error (" + str(dPA) + " deg) is too large for " + imageName + "; disabling guiding. Please home/recalibrate the rotator and delete disableGuiding.txt",level='serious')
                with open("disableGuiding.txt","w") as f:
                    f.write(str(datetime.datetime.utcnow()))
                            
        if dtheta > 600:
            logger.error("Pointing error too large")
            mail.send("Pointing error too large","The pointing error (" + str(dtheta) + " arcsec) is too large for " + imageName + ". Please redo the pointing model",level='serious')

    else:
        PA = None

    return PA

def getstars(imageName):
    
    d = getfitsdata(imageName)
    th = threshold_pyguide(d, level = 4)

    if np.max(d*th) == 0.0:
        return np.zeros((1,3))
    
    imtofeed = np.array(np.round((d*th)/np.max(d*th)*255), dtype='uint8')
    cc = centroid_all_blobs(imtofeed)

    return cc

def guide(filename, reference):

    threshhold = 60.0 # maximum offset in X or Y (larger corrections will be ignored)
    maxangle = 5.0 # maximum offset in theta (larger corrections will be ignored)

    if os.path.exists("disableGuiding.txt"):
        logger.info("Guiding disabled")
        return None

    if reference == None:
        logger.info("No reference frame defined yet; using " + filename)
        reference = getstars(filename)
        if len(reference[:,0]) < 6:
            logger.error("Not enough stars in reference frame")
            return None
        return reference

    logger.info("Extracting stars for " + filename)
    stars = getstars(filename)
    if len(stars[:,0]) < 6:
        logger.error("Not enough stars in frame")
        return reference

    # run the aqawan heartbeat and weather checking asynchronously
    logger.info("Running astrometry to find PA on " + filename)
    astrometryThread = threading.Thread(target=getPA, args=(filename,), kwargs={})
    astrometryThread.start()

    # proportional servo gain (apply this fraction of the offset)
    gain = 0.66

    # get the platescale from the header
    hdr = pyfits.getheader(filename)
    platescale = float(hdr['PIXSCALE'])
    dec = float(hdr['CRVAL2'])*math.pi/180.0 # declination in radians
    PA = math.acos(float(-hdr['CD1_1'])*3600.0/platescale) # position angle in radians
    logger.info("Image PA=" + str(PA))

    m0 = 22
    x = stars[:,0]
    y = stars[:,1]
    mag = -2.5*np.log10(stars[:,2])+m0

    xref = reference[:,0]
    yref = reference[:,1]
    magref = -2.5*np.log10(reference[:,2])+m0

    logger.info("Getting offset for " + filename)
    dx,dy,scale,rot,flag,rmsf,nstf = findoffset(x, y, mag, xref, yref, magref)

    logger.info("dx=" + str(dx) + ", dy=" + str(dy) + ", scale=" + str(scale) +
                ", rot=" + str(rot) + ", flag=" + str(flag) +
                ", rmsf=" + str(rmsf) + ", nstf=" + str(nstf))
    
    if abs(dx) > threshhold or abs(dy) > threshhold or abs(rot) > maxangle:
        logger.error("Offset too large; ignoring")
        return reference

    # adjust the rotator angle (sign?)
    logger.info("Adjusting the rotator by " + str(rot*gain) + " degrees")
    telescope.rotatorIncrement(rot*gain)

    # adjust RA/Dec (need to calibrate PA)
    deltaRA = -(dx*math.cos(PA) - dy*math.sin(PA))*math.cos(dec)*platescale*gain
    deltaDec = (dx*math.sin(PA) + dy*math.cos(PA))*platescale*gain
    logger.info("Adjusting the RA,Dec by " + str(deltaRA) + "," + str(deltaDec))
    telescope.mountOffsetRaDec(deltaRA,deltaDec)

    # correction sent
    telescope.rotatorMailsent=False

    return reference

# finds the offset (x, y, theta) between two star lists)
def findoffset(x, y, mag, xref, yref, magref):

    MAXSTARS = 50 # only consider MAXSTARS brightest stars
    thet=0.0 # thet +/- dthet (deg)
    dthet=3.0 # maximum allowed rotation between images (deg)

    # allowed change in scale from image to image
    scl = 0.0 # 1 + scl +/- dscl
    dscl = 0.01

    # size of the image (should be dynamic)
    # actually, twice the center pixel of the rotator
    naxis1 = 2048
    naxis2 = 2048

    maxstars = min(MAXSTARS,len(xref))
    sortndx = np.argsort(magref)
       
    xreftrunc = xref[sortndx[0:maxstars]]
    yreftrunc = yref[sortndx[0:maxstars]]
    magreftrunc = magref[sortndx[0:maxstars]]
    lindx1,lparm1 = segments.listseg(xreftrunc, yreftrunc, magreftrunc)

    maxstars = min(MAXSTARS,len(x))

    sortndx = np.argsort(mag)
    xtrunc = x[sortndx[0:maxstars]]
    ytrunc = y[sortndx[0:maxstars]]
    magtrunc = mag[sortndx[0:maxstars]]
    lindx2,lparm2 = segments.listseg(xtrunc, ytrunc, magtrunc)
    
    # magic
    dx,dy,scale,rot,mat,flag,rmsf,nstf = \
        segments.fitlists4(naxis1,naxis2,lindx1,lparm1,lindx2,lparm2,\
                               xreftrunc,yreftrunc,xtrunc,ytrunc,scl,dscl,thet,dthet)

    return dx,dy,scale,rot,flag,rmsf,nstf


def aqawanOpen(site, aqawan):
    response = -1

    if aqawan.lastClose > (datetime.datetime.utcnow() - datetime.timedelta(minutes=20)):
        logger.info('Aqawan closed at ' + str(aqawan.lastClose) + '; waiting 20 minutes for conditions to improve')
        return response
    
    if site.oktoopen():
        logger.info('Weather is good; opening telescope')
        response = aqawan.open_both()
    else:
        if site.sunalt() < 6:
            logger.info('Weather still not ok; resetting timeout')
            aqawan.lastClose = datetime.datetime.utcnow()

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
        t0 = datetime.datetime.utcnow()
        if not site.oktoopen(open=True):
            aqawan.close_both()
        else:
            logger.debug(aqawan.heartbeat())

        # send a heartbeat every 14 seconds
        sleeptime = max(14.0-(datetime.datetime.utcnow() - t0).total_seconds(),0)
        time.sleep(sleeptime)

def endNight(site, aqawan, telescope, imager):

    # park the scope
    logger.info("Parking Telescope")
    telescope.park()

    # Close the aqawan
    logger.info("Closing aqawan")
    aqawan.close_both()
    
    # Compress the data
    logger.info("Compressing data")
    compressData(imager.dataPath)

    # Turn off the camera cooler, disconnect
    logger.info("Disconnecting imager")
    imager.disconnect()

    #TODO: Back up the data
    #site.backup()

    # copy schedule to data directory
    logger.info("Copying schedule file from ./schedule/" + site.night + ".txt to " + imager.dataPath)
    shutil.copyfile("./schedule/" + site.night + ".txt", imager.dataPath + site.night + ".txt")

    # copy logs to data directory
    logs = glob.glob("./logs/" + site.night + "/*.log")
    for log in logs:
        logger.info("Copying log file " + log + " to " + imager.dataPath)
        shutil.copyfile(log, imager.dataPath + os.path.basename(log))

    # email completion notice
    mail.send(telescope.name + ' done observing','Love,\nMINERVA')

def compressData(dataPath):
    files = glob.glob(dataPath + "/*.fits")
    for filename in files:
#        logger.info('Compressing ' + filename)
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

    site = minervasite.site('Mount_Hopkins',night,configfile='minerva_class_files/site.ini')
    site.night = night

    site.startNightTime = datetime.datetime(today.year, today.month, today.day, 17) - datetime.timedelta(days=1)

    # initialize the first of everything
    telname =  hostname.split('-')[0] 
    if telname == 't1': 
	aqawanndx = 0
	telndx = 0
    elif telname == 't2':
	aqawanndx = 0
	telndx = 1
    elif telname == 't3':
	aqawanndx = 1
	telndx = 0
    elif telname == 't4':
        aqawanndx = 1
        telndx = 1

    aqawan = minervaaqawan.aqawan(site.enclosures[aqawanndx],night,configfile='minerva_class_files/aqawan.ini')
    telescope = minervatelescope.CDK700(aqawan.telescopes[telndx],night,configfile='minerva_class_files/telescope.ini')
    imager = minervaimager.imager(telescope.imager,night,configfile='minerva_class_files/imager.ini')

    imager.dataPath = "D:/minerva/data/" + night + "/"
    imager.gitPath = "C:/Users/" + telname + "/AppData/Local/GitHub/PortableGit_c2ba306e536fdf878271f7fe636a147ff37326ad/bin/git.exe"

    if not os.path.exists(imager.dataPath):
        os.makedirs(imager.dataPath)

    # email notice
    mail.send(telescope.name + ' Starting observing','Love,\nMINERVA')

    return site, aqawan, telescope, imager

def getIndex(dirname):
    files = glob.glob(dirname + "/*.fits*")

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
   
    # Take image
    logger.info("Taking " + str(exptime) + " second image")
    t0 = datetime.datetime.utcnow()
    imager.cam.Expose(exptime, exptype, imager.filters[filterInd])

    # Get status info for headers while exposing/reading out
    # (needs error handling)
    weather = -1
    while weather == -1:
        site.getWeather()
        weather = copy.deepcopy(site.weather)
        
    telescopeStatus = telescope.getStatus()
    telra = ten(telescopeStatus.mount.ra_2000)*15.0
    teldec = ten(telescopeStatus.mount.dec_2000)
    ra = ten(telescopeStatus.mount.ra_target)*15.0
    dec = ten(telescopeStatus.mount.dec_target)
    if dec > 90.0: dec = dec-360 # fixes bug in PWI

    moonpos = site.moonpos()
    moonra = moonpos[0]
    moondec = moonpos[1]
    moonsep = ephem.separation((telra*math.pi/180.0,teldec*math.pi/180.0),moonpos)*180.0/math.pi
    moonphase = site.moonphase()

    aqStatus = aqawan.status()    

    gitNum = subprocess.check_output([imager.gitPath, "rev-list", "HEAD", "--count"]).strip()

    try:
        while not imager.cam.ImageReady:
            if (datetime.datetime.utcnow()-t0).total_seconds() > (exptime  + 60):
                logger.error("Imager has been reading out for over a minute; beginning recovery")
                imager.nfailed=1
                imager.recover()
                imager.connect()
            time.sleep(0.01)
    except:
        logger.error("Camera failure: " + str(sys.exc_info()[0]))
        mail.send("Camera failure on " + telescope.name,"Camera failure on " + telescope.name + ": " + str(sys.exc_info()[0]) + "\n\nPlease reconnect, power cycle the panel, or reboot the machine.\n\nLove,\n" + telescope.name, level='serious')
        imager.nfailed=1
        imager.recover()
        imager.connect()

    # Save the image
    filename = imager.dataPath + "/" + site.night + "." + telescope.name + "." + objname + "." + filterInd + "." + getIndex(imager.dataPath) + ".fits"
    logger.info('Saving image: ' + filename)
    imager.cam.SaveImage(filename)

    # This only takes 15 ms
    logger.debug('Opening ' + filename + " to modify header")
    f = pyfits.open(filename, mode='update')

    # Static Keywords
    logger.debug('Inserting static keywords')
    f[0].header['SITELAT'] = str(site.obs.lat)
    f[0].header['SITELONG'] = (str(site.obs.lon),"East Longitude of the imaging location")
    f[0].header['SITEALT'] = (site.obs.elevation,"Site Altitude (m)")
    f[0].header['OBSERVER'] = ('MINERVA Robot',"Observer")
    f[0].header['TELESCOP'] = telescope.name
    f[0].header['OBJECT'] = objname
    f[0].header['APTDIA'] = 700
    f[0].header['APTAREA'] = 490000
    f[0].header['ROBOVER'] = (gitNum,"Git commit number for robotic control software")

    # Site Specific
    logger.debug('Inserting LST')
    f[0].header['LST'] = (telescopeStatus.status.lst,"Local Sidereal Time")

    # Enclosure Specific
    logger.debug('Inserting Enclosure keywords')
    try:
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
    except AttributeError:
        logger.error('Failed to get enclosure keywords!')
        f[0].header['AQSOFTV'] = ("UNKNOWN","Aqawan software version number")
        f[0].header['AQSHUT1'] = ("UNKNOWN","Aqawan shutter 1 state")
        f[0].header['AQSHUT2'] = ("UNKNOWN","Aqawan shutter 2 state")
        f[0].header['INHUMID'] = ("UNKNOWN","Humidity inside enclosure")
        f[0].header['DOOR1'] = ("UNKNOWN","Door 1 into aqawan state")
        f[0].header['DOOR2'] = ("UNKNOWN","Door 2 into aqawan state")
        f[0].header['PANELDR'] = ("UNKNOWN","Aqawan control panel door state")
        f[0].header['HRTBEAT'] = ("UNKNOWN","Heartbeat timer")
        f[0].header['AQPACUP'] = ("UNKNOWN","PAC uptime (seconds)")
        f[0].header['AQFAULT'] = ("UNKNOWN","Aqawan fault present?")
        f[0].header['AQERROR'] = ("UNKNOWN","Aqawan error present?")
        f[0].header['PANLTMP'] = ("UNKNOWN","Aqawan control panel exhaust temp (C)")
        f[0].header['AQTEMP'] = ("UNKNOWN","Enclosure temperature (C)")
        f[0].header['AQEXTMP'] = ("UNKNOWN","Enclosure exhaust temperature (C)")
        f[0].header['AQINTMP'] = ("UNKNOWN","Enclosure intake temperature (C)")
        f[0].header['AQLITON'] = ("UNKNOWN","Aqawan lights on?")

    # Mount specific
    logger.debug('Inserting Mount keywords')
    f[0].header['TELRA'] = (telra,"Telescope RA (J2000 deg)")
    f[0].header['TELDEC'] = (teldec,"Telescope Dec (J2000 deg)")
    f[0].header['RA'] = (ra, "Target RA (J2000 deg)")    
    f[0].header['DEC'] =  (dec, "Target Dec (J2000 deg)")
    f[0].header['MOONRA'] = (moonra, "Moon RA (J2000)")    
    f[0].header['MOONDEC'] =  (moondec, "Moon Dec (J2000)")
    f[0].header['MOONPHAS'] = (moonphase, "Moon Phase (Fraction)")    
    f[0].header['MOONDIST'] =  (moonsep, "Distance between pointing and moon (deg)")
    f[0].header['PMODEL'] = (telescopeStatus.mount.pointing_model,"Pointing Model File")

    # Focuser Specific
    logger.debug('Inserting Focuser keywords')
    f[0].header['FOCPOS'] = (telescopeStatus.focuser.position,"Focus Position (microns)")

    # Rotator Specific
    logger.debug('Inserting Rotator keywords')
    f[0].header['ROTPOS'] = (telescopeStatus.rotator.position,"Rotator Position (degrees)")

    # WCS
    logger.debug('Inserting WCS keywords')
    platescale = imager.platescale/3600.0*imager.xbin # deg/pix
    PA = 0.0 #float(telescopeStatus.rotator.position)*math.pi/180.0
    f[0].header['PIXSCALE'] = imager.platescale*imager.xbin
    f[0].header['CTYPE1'] = ("RA---TAN","TAN projection")
    f[0].header['CTYPE2'] = ("DEC--TAN","TAN projection")
    f[0].header['CUNIT1'] = ("deg","X pixel scale units")
    f[0].header['CUNIT2'] = ("deg","Y pixel scale units")    
    f[0].header['CRVAL1'] = (telra,"RA of reference point")
    f[0].header['CRVAL2'] = (teldec,"DEC of reference point")
    f[0].header['CRPIX1'] = (imager.xcenter,"X reference pixel")
    f[0].header['CRPIX2'] = (imager.ycenter,"Y reference pixel")
    f[0].header['CD1_1'] = -platescale*math.cos(PA)
    f[0].header['CD1_2'] = platescale*math.sin(PA)
    f[0].header['CD2_1'] = platescale*math.sin(PA)
    f[0].header['CD2_2'] = platescale*math.cos(PA)

    # M3 Specific
    logger.debug('Inserting M3 keywords')
    f[0].header['PORT'] = (telescopeStatus.m3.port,"Selected port")    
    
    # Fans
    logger.debug('Inserting Fan keywords')
    f[0].header['OTAFAN'] = (telescopeStatus.fans.on,"OTA Fans on?")    

    # Telemetry
    logger.debug('Inserting Telescope telemetry keywords') 
    try: 
        f[0].header['M1TEMP'] = (telescopeStatus.temperature.primary,"Primary Mirror Temp (C)")
        f[0].header['M2TEMP'] = (telescopeStatus.temperature.secondary,"Secondary Mirror Temp (C)")
        f[0].header['M3TEMP'] = (telescopeStatus.temperature.m3,"Tertiary Mirror Temp (C)")
        f[0].header['AMBTMP'] = (telescopeStatus.temperature.ambient,"Ambient Temp (C)")
        f[0].header['BCKTMP'] = (telescopeStatus.temperature.backplate,"Backplate Temp (C)")
    except:
        logger.error('Failed to get the telescope telemetry keywords!')
        f[0].header['M1TEMP'] = ("UNKNOWN","Primary Mirror Temp (C)")
        f[0].header['M2TEMP'] = ("UNKNOWN","Secondary Mirror Temp (C)")
        f[0].header['M3TEMP'] = ("UNKNOWN","Tertiary Mirror Temp (C)")
        f[0].header['AMBTMP'] = ("UNKNOWN","Ambient Temp (C)")
        f[0].header['BCKTMP'] = ("UNKNOWN","Backplate Temp (C)")

    # Weather station
    f[0].header['WJD'] = (str(weather['date']),"Last update of weather (UTC)")
    f[0].header['RAIN'] = (weather['wxt510Rain'],"Current Rain (mm?)")
    f[0].header['TOTRAIN'] = (weather['totalRain'],"Total rain since ?? (mm?)")
    f[0].header['OUTTEMP'] = (weather['outsideTemp'],"Outside Temperature (C)")
    f[0].header['SKYTEMP'] = (weather['relativeSkyTemp'],"Sky - Ambient (C)")
    f[0].header['DEWPOINT'] = (weather['outsideDewPt'],"Dewpoint (C)")
    f[0].header['WINDSPD'] = (weather['windSpeed'],"Wind Speed (mph)")
    f[0].header['WINDGUST'] = (weather['windGustSpeed'],"Wind Gust Speed (mph)")
    f[0].header['WINDIR'] = (weather['windDirectionDegrees'],"Wind Direction (Deg E of N)")
    f[0].header['PRESSURE'] = (weather['barometer'],"Outside Pressure (mmHg?)")
    f[0].header['SUNALT'] = (weather['sunAltitude'],"Sun Altitude (deg)")

    logger.debug('Updating header')
    f.flush()
    f.close()
    logger.debug('Done saving image: ' + filename)
    
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

def getMode(filename):
    image = pyfits.getdata(filename,0)

    # mode is slow; take the central 100x100 region
    # (or the size of the image, which ever is smaller)
    nx = len(image)
    ny = len(image[1])
    size = 100
    x1 = max(nx/2.0 - size/2.0,0)
    x2 = min(nx/2.0 + size/2.0,nx-1)
    y1 = max(ny/2.0 - size/2.0,0)
    y2 = min(ny/2.0 + size/2.0,ny-1)
    
    return stats.mode(image[x1:x2,y1:y2],axis=None)[0][0]

def isSupersaturated(filename):
    image = pyfits.getdata(filename,0)

    # mode is slow; take the central 100x100 region
    # (or the size of the image, which ever is smaller)
    nx = len(image)
    ny = len(image[1])
    size = 100
    x1 = max(nx/2.0 - size/2.0,0)
    x2 = min(nx/2.0 + size/2.0,nx-1)
    y1 = max(ny/2.0 - size/2.0,0)
    y2 = min(ny/2.0 + size/2.0,ny-1)

    photonNoise = 10.0 # made up, should do this better
    if np.std(image[x1:x2,y1:y2],axis=None) < photonNoise:
        return True
    
    return False

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
    # flats will be taken in this order (or reverse order in the morning)
    masterfilters = ['H-Beta','H-Alpha','Ha','Y','U','up','zp','zs','B','I','ip','V','rp','R','gp','w','solar','air']
    if morning: masterfilters.reverse()  

    for filterInd in masterfilters:
        if filterInd in filters and filterInd in imager.filters:

            i = 0
            NotFirstImage = 0
            while i < num:

                # Slew to the optimally flat part of the sky (Chromey & Hasselbacher, 1996)
                Alt = 75.0 # degrees (somewhat site dependent)
                Az = site.sunaz() + 180.0 # degrees
                if Az > 360.0: Az = Az - 360.0
                
                # keep slewing to the optimally flat part of the sky (dithers too)
                # DeltaPos is here to check if we're within DeltaPosLimit of the target pos.
                DeltaPos = 90.
                DeltaPosLimit = 5.0
                SlewRepeat = 0
                while DeltaPos > DeltaPosLimit:
                    logger.info('Slewing to the optimally flat part of the sky (alt=' + str(Alt) + ', az=' + str(Az) + ')')
                    telescope.mountGotoAltAz(Alt,Az)

                    if NotFirstImage == 0:
                        if telescope.inPosition():
                            logger.info("Finished slew to alt=" + str(Alt) + ', az=' + str(Az) + ')')
                            NotFirstImage = 1
                        else:
                            logger.error("Slew failed to alt=" + str(Alt) + ', az=' + str(Az) + ')')
                            # now what?  
                    else:
                        time.sleep(10)

                    telescopeStatus = telescope.getStatus()
                    ActualAz = float(telescopeStatus.mount.azm_radian)*(180./3.14159265358979626)
                    ActualAlt = float(telescopeStatus.mount.alt_radian)*(180./3.14159265358979626)
                    DeltaPos = math.sqrt((Alt-ActualAlt)**2.+(Az-ActualAz)**2.)
                    if DeltaPos > DeltaPosLimit:
                        logger.error("Telescope reports it is more than " + str(DeltaPos) + " deg. away from the target postion. Reslewing...") 
                        SlewRepeat += 1
                    if SlewRepeat>10:
                        logger.error("Repeated slewing is not getting us to the flat-field target position; skipping.")
                        break

                            
                # Take flat fields
                filename = takeImage(site, aqawan, telescope, imager, exptime, filterInd, 'SkyFlat')
                
                # determine the mode of the image (mode requires scipy, use mean for now...)
                mode = getMode(filename)
                logger.info("image " + str(i+1) + " of " + str(num) + " in filter " + filterInd + "; " + filename + ": mode = " + str(mode) + " exptime = " + str(exptime) + " sunalt = " + str(site.sunalt()))

                # if way too many counts, it can roll over and look dark
                supersaturated = isSupersaturated(filename)
                
                if mode > saturation or supersaturated:
                    # Too much signal
                    logger.info("Flat deleted: exptime=" + str(exptime) + " Mode=" + str(mode) +
                                '; sun altitude=' + str(site.sunalt()) +
                                 "; exptime=" + str(exptime) + '; filter = ' + filterInd)
                    os.remove(filename)
                    i-=1
                    if exptime == minExpTime and morning:
                        logger.info("Exposure time at minimum, image saturated, and getting brighter; skipping remaining exposures in filter " + filterInd)
                        break
                elif mode < 6.0*biasLevel:
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
                if supersaturated:
                    exptime = minExpTime
                elif mode-biasLevel <= 0:
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

    if target['name'] == 'autofocus':
        try:
            telescope.acquireTarget(target['ra'],target['dec'],pa=pa)
        except:
            pass
        telescope.autoFocus()
        return

    # get the desired position angle (if none specified, don't move rotator)
    #if positionAngle in target.keys():
    #    pa = target['positionAngle']
    #else: pa = None
    pa = None
    
    # slew to the target    
    telescope.acquireTarget(target['ra'],target['dec'],pa=pa)

    newfocus = telescope.focus + target['defocus']*1000.0
    status = telescope.getStatus()
    if newfocus <> status.focuser.position:
        logger.info("Defocusing Telescope by " + str(target['defocus']) + ' mm, to ' + str(newfocus))
        telescope.focuserMove(newfocus)

    status = telescope.getStatus()
    while status.focuser.moving == 'True':
        logger.info('Focuser moving (' + str(status.focuser.position) + ')')
        time.sleep(0.3)
        status = telescope.getStatus()

    reference=None

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
                    filename = takeImage(site, aqawan, telescope, imager, target['exptime'][j], target['filter'][j], target['name'])
                    if target['selfguide']:
                        reference = guide(filename, reference)
                
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
                filename = takeImage(site, aqawan, telescope, imager, target['exptime'][j], target['filter'][j], target['name'])
                if target['selfguide']:
                    reference = guide(filename, reference)

def scheduleIsValid(targetFile):

    if not os.path.exists(targetFile):
        logger.error('No schedule file: ' + targetFile)
        mail.send("No schedule file: " + targetFile,"Cannot observe!",level='serious')
        return False

    emailbody = ''
    with open(targetFile, 'r') as targetfile:
        linenum = 1
        line = targetfile.readline()
        CalibInfo = parseCalib(line)
   	# check for malformed JSON code
        if CalibInfo == -1:
            logger.error('Line ' + str(linenum) + ': malformed JSON: ' + line)
            emailbody = emailbody + 'Line ' + str(linenum) + ': malformed JSON: ' + line + '\n'
        else:
            requiredKeys = ['nbias','ndark','nflat','darkexptime','flatFilters','WaitForMorning']
            for key in requiredKeys:
                if key not in CalibInfo.keys():
                    logger.error('Line 1: Required key (' + key + ') not present: ' + line)
                    emailbody = emailbody + 'Line 1: Required key (' + key + ') not present: ' + line + '\n'

        linenum = 2
        line = targetfile.readline()
    	CalibEndInfo = parseCalib(line)
    	# check for malformed JSON code
        if CalibEndInfo == -1:
            logger.error('Line ' + str(linenum) + ': malformed JSON: ' + line)
            emailbody = emailbody + 'Line ' + str(linenum) + ': malformed JSON: ' + line + '\n'
        else:
            requiredKeys = ['nbiasEnd','ndarkEnd','nflatEnd']
            for key in requiredKeys:
                if key not in CalibEndInfo.keys():
                    logger.error('Line 2: Required key (' + key + ') not present: ' + line)
                    emailbody = emailbody + 'Line 2: Required key (' + key + ') not present: ' + line + '\n'

        linenum = 3
        for line in targetfile:
            target = parseTarget(line)

            # check for malformed JSON code
            if target == -1:
                logger.error('Line ' + str(linenum) + ': malformed JSON: ' + line)
                emailbody = emailbody + 'Line ' + str(linenum) + ': malformed JSON: ' + line + '\n'
            else:
                # check to make sure all required keys are present
                key = 'name'
                if key not in target.keys():
                    logger.error('Line ' + str(linenum) + ': Required key (' + key + ') not present: ' + line)
                    emailbody = emailbody + 'Line ' + str(linenum) + ': Required key (' + key + ') not present: ' + line + '\n'
                else:
                    if target['name'] == 'autofocus':
                        requiredKeys = ['starttime','endtime']
                    else:
                        requiredKeys = ['starttime','endtime','ra','dec','filter','num','exptime','defocus','selfguide','guide','cycleFilter']

                    for key in requiredKeys:
                        if key not in target.keys():
                            logger.error('Line ' + str(linenum) + ': Required key (' + key + ') not present: ' + line)
                            emailbody = emailbody + 'Line ' + str(linenum) + ': Required key (' + key + ') not present: ' + line + '\n'

                    if target['name'] <> 'autofocus':
                        try:
                            nnum = len(target['num'])
                            nexptime = len(target['exptime'])
                            nfilter = len(target['filter'])
                            if nnum <> nexptime or nnum <> nfilter:
                                logger.error('Line ' + str(linenum) + ': Array size for num (' + str(nnum) + '), exptime (' + str(nexptime) + '), and filter (' + str(nfilter) + ') must agree')
                                emailbody = emailbody + 'Line ' + str(linenum) + ': Array size for num (' + str(nnum) + '), exptime (' + str(nexptime) + '), and filter (' + str(nfilter) + ') must agree\n'                            
                        except:
                            ipdb.set_trace()
                            pass            
            linenum = linenum + 1
            if emailbody <> '':
                mail.send("Errors in target file: " + targetFile,emailbody,level='serious')
                return False
    return True
            
if __name__ == '__main__':

    # this file is created at the beginning and deleted at the end
    # to enable automatic recovery
    with open('running.txt','w') as f:
        f.write(str(datetime.datetime.utcnow()))

    site, aqawan, telescope, imager = prepNight()

    # setting up main logger
    fmt = "%(asctime)s [%(filename)s:%(lineno)s - %(funcName)s()] %(levelname)s: %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S"

#    logging.basicConfig(level=logging.DEBUG, format=fmt, datefmt=datefmt)
    logger = logging.getLogger('main')
    formatter = logging.Formatter(fmt,datefmt=datefmt)
    formatter.converter = time.gmtime
        
    fileHandler = logging.FileHandler('logs/' + site.night + '/main.log', mode='a')
    fileHandler.setFormatter(formatter)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.setLevel(logging.INFO)
        
    logger.setLevel(logging.DEBUG)
    logger.addHandler(fileHandler)
    logger.addHandler(console)

    # verify the schedule file
    if not scheduleIsValid('schedule/' + site.night + '.txt'):
        logger.error("schedule file not valid; exiting")
        sys.exit()

    # run the aqawan heartbeat and weather checking asynchronously
    aqawanThread = threading.Thread(target=heartbeat, args=(site, aqawan), kwargs={})
    aqawanThread.start()

    if datetime.datetime.utcnow() > site.NautTwilBegin():
        cooler = False
    else: cooler = True
    imager.connect(cooler=cooler)
    telescope.initialize()

    # Open the target file and read the first line for calibration info
    # then close the file
    with open('schedule/' + site.night + '.txt', 'r') as calibfile:
        calibline1 = calibfile.readline()
        CalibInfo = parseCalib(calibline1)
        calibline2 = calibfile.readline()
    	CalibEndInfo = parseCalib(calibline2)
    	
    # wait until it's darker to take biases/darks
    readtime = 10.0

    biastime = site.sunset() - datetime.timedelta(seconds=CalibInfo['nbias']*readtime+CalibInfo['ndark']*sum(CalibInfo['darkexptime']) + CalibInfo['ndark']*readtime*len(CalibInfo['darkexptime']) + 600.0)
    waittime = (biastime - datetime.datetime.utcnow()).total_seconds()
    if waittime > 0:
    	# Take biases and darks (skip if we don't have time before twilight)
    	logger.info('Waiting until darker before biases/darks (' + str(waittime) + ' seconds)')
    	time.sleep(waittime)
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
    while response == -1 and datetime.datetime.utcnow() < site.NautTwilBegin():
        response = aqawanOpen(site, aqawan)
        if response == -1: time.sleep(60)
    if response <> -1: logger.info('Dome open')
    #ipdb.set_trace() # stop execution until we type 'cont' so we can keep the dome open 

    flatFilters = CalibInfo['flatFilters']

    # Take Evening Sky flats
    logger.info('Beginning sky flats')
    doSkyFlat(site, aqawan, telescope, imager, flatFilters, num=CalibInfo['nflat'])
   
    # Wait until nautical twilight ends 
    timeUntilTwilEnd = (site.NautTwilEnd() - datetime.datetime.utcnow()).total_seconds()
    if timeUntilTwilEnd > 0:
        logger.info('Waiting for nautical twilight to end (' + str(timeUntilTwilEnd) + 'seconds)')
        time.sleep(timeUntilTwilEnd)

    # find the best focus for the night
    if datetime.datetime.utcnow() < site.NautTwilBegin():
        logger.info('Beginning autofocus')
        telescope.autoFocus()

    # read the target list
    with open('./schedule/' + site.night + '.txt', 'r') as targetfile:
        next(targetfile) # skip the calibration headers
        next(targetfile) # skip the calibration headers
        for line in targetfile:
            target = parseTarget(line)
            if target <> -1:
                # check if the end is after morning twilight begins
                if target['endtime'] > site.NautTwilBegin(): 
                    target['endtime'] = site.NautTwilBegin()
                # check if the start is after evening twilight ends
                if target['starttime'] < site.NautTwilEnd(): 
                    target['starttime'] = site.NautTwilEnd()

                # compute the rise/set times of the target
                site.obs.horizon = '20.0'
                body = ephem.FixedBody()
                body._ra = str(target['ra'])
                body._dec = str(target['dec'])
                body._epoch = '2000.0'
                body.compute()
                try:
                    risetime = site.obs.next_rising(body,start=site.NautTwilEnd()).datetime()
                except AlwaysUpError:
                    # if it's always up, don't modify the start time
                    risetime = target['starttime']
                except NeverUpError:
                    # if it's never up, skip the target
                    risetime = target['endtime']
                try:
                    settime = site.obs.next_setting(body,start=site.NautTwilEnd()).datetime()
                except AlwaysUpError:
                    # if it's always up, don't modify the end time
                    settime = target['endtime']
                except NeverUpError:
                    # if it's never up, skip the target
                    settime = target['starttime']

                if risetime > settime:
                    try:
                        risetime = site.obs.next_rising(body,start=site.NautTwilEnd()-datetime.timedelta(days=1)).datetime()
                    except AlwaysUpError:
                        # if it's always up, don't modify the start time
                        risetime = target['starttime']
                    except NeverUpError:
                        # if it's never up, skip the target
                        risetime = target['endtime']
                    
                # make sure the target is always above the horizon
                if target['starttime'] < risetime:
                    target['starttime'] = risetime
                if target['endtime'] > settime:
                    target['endtime'] = settime

                if target['starttime'] < target['endtime']:
                    doScience(site, aqawan, telescope, imager, target)
                else:
                    logger.info(target['name']+ ' not observable; skipping')

    # Take Morning Sky flats
    # Check if we want to wait for these
    if CalibInfo['WaitForMorning']:
        sleeptime = (site.NautTwilBegin() - datetime.datetime.utcnow()).total_seconds()
        if sleeptime > 0:
            logger.info('Waiting for morning flats (' + str(sleeptime) + ' seconds)')
            time.sleep(sleeptime)
    	doSkyFlat(site, aqawan, telescope, imager, flatFilters, num=CalibEndInfo['nflatEnd'], morning=True)

    # Want to close the aqawan before darks and biases
    # closeAqawan in endNight just a double check
    telescope.park()
    aqawan.close_both()

    # Take biases and darks
    if CalibEndInfo['nbiasEnd'] <> 0 or CalibEndInfo['ndarkEnd']:
        imager.connect() # make sure the cooler is on
    doBias(site, aqawan, telescope, imager, num=CalibEndInfo['nbiasEnd'])
    doDark(site, aqawan, telescope, imager, num=CalibEndInfo['ndarkEnd'], exptime=CalibInfo['darkexptime'])

    endNight(site, aqawan, telescope, imager)
    
    # Stop the aqawan thread
    site.observing = False

    if os.path.exists('running.txt'):
        os.remove('running.txt')
    
    
