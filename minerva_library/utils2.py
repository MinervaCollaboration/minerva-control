# this file contains a set of generally useful utility functions for MINERVA operations
import re
import subprocess, psutil, os, signal
from astropy.io import fits as pyfits
import numpy as np
import ephem
import datetime, time
import ipdb
import logging
import unicodecsv
import json
import mail
from astropy.stats import sigma_clipped_stats
import scipy
#from photutils import DAOStarFinder
#from photutils import centroid_com
from get_all_centroids import threshold_pyguide, centroid_brightest_blob, centroid_all_blobs

def get_stars_cv(image, filename=None):
    if filename != None:
        image = pyfits.getdata(filename)

    d = np.array(image, dtype='float')
    th = threshold_pyguide(d, level = 4)

    # all zero image
    if np.max(image*th) == 0.0:
        return []

    imtofeed = np.array(np.round((d*th)/np.max(d*th)*255), dtype='uint8')
    return centroid_all_blobs(imtofeed)

def get_stars_com(image,filename=None,logger=None):
    if filename != None:
        image = pyfits.getdata(filename)

    xy = get_stars_cv(image,filename=filename)
        
    xsize = image.shape[1]
    ysize = image.shape[0]
    boxsize = 8
    x1 = int(round(xsize/2.0-boxsize/2.0))
    x2 = int(round(xsize/2.0+boxsize/2.0))
    y1 = int(round(ysize/2.0-boxsize/2.0))
    y2 = int(round(ysize/2.0+boxsize/2.0))
    bkg = np.average(image[y1:y2,x1:x2])
    if logger != None: logger.info("background is " + str(bkg))

    data_sub = image - bkg

    # if not above threshold, return nothing
    rms = np.std(data_sub)

    threshold = 10
    n_high_pixels = len(data_sub[data_sub > (threshold*rms)])
    if logger != None: 
        logger.info("background rms is " + str(rms) + '. ' +\
                        str(n_high_pixels) +\
                        ' pixels above ' + str(threshold) + "*rms")

    # this is just for future reference and can be deleted to save time during the guide loop
    total_counts = np.sum(data_sub)
    if logger != None: 
        logger.info("total counts after subtracting background is " + str(total_counts))

    minarea = 10
    if n_high_pixels < minarea:
        if logger != None: logger.info("too few pixels above threshold (< " + str(minarea) + "), no star detected")
        return []

    # if not above threshold, return nothing
    threshold = 1000
    if total_counts < threshold:
        if logger != None: logger.info("too few total counts (< " + str(threshold) + "), no star detected")
        return []

    # compute the center of mass
    ycom,xcom = scipy.ndimage.measurements.center_of_mass(data_sub)
    if logger != None: logger.info("xcom=" + str(xcom) + " ycom=" + str(ycom))
    if xcom < 0 or xcom > data_sub.shape[1] or ycom < 0 or ycom > data_sub.shape[0]:
        if logger != None: logger.info("Center of mass outside of image. No star detected")
        return []

    return(np.transpose(np.vstack((xcom+1,ycom+1,total_counts))))


def get_stars_brightest(image, filename=None):

    if filename != None:
        image = pyfits.getdata(filename)

    xc0 = np.where(np.amax(np.sum(image,axis=0)) ==  np.sum(image,axis=0))
    yc0 = np.where(np.amax(np.sum(image,axis=1)) ==  np.sum(image,axis=1))
    xc = xc0[0][0]+1
    yc = yc0[0][0]+1

    # make sure we have a detection
    boxsize = 50
    xmin = xc - boxsize
    xmax = xc + boxsize
    ymin = yc - boxsize
    ymax = yc + boxsize
    mean, median, std = sigma_clipped_stats(image[xmin:xmax,ymin:ymax], sigma = 3.0)
    try:
        if np.max(image[xmin:xmax,ymin:ymax]) > 10.0*std:
            return np.transpose(np.vstack((xc, yc, 1)))
            #return [[xc],[yc],[1]]
    except:
        return []
    return []

# only works on linux
def get_stars_sex(image, filename=None):
    
    filename = 'C:/minerva/data/n20200206/n20200206.MRED.FAU.backlight.0001.fits'

    t0 = datetime.datetime.utcnow()
    catname = sextract('',filename,sexfile='backlight.sex')
    #print "extracted stars in " + str((datetime.datetime.utcnow() - t0).total_seconds()) + ' seconds'
    cat = readsexcat(catname)
    #print "read catalog in " + str((datetime.datetime.utcnow() - t0).total_seconds()) + ' seconds'

    ipdb.set_trace()

def get_stars_dao(image, filename=None):
    if filename != None:
        image = pyfits.getdata(filename)
#    t0 = datetime.datetime.utcnow()
    stars = get_stars_brightest(image)
    if len(stars) < 1: return []
    xc = stars[0,0]
    yc = stars[0,1]

    boxsize = 50
    xmin = xc - boxsize
    xmax = xc + boxsize
    ymin = yc - boxsize
    ymax = yc + boxsize
    mean, median, std = sigma_clipped_stats(image[ymin:ymax,xmin:xmax], sigma = 3.0)
#    print "image stats in " + str((datetime.datetime.utcnow() - t0).total_seconds()) + ' seconds'
    return []
    daofind = DAOStarFinder(fwhm=4.0, threshold=10.0*std, ratio=0.3)
    sources = daofind(image[ymin:ymax,xmin:xmax] - median)
#    sources = daofind(image - median)

    if len(sources) == 0:
        return []

#    print "extracted stars in " + str((datetime.datetime.utcnow() - t0).total_seconds()) + ' seconds'
#    ipdb.set_trace()
    stars = np.vstack((sources['xcentroid']+xmin, sources['ycentroid']+ymin, sources['flux'])).T
    #stars = np.vstack((sources['xcentroid'], sources['ycentroid'], sources['flux'])).T
    #print stars, stars.T
    return stars

# this kills main.py if running (use before runninging to ensure a clean start)
def killmain(red=False,south=False):
    for pid in psutil.pids():
        p = psutil.Process(pid)
        if p.name() == "python" and pid != os.getpid():
            if len(p.cmdline()) > 1:
                if (p.cmdline())[1] == 'mainNew.py' or (p.cmdline())[1] == 'main.py' or (p.cmdline())[1] == 'daytimespec.py' :
                    if len(p.cmdline()) == 3:
                        if (p.cmdline())[2] == '--red' and red:
                            # kill main.py --red
                            os.kill(pid, signal.SIGKILL)
                        elif (p.cmdline())[2] == '--south' and south:
                            # kill main.py --south
                            os.kill(pid, signal.SIGKILL)    
                    else:
                        # kill main.py
                        if not red and not south:
                            os.kill(pid, signal.SIGKILL)    

def dateobs2jd(dateobs):
    t0 = datetime.datetime(2000,1,1)
    t0jd = 2451544.5
    ti = datetime.datetime.strptime(dateobs,"%Y-%m-%dT%H:%M:%S.%f")
    return t0jd + (ti-t0).total_seconds()/86400.0

def findBrightest(imageName):
    catname = sextract('',imageName)
    cat = readsexcat(catname)
    try: brightest = np.argmax(cat['FLUX_ISO'])
    except: return None,None
    
    try:
        x = cat['XWIN_IMAGE'][brightest]
        y = cat['YWIN_IMAGE'][brightest]
        return x,y
    except:
        return None, None


# reads a CSV into a dictionary; the header line becomes the keys for lists
def readcsv(filename):
    # parse the CSV file                                                                                    
    with open(filename,'rb') as f:
        reader = unicodecsv.reader(f)
        headers = reader.next()
        csv = {}
        for h in headers:
            csv[h.split('(')[0].strip()] = []
        for row in reader:
            for h,v in zip(headers,row):
                csv[h.split('(')[0].strip()].append(v)
        for key in csv.keys():
            try: csv[key] = np.asarray(csv[key],dtype=np.float32)
            except: csv[key] = np.asarray(csv[key])
        return csv

def brightStars(filename='bsc.csv',path='/home/minerva/minerva-control/dependencies/',maxmag=6.0):
#def brightStars(filename='brightstars2.csv',path='/home/minerva/minerva-control/dependencies/',maxmag=6.0):
    brightstars = readcsv(path+filename)
    brightest = np.where(brightstars['vmag'] <= maxmag)
    for key in brightstars.keys():
        brightstars[key] = brightstars[key][brightest]

    '''
    # cut out high proper motion stars
    pm = np.sqrt(np.power(brightstars['pmra'],2) + np.power(brightstars['pmdec'],2) )
    lowmu = np.where(pm <= 100)
    for key in brightstars.keys():
        brightstars[key] = brightstars[key][lowmu]
    '''

    return brightstars

def parseTarget(line, logger=None):
    try:
        target = json.loads(line)
    except ValueError:
        if logger == None:
            print 'Not a valid JSON line: ' + line
        else:
            logger.error('Not a valid JSON line: ' + line)
        return -1

    # convert strings to datetime objects
    target['starttime'] = datetime.datetime.strptime(target['starttime'],'%Y-%m-%d %H:%M:%S')
    target['endtime'] = datetime.datetime.strptime(target['endtime'],'%Y-%m-%d %H:%M:%S')
    return target

def scheduleIsValid(scheduleFile, email=True, logger=None, directory=None):
    if not os.path.exists(scheduleFile):
        if logger != None: 
            logger.error('No schedule file: ' + scheduleFile)
        else: 
            print 'No schedule file: ' + scheduleFile
        return False

    emailbody = ''
    with open(scheduleFile, 'r') as targetfile:
        linenum = 1
        line = targetfile.readline()
        try: CalibInfo = json.loads(line)
        except: CalibInfo = -1

        # check for malformed JSON code
        if CalibInfo == -1:
            if logger != None: logger.error('Line ' + str(linenum) + ': malformed JSON: ' + line)
            emailbody = emailbody + 'Line ' + str(linenum) + ': malformed JSON: ' + line + '\n'
        else:
            requiredKeys = ['nbias','ndark','nflat','darkexptime','flatFilters','WaitForMorning']
            for key in requiredKeys:
                if key not in CalibInfo.keys():
                    if logger != None: logger.error('Line 1: Required key (' + key + ') not present: ' + line)
                    emailbody = emailbody + 'Line 1: Required key (' + key + ') not present: ' + line + '\n'

        linenum = 2
        line = targetfile.readline()
        try: CalibEndInfo = json.loads(line)
        except: CalibEndInfo = -1

        # check for malformed JSON code
        if CalibEndInfo == -1:
            if logger != None: logger.error('Line ' + str(linenum) + ': malformed JSON: ' + line)
            emailbody = emailbody + 'Line ' + str(linenum) + ': malformed JSON: ' + line + '\n'
        else:
            requiredKeys = ['nbiasEnd','ndarkEnd','nflatEnd']
            for key in requiredKeys:
                if key not in CalibEndInfo.keys():
                    if logger != None: logger.error('Line 2: Required key (' + key + ') not present: ' + line)
                    emailbody = emailbody + 'Line 2: Required key (' + key + ') not present: ' + line + '\n'

        linenum = 3
        for line in targetfile:
            target = parseTarget(line)
            
            # check for malformed JSON code
            if target == -1:
                if logger != None: logger.error('Line ' + str(linenum) + ': malformed JSON: ' + line)
                emailbody = emailbody + 'Line ' + str(linenum) + ': malformed JSON: ' + line + '\n'
            else:
                # check to make sure all required keys are present  
                key = 'name'
                if key not in target.keys():
                    if logger != None: logger.error('Line ' + str(linenum) + ': Required key (' + key + ') not present: ' + line)
                    emailbody = emailbody + 'Line ' + str(linenum) + ': Required key (' + key + ') not present: ' + line + '\n'
                else:
                    if target['name'] == 'autofocus':
                        requiredKeys = ['starttime','endtime']
                    else:
                        requiredKeys = ['starttime','endtime','ra','dec','filter','num','exptime','defocus','selfguide','guide','cycleFilter']

                    for key in requiredKeys:
                        if key not in target.keys():
                            if logger != None: logger.error('Line ' + str(linenum) + ': Required key (' + key + ') not present: ' + line)
                            emailbody = emailbody + 'Line ' + str(linenum) + ': Required key (' + key + ') not present: ' + line + '\n'
                            
                    if target['name'] <> 'autofocus':
                        try:
                            nnum = len(target['num'])
                            nexptime = len(target['exptime'])
                            nfilter = len(target['filter'])
                            if nnum <> nexptime or nnum <> nfilter:
                                if logger != None: logger.error('Line ' + str(linenum) + ': Array size for num (' + str(nnum) + '), exptime (' + str(nexptime) + '), and filter (' + str(nfilter) + ') must agree')
                                emailbody = emailbody + 'Line ' + str(linenum) + ': Array size for num (' + str(nnum) + '), exptime (' + str(nexptime) + '), and filter (' + str(nfilter) + ') must agree\n'                   \
                                    
                        except:
                            pass
                        try: 
                            if target['ra'] > 24.0 or target['ra'] < 0:
                                if logger != None: logger.error('Line ' + str(linenum) + ': RA (' + str(target['ra']) + ') must be in decimal hours (0 < RA < 24)')
                                emailbody = emailbody + 'Line ' + str(linenum) + ': RA (' + str(target['ra']) + ') must be in decimal hours (0 < RA < 24)\n'
                        except: pass
                        try: 
                            if target['dec'] > 90.0 or target['dec'] < -90:
                                if logger != None: logger.error('Line ' + str(linenum) + ': Dec (' + str(target['dec']) + ') must be in decimal degrees (-90 < RA < 90)')
                                emailbody = emailbody + 'Line ' + str(linenum) + ': Dec (' + str(target['dec']) + ') must be in decimal degrees (-90 < RA < 90)\n'
                        except: pass
                        
            linenum = linenum + 1
            if emailbody <> '':
                if email: mail.send("Errors in target file: " + scheduleFile,emailbody,level='serious',directory=directory)
                return False
    return True




# gets the telescope object (by reference) corresponding to a particular telescope number
def getTelescope(minerva, telid):

    for telescope in minerva.telescopes:
        if telescope.num == str(telid) or telescope.id == str(telid):
            return telescope
    return False

# gets the camera object (by reference) corresponding to a particular telescope number
def getCamera(minerva, telid):

    for camera in minerva.cameras:
        if camera.telnum == str(telid) or camera.telid == str(telid):
            return camera
    return False

# gets the dome object (by reference) corresponding to a particular telescope number
def getDome(minerva, telnum):
    
    # this is a hack and should be done better
    if telnum == 5 or telnum == 'MRED': 
        dome = minerva.domes[0]
        return dome

    if telnum == 'T1' or telnum == 'T2':
        domenum = 1
    elif telnum == 'T3' or telnum == 'T4':
        domenum = 2
    elif float(telnum) < 1:
        return False
    elif float(telnum) <= 2:
        domenum = 1
    elif float(telnum) <= 4:
        domenum = 2
    else: return False

    for dome in minerva.domes:
        if dome.num == str(domenum):
            return dome

    return False


def night():
    today = datetime.datetime.utcnow()
    if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
        today = today + datetime.timedelta(days=1)
    return 'n' + today.strftime('%Y%m%d')

def update_logger_path(logger, newpath):
    fmt = "%(asctime)s.%(msecs).03d [%(filename)s:%(lineno)s - %(funcName)s()] %(levelname)s: %(threadName)s: %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S"
    formatter = logging.Formatter(fmt,datefmt=datefmt)
    formatter.converter = time.gmtime

    for fh in logger.handlers: logger.removeHandler(fh)
    fh = logging.FileHandler(newpath, mode='a')
    fh.setFormatter(formatter)
    logger.addHandler(fh)

def setup_logger(base_dir, night, logger_name):

    path = base_dir + '/log/' + night

    if os.path.exists(path) == False:os.mkdir(path)
    fmt = "%(asctime)s.%(msecs).03d [%(filename)s:%(lineno)s - %(funcName)s()] %(levelname)s: %(threadName)s: %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S"

    logger = logging.getLogger(logger_name)
    formatter = logging.Formatter(fmt,datefmt=datefmt)
    formatter.converter = time.gmtime

    fileHandler = logging.FileHandler(path + '/' + logger_name + '.log', mode='a')
    fileHandler.setFormatter(formatter)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.setLevel(logging.INFO)

    # add a separate logger for the terminal (don't display debug-level messages)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(fileHandler)
    logger.addHandler(console)

    return logger

# Truncates target['starttime'] and target['endtime'] to ensure 
# the object is observable (Sun below sunalt and target above horizon)
def truncate_observable_window(site,target,sunalt=-12.0,horizon=21.0,timeof=None,logger=None):

    if timeof == None: timeof = datetime.datetime.utcnow()

    sunset = site.sunset(horizon=sunalt, start=timeof)
    sunrise = site.sunrise(horizon=sunalt, start=timeof)

    niter = 0
    while sunrise < timeof and niter < 100:
        sunrise = site.sunrise(horizon=sunalt, start=timeof + datetime.timedelta(days=0.1*niter))
        niter += 1
    if sunrise < timeof:
        if logger <> None: logger.error("Error calculating nearest sunrise")
        return

    niter = 0
    while sunset > sunrise and niter < 100:
        sunset = site.sunset(horizon=sunalt, start=timeof - datetime.timedelta(days=0.1*niter))
        niter += 1
    if sunset > sunrise:
        if logger <> None: logger.error("Error calculating nearest sunset")
        return
        
    site.obs.horizon = str(horizon)
    body = ephem.FixedBody()
    body._ra = ephem.hours(str(target['ra']))
    body._dec = ephem.degrees(str(target['dec']))

    #S UTC vs local time not right for epoch, but not significant
    body._epoch = timeof#datetime.datetime.utcnow()
    body.compute()

    # calculate the object's rise time
    try:
        risetime = site.obs.next_rising(body,start=sunset).datetime()
    except ephem.AlwaysUpError:
        # if it's always up, we can observe at sunset
        risetime = sunset
    except ephem.NeverUpError:
        # if it's never up, skip the target
        risetime = sunrise

    # calculate the object's set time
    try:
        settime = site.obs.next_setting(body,start=sunset).datetime()
    except ephem.AlwaysUpError:
        # if it's always up, we can observe until sunrise
        settime = sunrise
    except ephem.NeverUpError:
        # if it's never up, skip the target
        settime = sunset

    # if it rises before it sets, redo with the previous day
    niter = 0
    while risetime > settime and niter < 100:
        try:
            risetime = site.obs.next_rising(body,start=sunset - datetime.timedelta(days=0.1*niter)).datetime()
        except ephem.AlwaysUpError:
            # if it's always up, don't modify the start time
            risetime = sunset
        except ephem.NeverUpError:
            # if it's never up, skip the target
            risetime = sunrise
        niter += 1

    if risetime > settime:
        if logger <> None: logger.error("Error calculating nearest sunset")
        return

    # the start time should be the later of the requested start time, when the target rises, or when the sun sets
    starttime = max(target['starttime'],risetime,sunset) 

    # the end time should be the earlier of the requested end time, when the target sets, or when the sun rises
    endtime = min(target['endtime'],sunrise,settime)

    if logger <> None:
        logger.info('Time of calculation is ' + str(timeof))
        logger.info('Target start time is ' + str(target['starttime']))
        logger.info('Target rise time is ' + str(risetime))
        logger.info('The new start time is ' + str(starttime))
        logger.info('Sun set time is '  + str(sunset))
        logger.info('Target end time is ' + str(target['endtime']))
        logger.info('Target set time is '  + str(settime))
        logger.info('Sun rise time is '  + str(sunrise))
        logger.info('The new end time is ' + str(endtime))   

    target['starttime'] = starttime
    target['endtime'] = endtime

    return target

# converts a sexigesimal string to a float
# the string may be delimited by either spaces or colons
def ten(string):
    array = re.split(' |:',string)
    if "-" in array[0]:
        return float(array[0]) - float(array[1])/60.0 - float(array[2])/3600.0
    return float(array[0]) + float(array[1])/60.0 + float(array[2])/3600.0

# run astrometry.net on imageName, update solution in header
def astrometry(imageName, rakey='RA', deckey='DEC',pixscalekey='PIXSCALE', pixscale=None, nopositionlimit=False, noquadlimit=False):
    hdr = pyfits.getheader(imageName)

    try:
        if pixscale == None:
            pixscale = float(hdr[pixscalekey])
    except:
        return False

    try: ra = float(hdr[rakey])
    except: ra = ten(hdr[rakey])*15.0
    
    try: dec = float(hdr[deckey])
    except: dec = ten(hdr[deckey])
    if dec > 90.0: dec = dec - 360.0
    
    radius = 3.0*pixscale*float(hdr['NAXIS1'])/3600.0
    
    cmd = 'solve-field --scale-units arcsecperpix' + \
        ' --scale-low ' + str(0.99*pixscale) + \
        ' --scale-high ' + str(1.01*pixscale)

    if not nopositionlimit:
        cmd += ' --ra ' + str(ra) + \
            ' --dec ' + str(dec) + \
            ' --radius ' + str(radius)
    if not noquadlimit:
        cmd += ' --quad-size-min 0.4' + \
            ' --quad-size-max 0.6'
    cmd += ' --cpulimit 30' + \
        ' --no-verify' + \
        ' --crpix-center' + \
        ' --no-fits2fits' + \
        ' --no-plots' + \
        ' --overwrite ' + \
        imageName
#        ' --use-sextractor' + \ #need to install sextractor
#        ' --quad-size-min 0.4' + \
#        ' --quad-size-max 0.6' + \

    cmd = r'/usr/local/astrometry/bin/' + cmd + ' >/dev/null 2>&1'
    os.system(cmd)
    
    baseName = os.path.splitext(imageName)[0]
    f = pyfits.open(imageName, mode='update')
    if os.path.exists(baseName + '.new'):
      
        # preserve original solution
        orighdr = pyfits.getheader(imageName)
        f[0].header['WCD1_1'] = float(f[0].header['CD1_1'])
        f[0].header['WCD1_2'] = float(f[0].header['CD1_2'])
        f[0].header['WCD2_1'] = float(f[0].header['CD2_1'])
        f[0].header['WCD2_2'] = float(f[0].header['CD2_2'])
        f[0].header['WCRVAL1'] = float(f[0].header['CRVAL1'])
        f[0].header['WCRVAL2'] = float(f[0].header['CRVAL2'])

        # copy the WCS solution to the file
        newhdr = pyfits.getheader(baseName + '.new')
        f[0].header['WCSSOLVE'] = 'True'
        f[0].header['WCSAXES'] = newhdr['WCSAXES']
        f[0].header['CTYPE1'] = newhdr['CTYPE1']
        f[0].header['CTYPE2'] = newhdr['CTYPE2']
        f[0].header['EQUINOX'] = newhdr['EQUINOX']
        f[0].header['LONPOLE'] = newhdr['LONPOLE']
        f[0].header['LATPOLE'] = newhdr['LATPOLE']
        f[0].header['CRVAL1'] = newhdr['CRVAL1']
        f[0].header['CRVAL2'] = newhdr['CRVAL2']
        f[0].header['CRPIX1'] = newhdr['CRPIX1']
        f[0].header['CRPIX2'] = newhdr['CRPIX2']
        f[0].header['CUNIT1'] = newhdr['CUNIT1']
        f[0].header['CUNIT2'] = newhdr['CUNIT2']
        f[0].header['CD1_1'] = newhdr['CD1_1']
        f[0].header['CD1_2'] = newhdr['CD1_2']
        f[0].header['CD2_1'] = newhdr['CD2_1']
        f[0].header['CD2_2'] = newhdr['CD2_2']
        f[0].header['IMAGEW'] = newhdr['IMAGEW']
        f[0].header['IMAGEH'] = newhdr['IMAGEH']
        f[0].header['A_ORDER'] = newhdr['A_ORDER']
        f[0].header['A_0_2'] = newhdr['A_0_2']
        f[0].header['A_1_1'] = newhdr['A_1_1']
        f[0].header['A_2_0'] = newhdr['A_2_0']
        f[0].header['B_ORDER'] = newhdr['B_ORDER']
        f[0].header['B_0_2'] = newhdr['B_0_2']
        f[0].header['B_1_1'] = newhdr['B_1_1']
        f[0].header['B_2_0'] = newhdr['B_2_0']
        f[0].header['AP_ORDER'] = newhdr['AP_ORDER']
        f[0].header['AP_0_1'] = newhdr['AP_0_1']
        f[0].header['AP_0_2'] = newhdr['AP_0_2']
        f[0].header['AP_1_0'] = newhdr['AP_1_0']
        f[0].header['AP_1_1'] = newhdr['AP_1_1']
        f[0].header['AP_2_0'] = newhdr['AP_2_0']
        f[0].header['BP_ORDER'] = newhdr['BP_ORDER']
        f[0].header['BP_0_1'] = newhdr['BP_0_1']
        f[0].header['BP_0_2'] = newhdr['BP_0_2']
        f[0].header['BP_1_0'] = newhdr['BP_1_0']
        f[0].header['BP_1_1'] = newhdr['BP_1_1']
        f[0].header['BP_2_0'] = newhdr['BP_2_0']
        success = True
    else:
        f[0].header['WCSSOLVE'] = 'False'
        success = False
    f.flush()
    f.close()

    # clean up extra files
    extstodelete = ['-indx.png','-indx.xyls','-ngc.png','-objs.png','.axy',
                    '.corr','.match','.new','.rdls','.solved','.wcs']
    for ext in extstodelete:
        if os.path.exists(baseName + ext):
            os.remove(baseName + ext)
        
    return success
    
# run sextractor on an image
def sextract(datapath,imagefile,sexfile='autofocus.sex',paramfile=None,convfile=None,catfile=None):
    #S Path on MinervaMAIN where all the .sex, .param, etc. files will be
    #S located
    sexpath = '/usr/share/sextractor/'

    #S This is the base command we be calling with sextractor. It has
    #S the default sexfile of autofocus.sex, which will be given some pretty
    #S general values for now.
    # We'll add on other parameters and arguements as they are specified
    sexcommand = 'sex '+datapath+imagefile+' -c ' + sexpath+sexfile
    
    #S If a paramfile was specfied, then we will use that instead of the
    #S default param file in autofocus.sex (which is autofocus.param)
    if paramfile <> None:
        sexcommand+= ' -PARAMETERS_NAME ' + sexpath+paramfile

    #S Similar to above, but the convolution filter
    if convfile <> None:
        sexcommand+= ' -FILTER_NAME ' + sexpath+convfile

    #S we're going to name the catalog after the image just by removing the
    #S fits and  adding cat. if a cat file is specified we'll use that.
    #S Datapath is the path where the image is (hopefully), but can be anywhere
    #S you want it to go.
    if catfile == None:
        catfile = imagefile.split('.fits')[0] + '.cat'
        sexcommand += ' -CATALOG_NAME ' + datapath+catfile

    #S so we a have sexcommand, which has all of its components split by
    #S spaces ideally, which will allow for just a .split to put in a list
    #S for subprocess.call
    subprocess.call(sexcommand.split())

    #S Just going to return the catalog file name for now, could return fwhm,
    #S whatever later
    return datapath+catfile

# read a generic sextractor catalog file into a dictionary
# the header values (PARAMS) become the dictionary keys
# objects are read into lists under each dictionary key
def readsexcat(catname):

    data = {}
    if not os.path.exists(catname): return data
    with open(catname,'rb') as filep:
        header = []
        for line in filep:
            # header lines begin with # and are the 3rd item in the line
            if line.startswith('#'):
                header.append(line.split()[2])
                for h in header:
                    data[h] = []
            # older sextractor catalogs contain a few nuisance lines; ignore those
            elif not line.startswith('-----') and not line.startswith('Measuring') and \
                    not line.startswith('(M+D)') and not line.startswith('Objects:'):
                # assume all values are floats
                values = [ float(x) for x in line.split() ]
                for h,v in zip(header,values):
                    data[h].append(v)
    for key in data.keys():
        #S try and convert to an np.array, and if not possible jsut pass
        #S the try is in case for some reason a non-numerical entry is 
        #S encountered. may be a l
        try:
            data[key] = np.array(data[key])
        except:
            pass

    return data
    

# this file contains a set of generally useful utility functions for MINERVA operations
import re
import subprocess, psutil, os, signal
#try:
#    import pyfits
#except:
from astropy.io import fits as pyfits
import numpy as np
import ephem
import datetime, time
import ipdb
import logging
import unicodecsv
import json
import mail
from astropy.stats import sigma_clipped_stats
#from photutils import DAOStarFinder
#from photutils import centroid_com
from get_all_centroids import threshold_pyguide, centroid_brightest_blob, centroid_all_blobs

def get_stars_cv(image, filename=None):
    if filename != None:
        image = pyfits.getdata(filename) 

    d = np.array(image, dtype='float')
    th = threshold_pyguide(d, level = 4)

    # all zero image
    if np.max(image*th) == 0.0:
        return []

    imtofeed = np.array(np.round((d*th)/np.max(d*th)*255), dtype='uint8')
    return centroid_all_blobs(imtofeed)

def get_stars_brightest(image, filename=None):

    if filename != None:
        image = pyfits.getdata(filename)

    xc0 = np.where(np.amax(np.sum(image,axis=0)) ==  np.sum(image,axis=0))
    yc0 = np.where(np.amax(np.sum(image,axis=1)) ==  np.sum(image,axis=1))
    xc = xc0[0][0]+1
    yc = yc0[0][0]+1

    # make sure we have a detection
    boxsize = 50
    xmin = xc - boxsize
    xmax = xc + boxsize
    ymin = yc - boxsize
    ymax = yc + boxsize
    mean, median, std = sigma_clipped_stats(image[xmin:xmax,ymin:ymax], sigma = 3.0)
    try:
        if np.max(image[xmin:xmax,ymin:ymax]) > 10.0*std:
            return np.transpose(np.vstack((xc, yc, 1)))
            #return [[xc],[yc],[1]]
    except:
        return []
    return []

# only works on linux
def get_stars_sex(image, filename=None):
    
    filename = 'C:/minerva/data/n20200206/n20200206.MRED.FAU.backlight.0001.fits'

    t0 = datetime.datetime.utcnow()
    catname = sextract('',filename,sexfile='backlight.sex')
    #print "extracted stars in " + str((datetime.datetime.utcnow() - t0).total_seconds()) + ' seconds'
    cat = readsexcat(catname)
    #print "read catalog in " + str((datetime.datetime.utcnow() - t0).total_seconds()) + ' seconds'

    ipdb.set_trace()

# this kills main.py if running (use before runninging to ensure a clean start)
def killmain(red=False,south=False):
    for pid in psutil.pids():
        p = psutil.Process(pid)
        if p.name() == "python" and pid != os.getpid():
            if len(p.cmdline()) > 1:
                if (p.cmdline())[1] == 'mainNew.py' or (p.cmdline())[1] == 'main.py' or (p.cmdline())[1] == 'daytimespec.py' :
                    if len(p.cmdline()) == 3:
                        if (p.cmdline())[2] == '--red' and red:
                            # kill main.py --red
                            os.kill(pid, signal.SIGKILL)
                        elif (p.cmdline())[2] == '--south' and south:
                            # kill main.py --south
                            os.kill(pid, signal.SIGKILL)    
                    else:
                        # kill main.py
                        if not red and not south:
                            os.kill(pid, signal.SIGKILL)    

def dateobs2jd(dateobs):
    t0 = datetime.datetime(2000,1,1)
    t0jd = 2451544.5
    ti = datetime.datetime.strptime(dateobs,"%Y-%m-%dT%H:%M:%S.%f")
    return t0jd + (ti-t0).total_seconds()/86400.0

def findBrightest(imageName):
    catname = sextract('',imageName)
    cat = readsexcat(catname)
    try: brightest = np.argmax(cat['FLUX_ISO'])
    except: return None,None
    
    try:
        x = cat['XWIN_IMAGE'][brightest]
        y = cat['YWIN_IMAGE'][brightest]
        return x,y
    except:
        return None, None


# reads a CSV into a dictionary; the header line becomes the keys for lists
def readcsv(filename):
    # parse the CSV file                                                                                    
    with open(filename,'rb') as f:
        reader = unicodecsv.reader(f)
        headers = reader.next()
        csv = {}
        for h in headers:
            csv[h.split('(')[0].strip()] = []
        for row in reader:
            for h,v in zip(headers,row):
                csv[h.split('(')[0].strip()].append(v)
        for key in csv.keys():
            try: csv[key] = np.asarray(csv[key],dtype=np.float32)
            except: csv[key] = np.asarray(csv[key])
        return csv

def brightStars(filename='bsc.csv',path='/home/minerva/minerva-control/dependencies/',maxmag=6.0):
#def brightStars(filename='brightstars2.csv',path='/home/minerva/minerva-control/dependencies/',maxmag=6.0):
    brightstars = readcsv(path+filename)
    brightest = np.where(brightstars['vmag'] <= maxmag)
    for key in brightstars.keys():
        brightstars[key] = brightstars[key][brightest]

    '''
    # cut out high proper motion stars
    pm = np.sqrt(np.power(brightstars['pmra'],2) + np.power(brightstars['pmdec'],2) )
    lowmu = np.where(pm <= 100)
    for key in brightstars.keys():
        brightstars[key] = brightstars[key][lowmu]
    '''

    return brightstars

def parseTarget(line, logger=None):
    try:
        target = json.loads(line)
    except ValueError:
        if logger == None:
            print 'Not a valid JSON line: ' + line
        else:
            logger.error('Not a valid JSON line: ' + line)
        return -1

    # convert strings to datetime objects
    target['starttime'] = datetime.datetime.strptime(target['starttime'],'%Y-%m-%d %H:%M:%S')
    target['endtime'] = datetime.datetime.strptime(target['endtime'],'%Y-%m-%d %H:%M:%S')
    return target

def scheduleIsValid(scheduleFile, email=True, logger=None, directory=None):
    if not os.path.exists(scheduleFile):
        if logger != None: 
            logger.error('No schedule file: ' + scheduleFile)
        else: 
            print 'No schedule file: ' + scheduleFile
        return False

    emailbody = ''
    with open(scheduleFile, 'r') as targetfile:
        linenum = 1
        line = targetfile.readline()
        try: CalibInfo = json.loads(line)
        except: CalibInfo = -1

        # check for malformed JSON code
        if CalibInfo == -1:
            if logger != None: logger.error('Line ' + str(linenum) + ': malformed JSON: ' + line)
            emailbody = emailbody + 'Line ' + str(linenum) + ': malformed JSON: ' + line + '\n'
        else:
            requiredKeys = ['nbias','ndark','nflat','darkexptime','flatFilters','WaitForMorning']
            for key in requiredKeys:
                if key not in CalibInfo.keys():
                    if logger != None: logger.error('Line 1: Required key (' + key + ') not present: ' + line)
                    emailbody = emailbody + 'Line 1: Required key (' + key + ') not present: ' + line + '\n'

        linenum = 2
        line = targetfile.readline()
        try: CalibEndInfo = json.loads(line)
        except: CalibEndInfo = -1

        # check for malformed JSON code
        if CalibEndInfo == -1:
            if logger != None: logger.error('Line ' + str(linenum) + ': malformed JSON: ' + line)
            emailbody = emailbody + 'Line ' + str(linenum) + ': malformed JSON: ' + line + '\n'
        else:
            requiredKeys = ['nbiasEnd','ndarkEnd','nflatEnd']
            for key in requiredKeys:
                if key not in CalibEndInfo.keys():
                    if logger != None: logger.error('Line 2: Required key (' + key + ') not present: ' + line)
                    emailbody = emailbody + 'Line 2: Required key (' + key + ') not present: ' + line + '\n'

        linenum = 3
        for line in targetfile:
            target = parseTarget(line)
            
            # check for malformed JSON code
            if target == -1:
                if logger != None: logger.error('Line ' + str(linenum) + ': malformed JSON: ' + line)
                emailbody = emailbody + 'Line ' + str(linenum) + ': malformed JSON: ' + line + '\n'
            else:
                # check to make sure all required keys are present  
                key = 'name'
                if key not in target.keys():
                    if logger != None: logger.error('Line ' + str(linenum) + ': Required key (' + key + ') not present: ' + line)
                    emailbody = emailbody + 'Line ' + str(linenum) + ': Required key (' + key + ') not present: ' + line + '\n'
                else:
                    if target['name'] == 'autofocus':
                        requiredKeys = ['starttime','endtime']
                    else:
                        requiredKeys = ['starttime','endtime','ra','dec','filter','num','exptime','defocus','selfguide','guide','cycleFilter']

                    for key in requiredKeys:
                        if key not in target.keys():
                            if logger != None: logger.error('Line ' + str(linenum) + ': Required key (' + key + ') not present: ' + line)
                            emailbody = emailbody + 'Line ' + str(linenum) + ': Required key (' + key + ') not present: ' + line + '\n'
                            
                    if target['name'] <> 'autofocus':
                        try:
                            nnum = len(target['num'])
                            nexptime = len(target['exptime'])
                            nfilter = len(target['filter'])
                            if nnum <> nexptime or nnum <> nfilter:
                                if logger != None: logger.error('Line ' + str(linenum) + ': Array size for num (' + str(nnum) + '), exptime (' + str(nexptime) + '), and filter (' + str(nfilter) + ') must agree')
                                emailbody = emailbody + 'Line ' + str(linenum) + ': Array size for num (' + str(nnum) + '), exptime (' + str(nexptime) + '), and filter (' + str(nfilter) + ') must agree\n'                   \
                                    
                        except:
                            pass
                        try: 
                            if target['ra'] > 24.0 or target['ra'] < 0:
                                if logger != None: logger.error('Line ' + str(linenum) + ': RA (' + str(target['ra']) + ') must be in decimal hours (0 < RA < 24)')
                                emailbody = emailbody + 'Line ' + str(linenum) + ': RA (' + str(target['ra']) + ') must be in decimal hours (0 < RA < 24)\n'
                        except: pass
                        try: 
                            if target['dec'] > 90.0 or target['dec'] < -90:
                                if logger != None: logger.error('Line ' + str(linenum) + ': Dec (' + str(target['dec']) + ') must be in decimal degrees (-90 < RA < 90)')
                                emailbody = emailbody + 'Line ' + str(linenum) + ': Dec (' + str(target['dec']) + ') must be in decimal degrees (-90 < RA < 90)\n'
                        except: pass
                        
            linenum = linenum + 1
            if emailbody <> '':
                if email: mail.send("Errors in target file: " + scheduleFile,emailbody,level='serious',directory=directory)
                return False
    return True




# gets the telescope object (by reference) corresponding to a particular telescope number
def getTelescope(minerva, telid):

    for telescope in minerva.telescopes:
        if telescope.num == str(telid) or telescope.id == str(telid):
            return telescope
    return False

# gets the camera object (by reference) corresponding to a particular telescope number
def getCamera(minerva, telid):

    for camera in minerva.cameras:
        if camera.telnum == str(telid) or camera.telid == str(telid):
            return camera
    return False

# gets the dome object (by reference) corresponding to a particular telescope number
def getDome(minerva, telnum):
    
    # this is a hack and should be done better
    if telnum == 5 or telnum == 'MRED': 
        dome = minerva.domes[0]
        return dome

    if telnum == 'T1' or telnum == 'T2':
        domenum = 1
    elif telnum == 'T3' or telnum == 'T4':
        domenum = 2
    elif float(telnum) < 1:
        return False
    elif float(telnum) <= 2:
        domenum = 1
    elif float(telnum) <= 4:
        domenum = 2
    else: return False

    for dome in minerva.domes:
        if dome.num == str(domenum):
            return dome

    return False


def night():
    today = datetime.datetime.utcnow()
    if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
        today = today + datetime.timedelta(days=1)
    return 'n' + today.strftime('%Y%m%d')

def update_logger_path(logger, newpath):
    fmt = "%(asctime)s.%(msecs).03d [%(filename)s:%(lineno)s - %(funcName)s()] %(levelname)s: %(threadName)s: %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S"
    formatter = logging.Formatter(fmt,datefmt=datefmt)
    formatter.converter = time.gmtime

    for fh in logger.handlers: logger.removeHandler(fh)
    fh = logging.FileHandler(newpath, mode='a')
    fh.setFormatter(formatter)
    logger.addHandler(fh)

def setup_logger(base_dir, night, logger_name):

    path = base_dir + '/log/' + night

    if os.path.exists(path) == False:os.mkdir(path)
    fmt = "%(asctime)s.%(msecs).03d [%(filename)s:%(lineno)s - %(funcName)s()] %(levelname)s: %(threadName)s: %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S"

    logger = logging.getLogger(logger_name)
    formatter = logging.Formatter(fmt,datefmt=datefmt)
    formatter.converter = time.gmtime

    fileHandler = logging.FileHandler(path + '/' + logger_name + '.log', mode='a')
    fileHandler.setFormatter(formatter)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.setLevel(logging.INFO)

    # add a separate logger for the terminal (don't display debug-level messages)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(fileHandler)
    logger.addHandler(console)

    return logger

# Truncates target['starttime'] and target['endtime'] to ensure 
# the object is observable (Sun below sunalt and target above horizon)
def truncate_observable_window(site,target,sunalt=-12.0,horizon=21.0,timeof=None,logger=None):

    if timeof == None: timeof = datetime.datetime.utcnow()

    sunset = site.sunset(horizon=sunalt, start=timeof)
    sunrise = site.sunrise(horizon=sunalt, start=timeof)

    niter = 0
    while sunrise < timeof and niter < 100:
        sunrise = site.sunrise(horizon=sunalt, start=timeof + datetime.timedelta(days=0.1*niter))
        niter += 1
    if sunrise < timeof:
        if logger <> None: logger.error("Error calculating nearest sunrise")
        return

    niter = 0
    while sunset > sunrise and niter < 100:
        sunset = site.sunset(horizon=sunalt, start=timeof - datetime.timedelta(days=0.1*niter))
        niter += 1
    if sunset > sunrise:
        if logger <> None: logger.error("Error calculating nearest sunset")
        return
        
    site.obs.horizon = str(horizon)
    body = ephem.FixedBody()
    body._ra = ephem.hours(str(target['ra']))
    body._dec = ephem.degrees(str(target['dec']))

    #S UTC vs local time not right for epoch, but not significant
    body._epoch = timeof#datetime.datetime.utcnow()
    body.compute()

    # calculate the object's rise time
    try:
        risetime = site.obs.next_rising(body,start=sunset).datetime()
    except ephem.AlwaysUpError:
        # if it's always up, we can observe at sunset
        risetime = sunset
    except ephem.NeverUpError:
        # if it's never up, skip the target
        risetime = sunrise

    # calculate the object's set time
    try:
        settime = site.obs.next_setting(body,start=sunset).datetime()
    except ephem.AlwaysUpError:
        # if it's always up, we can observe until sunrise
        settime = sunrise
    except ephem.NeverUpError:
        # if it's never up, skip the target
        settime = sunset

    # if it rises before it sets, redo with the previous day
    niter = 0
    while risetime > settime and niter < 100:
        try:
            risetime = site.obs.next_rising(body,start=sunset - datetime.timedelta(days=0.1*niter)).datetime()
        except ephem.AlwaysUpError:
            # if it's always up, don't modify the start time
            risetime = sunset
        except ephem.NeverUpError:
            # if it's never up, skip the target
            risetime = sunrise
        niter += 1

    if risetime > settime:
        if logger <> None: logger.error("Error calculating nearest sunset")
        return

    # the start time should be the later of the requested start time, when the target rises, or when the sun sets
    starttime = max(target['starttime'],risetime,sunset) 

    # the end time should be the earlier of the requested end time, when the target sets, or when the sun rises
    endtime = min(target['endtime'],sunrise,settime)

    if logger <> None:
        logger.info('Time of calculation is ' + str(timeof))
        logger.info('Target start time is ' + str(target['starttime']))
        logger.info('Target rise time is ' + str(risetime))
        logger.info('The new start time is ' + str(starttime))
        logger.info('Sun set time is '  + str(sunset))
        logger.info('Target end time is ' + str(target['endtime']))
        logger.info('Target set time is '  + str(settime))
        logger.info('Sun rise time is '  + str(sunrise))
        logger.info('The new end time is ' + str(endtime))   

    target['starttime'] = starttime
    target['endtime'] = endtime

    return target

# converts a sexigesimal string to a float
# the string may be delimited by either spaces or colons
def ten(string):
    array = re.split(' |:',string)
    if "-" in array[0]:
        return float(array[0]) - float(array[1])/60.0 - float(array[2])/3600.0
    return float(array[0]) + float(array[1])/60.0 + float(array[2])/3600.0

# run astrometry.net on imageName, update solution in header
def astrometry(imageName, rakey='RA', deckey='DEC',pixscalekey='PIXSCALE', pixscale=None, nopositionlimit=False, noquadlimit=False):
    hdr = pyfits.getheader(imageName)

    try:
        if pixscale == None:
            pixscale = float(hdr[pixscalekey])
    except:
        return False

    try: ra = float(hdr[rakey])
    except: ra = ten(hdr[rakey])*15.0
    
    try: dec = float(hdr[deckey])
    except: dec = ten(hdr[deckey])
    if dec > 90.0: dec = dec - 360.0
    
    radius = 3.0*pixscale*float(hdr['NAXIS1'])/3600.0
    
    cmd = 'solve-field --scale-units arcsecperpix' + \
        ' --scale-low ' + str(0.99*pixscale) + \
        ' --scale-high ' + str(1.01*pixscale)

    if not nopositionlimit:
        cmd += ' --ra ' + str(ra) + \
            ' --dec ' + str(dec) + \
            ' --radius ' + str(radius)
    if not noquadlimit:
        cmd += ' --quad-size-min 0.4' + \
            ' --quad-size-max 0.6'
    cmd += ' --cpulimit 30' + \
        ' --no-verify' + \
        ' --crpix-center' + \
        ' --no-fits2fits' + \
        ' --no-plots' + \
        ' --overwrite ' + \
        imageName
#        ' --use-sextractor' + \ #need to install sextractor
#        ' --quad-size-min 0.4' + \
#        ' --quad-size-max 0.6' + \

    cmd = r'/usr/local/astrometry/bin/' + cmd + ' >/dev/null 2>&1'
    os.system(cmd)
    
    baseName = os.path.splitext(imageName)[0]
    f = pyfits.open(imageName, mode='update')
    if os.path.exists(baseName + '.new'):
      
        # preserve original solution
        orighdr = pyfits.getheader(imageName)
        f[0].header['WCD1_1'] = float(f[0].header['CD1_1'])
        f[0].header['WCD1_2'] = float(f[0].header['CD1_2'])
        f[0].header['WCD2_1'] = float(f[0].header['CD2_1'])
        f[0].header['WCD2_2'] = float(f[0].header['CD2_2'])
        f[0].header['WCRVAL1'] = float(f[0].header['CRVAL1'])
        f[0].header['WCRVAL2'] = float(f[0].header['CRVAL2'])

        # copy the WCS solution to the file
        newhdr = pyfits.getheader(baseName + '.new')
        f[0].header['WCSSOLVE'] = 'True'
        f[0].header['WCSAXES'] = newhdr['WCSAXES']
        f[0].header['CTYPE1'] = newhdr['CTYPE1']
        f[0].header['CTYPE2'] = newhdr['CTYPE2']
        f[0].header['EQUINOX'] = newhdr['EQUINOX']
        f[0].header['LONPOLE'] = newhdr['LONPOLE']
        f[0].header['LATPOLE'] = newhdr['LATPOLE']
        f[0].header['CRVAL1'] = newhdr['CRVAL1']
        f[0].header['CRVAL2'] = newhdr['CRVAL2']
        f[0].header['CRPIX1'] = newhdr['CRPIX1']
        f[0].header['CRPIX2'] = newhdr['CRPIX2']
        f[0].header['CUNIT1'] = newhdr['CUNIT1']
        f[0].header['CUNIT2'] = newhdr['CUNIT2']
        f[0].header['CD1_1'] = newhdr['CD1_1']
        f[0].header['CD1_2'] = newhdr['CD1_2']
        f[0].header['CD2_1'] = newhdr['CD2_1']
        f[0].header['CD2_2'] = newhdr['CD2_2']
        f[0].header['IMAGEW'] = newhdr['IMAGEW']
        f[0].header['IMAGEH'] = newhdr['IMAGEH']
        f[0].header['A_ORDER'] = newhdr['A_ORDER']
        f[0].header['A_0_2'] = newhdr['A_0_2']
        f[0].header['A_1_1'] = newhdr['A_1_1']
        f[0].header['A_2_0'] = newhdr['A_2_0']
        f[0].header['B_ORDER'] = newhdr['B_ORDER']
        f[0].header['B_0_2'] = newhdr['B_0_2']
        f[0].header['B_1_1'] = newhdr['B_1_1']
        f[0].header['B_2_0'] = newhdr['B_2_0']
        f[0].header['AP_ORDER'] = newhdr['AP_ORDER']
        f[0].header['AP_0_1'] = newhdr['AP_0_1']
        f[0].header['AP_0_2'] = newhdr['AP_0_2']
        f[0].header['AP_1_0'] = newhdr['AP_1_0']
        f[0].header['AP_1_1'] = newhdr['AP_1_1']
        f[0].header['AP_2_0'] = newhdr['AP_2_0']
        f[0].header['BP_ORDER'] = newhdr['BP_ORDER']
        f[0].header['BP_0_1'] = newhdr['BP_0_1']
        f[0].header['BP_0_2'] = newhdr['BP_0_2']
        f[0].header['BP_1_0'] = newhdr['BP_1_0']
        f[0].header['BP_1_1'] = newhdr['BP_1_1']
        f[0].header['BP_2_0'] = newhdr['BP_2_0']
        success = True
    else:
        f[0].header['WCSSOLVE'] = 'False'
        success = False
    f.flush()
    f.close()

    # clean up extra files
    extstodelete = ['-indx.png','-indx.xyls','-ngc.png','-objs.png','.axy',
                    '.corr','.match','.new','.rdls','.solved','.wcs']
    for ext in extstodelete:
        if os.path.exists(baseName + ext):
            os.remove(baseName + ext)
        
    return success
    
# run sextractor on an image
def sextract(datapath,imagefile,sexfile='autofocus.sex',paramfile=None,convfile=None,catfile=None):
    #S Path on MinervaMAIN where all the .sex, .param, etc. files will be
    #S located
    sexpath = '/usr/share/sextractor/'

    #S This is the base command we be calling with sextractor. It has
    #S the default sexfile of autofocus.sex, which will be given some pretty
    #S general values for now.
    # We'll add on other parameters and arguements as they are specified
    sexcommand = 'sex '+datapath+imagefile+' -c ' + sexpath+sexfile
    
    #S If a paramfile was specfied, then we will use that instead of the
    #S default param file in autofocus.sex (which is autofocus.param)
    if paramfile <> None:
        sexcommand+= ' -PARAMETERS_NAME ' + sexpath+paramfile

    #S Similar to above, but the convolution filter
    if convfile <> None:
        sexcommand+= ' -FILTER_NAME ' + sexpath+convfile

    #S we're going to name the catalog after the image just by removing the
    #S fits and  adding cat. if a cat file is specified we'll use that.
    #S Datapath is the path where the image is (hopefully), but can be anywhere
    #S you want it to go.
    if catfile == None:
        catfile = imagefile.split('.fits')[0] + '.cat'
        sexcommand += ' -CATALOG_NAME ' + datapath+catfile

    #S so we a have sexcommand, which has all of its components split by
    #S spaces ideally, which will allow for just a .split to put in a list
    #S for subprocess.call
    subprocess.call(sexcommand.split())

    #S Just going to return the catalog file name for now, could return fwhm,
    #S whatever later
    return datapath+catfile

# read a generic sextractor catalog file into a dictionary
# the header values (PARAMS) become the dictionary keys
# objects are read into lists under each dictionary key
def readsexcat(catname):

    data = {}
    if not os.path.exists(catname): return data
    with open(catname,'rb') as filep:
        header = []
        for line in filep:
            # header lines begin with # and are the 3rd item in the line
            if line.startswith('#'):
                header.append(line.split()[2])
                for h in header:
                    data[h] = []
            # older sextractor catalogs contain a few nuisance lines; ignore those
            elif not line.startswith('-----') and not line.startswith('Measuring') and \
                    not line.startswith('(M+D)') and not line.startswith('Objects:'):
                # assume all values are floats
                values = [ float(x) for x in line.split() ]
                for h,v in zip(header,values):
                    data[h].append(v)
    for key in data.keys():
        #S try and convert to an np.array, and if not possible jsut pass
        #S the try is in case for some reason a non-numerical entry is 
        #S encountered. may be a l
        try:
            data[key] = np.array(data[key])
        except:
            pass

    return data
