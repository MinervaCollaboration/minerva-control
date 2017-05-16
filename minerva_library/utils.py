# this file contains a set of generally useful utility functions for MINERVA operations
import re
import subprocess, psutil, os, signal
import pyfits
import numpy as np
import ephem
import datetime, time
import ipdb
import logging
import unicodecsv


# this kills main.py if running (use before runninging to ensure a clean start)
def killmain(red=False,south=False):
    for pid in psutil.pids():
        p = psutil.Process(pid)
        if p.name() == "python" and pid != os.getpid():
            if len(p.cmdline()) > 1:
                if (p.cmdline())[1] == 'main_mw_TV.py' or (p.cmdline())[1] == 'main.py' or (p.cmdline())[1] == 'daytimespec.py' :
                    if len(p.cmdline()) == 3:
                        if (p.cmdline())[2] == '--red' and red:
                            # kill main.py --red
                            os.kill(pid, signal.SIGKILL)
                        elif (p.cmdline())[2] == '--south' and south:
                            # kill main.py --south
                            os.kill(pid, signal.SIGKILL)    
                    else:
                        # kill main.py
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

# gets the telescope object (by reference) corresponding to a particular telescope number
def getTelescope(minerva, telnum):

    for telescope in minerva.telescopes:
        if telescope.num == str(telnum):
            return telescope
    return False

# gets the camera object (by reference) corresponding to a particular telescope number
def getCamera(minerva, telnum):

    for camera in minerva.cameras:
        if camera.telnum == str(telnum):
            return camera
    return False

# gets the dome object (by reference) corresponding to a particular telescope number
def getDome(minerva, telnum):
    
    if float(telnum) < 1:
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
def truncate_observable_window(site,target,sunalt=-18.0,horizon=21.0):

    sunset = site.sunset(horizon=sunalt)
    sunrise = site.sunrise(horizon=sunalt)

    starttime = max(sunset,target['starttime'])
    endtime = min(sunrise,target['endtime'])

    site.obs.horizon = str(horizon)

    body = ephem.FixedBody()
    body._ra = ephem.hours(str(target['ra']))
    body._dec = ephem.degrees(str(target['dec']))


    #S UTC vs local time not right for epoch, but not significant
    body._epoch = datetime.datetime.utcnow()
    body.compute()

    # calculate the object's rise time
    try:
        risetime = site.obs.next_rising(body,start=sunset).datetime()
    except ephem.AlwaysUpError:
        # if it's always up, don't modify the start time
        risetime = starttime
    except ephem.NeverUpError:
        # if it's never up, skip the target
        risetime = endtime

    # calculate the object's set time
    try:
        settime = site.obs.next_setting(body,start=sunset).datetime()
    except ephem.AlwaysUpError:
        # if it's always up, don't modify the end time
        settime = endtime
    except ephem.NeverUpError:
        # if it's never up, skip the target
        settime = starttime

    # if it rises before it sets, redo with the previous day
    if risetime > settime:
        try:
            risetime = site.obs.next_rising(body,start=sunset - datetime.timedelta(days=1)).datetime()
        except ephem.AlwaysUpError:
            # if it's always up, don't modify the start time
            risetime = starttime
        except ephem.NeverUpError:
            # if it's never up, skip the target
            risetime = endtime

    # modify start time to ensure the target is always above the horizon
    if starttime < risetime:
        starttime = risetime
    if endtime > settime:
        endtime = settime

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
def astrometry(imageName, rakey='RA', deckey='DEC',pixscalekey='PIXSCALE', pixscale=None):
    hdr = pyfits.getheader(imageName)

    if pixscale == None:
        pixscale = float(hdr[pixscalekey])
    
    try: ra = float(hdr[rakey])
    except: ra = ten(hdr[rakey])*15.0
    
    try: dec = float(hdr[deckey])
    except: dec = ten(hdr[deckey])
    if dec > 90.0: dec = dec - 360.0
    
    radius = 3.0*pixscale*float(hdr['NAXIS1'])/3600.0
    
    cmd = 'solve-field --scale-units arcsecperpix' + \
        ' --scale-low ' + str(0.99*pixscale) + \
        ' --scale-high ' + str(1.01*pixscale) + \
        ' --ra ' + str(ra) + \
        ' --dec ' + str(dec) + \
        ' --radius ' + str(radius) +\
        ' --quad-size-min 0.4' + \
        ' --quad-size-max 0.6' + \
        ' --cpulimit 30' + \
        ' --no-verify' + \
        ' --crpix-center' + \
        ' --no-fits2fits' + \
        ' --no-plots' + \
        ' --overwrite ' + \
        imageName
#        ' --use-sextractor' + \ #need to install sextractor

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
    else:
        f[0].header['WCSSOLVE'] = 'False'
    f.flush()
    f.close()

    # clean up extra files
    extstodelete = ['-indx.png','-indx.xyls','-ngc.png','-objs.png','.axy',
                    '.corr','.match','.new','.rdls','.solved','.wcs']
    for ext in extstodelete:
        if os.path.exists(baseName + ext):
            os.remove(baseName + ext)
            
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
    
