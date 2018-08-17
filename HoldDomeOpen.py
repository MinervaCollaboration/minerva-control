import urllib, urllib2, datetime, time
import telnetlib, socket, os, glob, json, ipdb
import threading, sys, logging
from win32com.client import Dispatch
import ephem, math
from xml.etree import ElementTree
import subprocess
import pyfits
#from astropy.time import Time
import shutil

# google drive dependencies
import httplib2
import pprint
from apiclient.discovery import build
from apiclient.http import MediaFileUpload
from oauth2client.client import OAuth2WebServerFlow

Observing = True
sunOverride = True
cloudOverride = False

# reset the night at local 10 am
today = datetime.datetime.utcnow()

if datetime.datetime.now().hour > 10 and datetime.datetime.now().hour < 17:
    today = today + datetime.timedelta(days=1)
night = 'n' + today.strftime('%Y%m%d')

# the most recent local 10 am (17:00 UTC)
startNightTime = datetime.datetime(today.year, today.month, today.day, 17) - datetime.timedelta(days=1)

# Telescope communications
HOST = "127.0.0.1" # Localhost
PORT = 44444

######################################################################

def makeUrl(**kwargs):
    """
    Utility function that takes a set of keyword=value arguments
    and converts them into a properly formatted URL to send to PWI.
    For example, calling the function as:
      makeUrl(device="mount", cmd="move", ra2000="10 20 30", dec2000="20 30 40")
    will return the string:
      http://127.0.0.1:8080/?device=mount&cmd=move&dec=20+30+40&ra=10+20+30

    Note that spaces have been URL-encoded to "+" characters.
    """

    url = "http://" + HOST + ":" + str(PORT) + "/?"
    url = url + urllib.urlencode(kwargs.items())
    return url

def pwiRequest(**kwargs):
    """
    Issue a request to PWI using the keyword=value parameters
    supplied to the function, and return the response received from
    PWI.

    For example:
      makeUrl(device="mount", cmd="move", ra2000="10 20 30", dec2000="20 30 40")
    will request a slew to J2000 coordinates 10:20:30, 20:30:40, and will
    (under normal circumstances) return the status of the telescope as an
    XML string.
    """

    url = makeUrl(**kwargs)
    return urllib.urlopen(url).read()

def pwiRequestAndParse(**kwargs):
    """
    Works like pwiRequest(), except returns a parsed XML object rather
    than XML text
    """

    return parseXml(pwiRequest(**kwargs))

def parseXml(xml):
    """
    Convert the XML into a smart structure that can be navigated via
    the tree of tag names; e.g. "status.mount.ra"
    """

    return elementTreeToObject(ElementTree.fromstring(xml))

### Status wrappers #####################################

def getStatusXml():
    """
    Return a string containing the XML text representing the status of the telescope
    """

    return pwiRequest(cmd="getsystem")

def getStatus():
    """
    Return a status object representing the tree structure of the XML text.
    Example: getStatus().mount.tracking --> "False"
    """

    return parseXml(getStatusXml())

### High-level command wrappers begin here ##############

### FOCUSER ###

def focuserConnect(port=1):
    """
    Connect to the focuser on the specified Nasmyth port (1 or 2).
    """

    return pwiRequestAndParse(device="focuser"+str(port), cmd="connect")

def focuserDisconnect(port=1):
    """
    Disconnect from the focuser on the specified Nasmyth port (1 or 2).
    """

    return pwiRequestAndParse(device="focuser"+str(port), cmd="disconnect")

def focuserMove(position, port=1):
    """
    Move the focuser to the specified position in microns
    """

    return pwiRequestAndParse(device="focuser"+str(port), cmd="move", position=position)

def focuserIncrement(offset, port=1):
    """
    Offset the focuser by the specified amount, in microns
    """

    return pwiRequestAndParse(device="focuser"+str(port), cmd="move", increment=offset)

def focuserStop(port=1):
    """
    Halt any motion on the focuser
    """

    return pwiRequestAndParse(device="focuser"+str(port), cmd="stop")

def startAutoFocus():
    """
    Begin an AutoFocus sequence for the currently active focuser
    """

    return pwiRequestAndParse(device="focuser", cmd="startautofocus")

### ROTATOR ###

def rotatorMove(position, port=1):
    return pwiRequestAndParse(device="rotator"+str(port), cmd="move", position=position)

def rotatorIncrement(offset, port=1):
    return pwiRequestAndParse(device="rotator"+str(port), cmd="move", increment=offset)

def rotatorStop(port=1):
    return pwiRequestAndParse(device="rotator"+str(port), cmd="stop")

def rotatorStartDerotating(port=1):
    return pwiRequestAndParse(device="rotator"+str(port), cmd="derotatestart")

def rotatorStopDerotating(port=1):
    return pwiRequestAndParse(device="rotator"+str(port), cmd="derotatestop")

### MOUNT ###

def mountConnect():
    return pwiRequestAndParse(device="mount", cmd="connect")

def mountDisconnect():
    return pwiRequestAndParse(device="mount", cmd="disconnect")

def mountEnableMotors():
    return pwiRequestAndParse(device="mount", cmd="enable")

def mountDisableMotors():
    return pwiRequestAndParse(device="mount", cmd="disable")

def mountOffsetRaDec(deltaRaArcseconds, deltaDecArcseconds):
    return pwiRequestAndParse(device="mount", cmd="move", incrementra=deltaRaArcseconds, incrementdec=deltaDecArcseconds)

def mountOffsetAltAz(deltaAltArcseconds, deltaAzArcseconds):
    return pwiRequestAndParse(device="mount", cmd="move", incrementazm=deltaAzArcseconds, incrementalt=deltaAltArcseconds)

def mountGotoRaDecApparent(raAppHours, decAppDegs):
    """
    Begin slewing the telescope to a particular RA and Dec in Apparent (current
    epoch and equinox, topocentric) coordinates.

    raAppHours may be a number in decimal hours, or a string in "HH MM SS" format
    decAppDegs may be a number in decimal degrees, or a string in "DD MM SS" format
    """

    return pwiRequestAndParse(device="mount", cmd="move", ra=raAppHours, dec=decAppDegs)

def mountGotoRaDecJ2000(ra2000Hours, dec2000Degs):
    """
    Begin slewing the telescope to a particular J2000 RA and Dec.
    ra2000Hours may be a number in decimal hours, or a string in "HH MM SS" format
    dec2000Degs may be a number in decimal degrees, or a string in "DD MM SS" format
    """
    return pwiRequestAndParse(device="mount", cmd="move", ra2000=ra2000Hours, dec2000=dec2000Degs)

def mountGotoAltAz(altDegs, azmDegs):
    return pwiRequestAndParse(device="mount", cmd="move", alt=altDegs, azm=azmDegs)

def mountStop():
    return pwiRequestAndParse(device="mount", cmd="stop")

def mountTrackingOn():
    return pwiRequestAndParse(device="mount", cmd="trackingon")

def mountTrackingOff():
    return pwiRequestAndParse(device="mount", cmd="trackingoff")

def mountSetTracking(trackingOn):
    if trackingOn:
        mountTrackingOn()
    else:
        mountTrackingOff()

def mountSetTrackingRateOffsets(raArcsecPerSec, decArcsecPerSec):
    """
    Set the tracking rates of the mount, represented as offsets from normal
    sidereal tracking in arcseconds per second in RA and Dec.
    """
    return pwiRequestAndParse(device="mount", cmd="trackingrates", rarate=raArcsecPerSec, decrate=decArcsecPerSec)

def mountSetPointingModel(filename):
    return pwiRequestAndParse(device="mount", cmd="setmodel", filename=filename)

### M3 ###

def m3SelectPort(port):
    return pwiRequestAndParse(device="m3", cmd="select", port=port)

def m3Stop():
    return pwiRequestAndParse(device="m3", cmd="stop")



### XML Parsing Utilities ##################################

class Status: 
    """
    Contains a node (and possible sub-nodes) in the parsed XML status tree.
    Properties are added to the class by the elementTreeToObject function.
    """

    def __str__(self):
        result = ""
        for k,v in self.__dict__.items():
            result += "%s: %s\n" % (k, str(v))

        return result

def elementTreeToObject(elementTreeNode):
    """
    Recursively convert an ElementTree node to a hierarchy of objects that allow for
    easy navigation of the XML document. For example, after parsing:
      <tag1><tag2>data</tag2><tag1> 
    You could say:
      xml.tag1.tag2   # evaluates to "data"
    """

    if len(elementTreeNode) == 0:
        return elementTreeNode.text

    result = Status()
    for childNode in elementTreeNode:
        setattr(result, childNode.tag, elementTreeToObject(childNode))

    result.value = elementTreeNode.text

    return result


def getWeather():

    # the URL for the machine readable weather page for the Ridge
    url = "http://linmax.sao.arizona.edu/weather/weather.cur_cond"

    # read the webpage
    logging.info('Requesting URL: ' + url)
    request = urllib2.Request(url)
    try:
        response = urllib2.urlopen(request)
    except:
        logging.error('Error reading the weather page: ' + str(sys.exc_info()[0]))
        return -1
    
    data = response.read().split('\n')
    if data[0] == '': return -1
    
    # convert the date into a datetime object
    weather = {
        'date':datetime.datetime.strptime(data[0],'%Y, %m, %d, %H, %M, %S, %f')}
    
    # populate the weather dictionary from the webpage
    for parameter in data[1:-1]:
        weather[(parameter.split('='))[0]] = float((parameter.split('='))[1])
#        logging.info(parameter)

    # add in the Sun Altitude
    weather['sunAltitude'] = sunAltitude()

    # add in the cloud monitor
    url = "http://mearth.sao.arizona.edu/weather/now"

    # read the webpage
    logging.info('Requesting URL: ' + url)
    request = urllib2.Request(url)
    try:
        response = urllib2.urlopen(request)
    except:
        logging.error('Error reading the weather page: ' + str(sys.exc_info()[0]))
        return -1
    data = response.read().split()
    if data[0] == '': return -1    
    if len(data) <> 14: return -1

    # MJD to datetime
    weather['cloudDate'] = datetime.datetime(1858,11,17,0) + datetime.timedelta(days=float(data[0]))
    weather['relativeSkyTemp'] = float(data[13])

    # Determine the last time the enclosure closed
    f = open('lastClose.txt','r')
    weather['lastClose'] = datetime.datetime.strptime(f.readline(),'%Y-%m-%d %H:%M:%S')
    f.close()
   
    # make sure all required keys are present
    pageError = False
    requiredKeys = ['totalRain', 'wxt510Rain', 'barometer', 'windGustSpeed', 
                    'outsideHumidity', 'outsideDewPt', 'outsideTemp', 
                    'windSpeed', 'windDirectionDegrees', 'date', 'sunAltitude',
                    'cloudDate', 'relativeSkyTemp','lastClose']
    for key in requiredKeys:
        if not key in weather.keys():
            # if not, return an error
            logging.error('Weather page does not have all required keys (' + key + ')')
            pageError = True

    if pageError: return -1

    # if everything checks out, return the weather
    return weather

def aqawanCommunicate(message):

    messages = ['HEARTBEAT','STOP','OPEN_SHUTTERS','CLOSE_SHUTTERS',
                'CLOSE_SEQUENTIAL','OPEN_SHUTTER_1','CLOSE_SHUTTER_1',
                'OPEN_SHUTTER_2','CLOSE_SHUTTER_2','LIGHTS_ON','LIGHTS_OFF',
                'ENC_FANS_HI','ENC_FANS_MED','ENC_FANS_LOW','ENC_FANS_OFF',
                'PANEL_LED_GREEN','PANEL_LED_YELLOW','PANEL_LED_RED',
                'PANEL_LED_OFF','DOOR_LED_GREEN','DOOR_LED_YELLOW',
                'DOOR_LED_RED','DOOR_LED_OFF','SON_ALERT_ON',
                'SON_ALERT_OFF','LED_STEADY','LED_BLINK',
                'MCB_RESET_POLE_FANS','MCB_RESET_TAIL_FANS',
                'MCB_RESET_OTA_BLOWER','MCB_RESET_PANEL_FANS',
                'MCB_TRIP_POLE_FANS','MCB_TRIP_TAIL_FANS',
                'MCB_TRIP_PANEL_FANS','STATUS','GET_ERRORS','GET_FAULTS',
                'CLEAR_ERRORS','CLEAR_FAULTS','RESET_PAC']

    # not an allowed message
    if not message in messages:
       logging.error('Message not recognized: ' + message)
       return -1

    IP = '192.168.1.14'
    port = 22004
    try:
        tn = telnetlib.Telnet(IP,port,5)
    except socket.timeout:
        logging.error('Timeout attempting to connect to the aqawan')
        return -1

    tn.write("vt100\r\n")

    response = ''
    while response == '':    
        tn.write(message + "\r\n")
        response = tn.read_until(b"/r/n/r/n#>",5)

    logging.info('Response from command ' + message + ': ' + response)
    tn.close()
    return response

    return response.split("=")[1].split()[0]
    return tn.read_all()

    time.sleep(2)

# much faster than querying the PAC
def enclosureOpen():
    with open("enclosureOpen.txt",'r') as f:
        isOpen = f.read()
        if isOpen == 'True': return True
        return False
        
# should do this asychronously and continuously
def aqawan():

    while Observing:            
        logging.info(aqawanCommunicate('HEARTBEAT'))
        if not oktoopen(open=True):
            closeAqawan()
        time.sleep(15)
        
def setObserver():
    obs = ephem.Observer()

    # MINERVA latitude/longitude at Mt. Hopkins
    obs.lat = ephem.degrees('31.680407') # N
    obs.lon = ephem.degrees('-110.878977') # E
    obs.elevation = 2316.0 # meters
    return obs

def sunAltitude():

    obs = setObserver()
    obs.date = datetime.datetime.utcnow()
    sun = ephem.Sun()
    sun.compute(obs)
    return float(sun.alt)*180.0/math.pi

def sunAzimuth():

    obs = setObserver()
    obs.date = datetime.datetime.utcnow()
    sun = ephem.Sun()
    sun.compute(obs)
    return float(sun.az)*180.0/math.pi

def aqawanStatus():

    response = aqawanCommunicate('STATUS').split(',')
    status = {}
    for entry in response:
        if '=' in entry:
            status[(entry.split('='))[0].strip()] = (entry.split('='))[1].strip()

#    if status['ERROR'] == 'TRUE':
#        logging.warning('Error condition exists in the PAC')
#        logging.warning(aqawanCommunicate('GET_ERRORS'))
#    if status['FAULT'] == 'TRUE':
#        logging.warning('Fault condition exists in the PAC')
#        logging.warning(aqawanCommunicate('GET_FAULTS'))

    return status

# Open a shutter of the aqawan
def openShutter(shutter):

    # make sure this is an allowed shutter
    if shutter not in [1,2]:
        logging.info('Invalid shutter specified (' + str(shutter) + ')')
        return -1

    status = aqawanStatus()
    timeout = 180.0
    elapsedTime = 0.0

    # if it's already open, return
    if status['Shutter' + str(shutter)] == 'OPEN':
        logging.info('Shutter' + str(shutter) + ' already open')
        return

    # park the telescopes to make sure they're safe from falling debris
    parkScope()

    # open the shutter
    start = datetime.datetime.utcnow()
    response = aqawanCommunicate('OPEN_SHUTTER_' + str(shutter))                
    logging.info(response)
    if not 'Success=TRUE' in response:
        # did the command fail?
        logging.warning('Failed to open shutter ' + str(shutter) + ': ' + response)
        ipdb.set_trace()
        # need to reset the PAC? ("Enclosure not in AUTO"?)
            
    # Wait for it to open
    status = aqawanStatus()
    while status['Shutter' + str(shutter)] == 'OPENING' and elapsedTime < timeout:
        status = aqawanStatus()
        elapsedTime = (datetime.datetime.utcnow()-start).total_seconds()

    # Did it fail to open?
    if status['Shutter' + str(shutter)] <> 'OPEN':
        logging.error('Error opening Shutter ' + str(shutter) )
        return -1

    logging.info('Shutter ' + str(shutter) + ' open')

def crackAqawan():
    sunOverride = True

    if oktoopen():
        print "Ok to open; cracking the aqawan"
        response = aqawanCommunicate("OPEN_SHUTTER_1")
        response = aqawanCommunicate("STOP")

    while True:            
        aqawanCommunicate('HEARTBEAT')
        if not oktoopen(open=True):
            closeAqawan()
        time.sleep(15)  

# Open the aqawan shutters sequentially
def openAqawan():
    if oktoopen():
        # Open Shutter 1
        response = openShutter(1)
        if response == -1: return -1

        # Open Shutter 2
        response = openShutter(2)
        if response == -1: return -1

        with open("enclosureOpen.txt",'w') as f: f.write("True")
        return response

    else: return -1


# TODO: check to make sure it's not closed, then close, error handling
def closeAqawan():

    timeout = 500
    elapsedTime = 0
    status = aqawanStatus()
    if status['Shutter1'] == "CLOSED" and status['Shutter2'] == "CLOSED":
        logging.info('Both shutters already closed')
        with open("enclosureOpen.txt",'w') as f: f.write("False")
    else:
        # Park the telescope in a safe position
        parkScope()
        
        response = aqawanCommunicate('CLOSE_SEQUENTIAL')
        if not 'Success=TRUE' in response:
            logging.error('Aqawan failed to close!')
            # need to send alerts, attempt other stuff
#            email('Aqawan failed to close!')
        else:
            logging.info(response)    
            start = datetime.datetime.utcnow()
            while (status['Shutter1'] <> "CLOSED" or status['Shutter2'] <> "CLOSED") and elapsedTime < timeout:
                elapsedTime = (datetime.datetime.utcnow() - start).total_seconds()
                status = aqawanStatus()
            if status['Shutter1'] <> "CLOSED" or status['Shutter2'] <> "CLOSED":
                logging.error('Aqawan failed to close after ' + str(elapsedTime) + 'seconds!')
                # need to send alerts, attempt other stuff
            else:
                logging.info('Closed both shutters')
                with open("lastClose.txt",'w') as f: f.write(datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))
                with open("enclosureOpen.txt",'w') as f: f.write("False")

                
def oktoopen(open=False):
    retval = True    

    # define the safe limits [min,max] for each weather parameter
    # define more conservative limits to open to prevent cycling when borderline conditions
    openLimits = {
        'totalRain':[0.0,1000.0],
        'wxt510Rain':[0.0,0.0], 
        'barometer':[0,2000], 
        'windGustSpeed':[0.0,35.0], 
        'outsideHumidity':[0.0,75.0], 
        'outsideDewPt':[-100.0,100.0],
        'outsideTemp':[-20.0,50.0], 
        'windSpeed':[0.0,30.0], 
        'windDirectionDegrees':[0.0,360.0],
        'date':[datetime.datetime.utcnow()-datetime.timedelta(minutes=5),datetime.datetime(2200,1,1)],
        'sunAltitude':[-90,6],
        'relativeSkyTemp':[-999,-37],
        'cloudDate':[datetime.datetime.utcnow()-datetime.timedelta(minutes=5),datetime.datetime(2200,1,1)],
        'lastClose':[datetime.datetime(2000,1,1),datetime.datetime.utcnow()-datetime.timedelta(minutes=20)],
        }

    closeLimits = {
        'totalRain':[0.0,1000.0],
        'wxt510Rain':[0.0,0.0], 
        'barometer':[0,2000], 
        'windGustSpeed':[0.0,40.0], 
        'outsideHumidity':[0.0,80.0], 
        'outsideDewPt':[-100.0,100.0],
        'outsideTemp':[-30.0,60.0], 
        'windSpeed':[0.0,35.0], 
        'windDirectionDegrees':[0.0,360.0],
        'date':[datetime.datetime.utcnow()-datetime.timedelta(minutes=5),datetime.datetime(2200,1,1)],
        'sunAltitude':[-90,6],
        'relativeSkyTemp':[-999,-40],
        'cloudDate':[datetime.datetime.utcnow()-datetime.timedelta(minutes=5),datetime.datetime(2200,1,1)],
        'lastClose':[datetime.datetime(2000,1,1),datetime.datetime(2200,1,1)],
        }

    if open: weatherLimits = closeLimits
    else: weatherLimits = openLimits

    if sunOverride: weatherLimits['sunAltitude'] = [-90,90]
    if cloudOverride: weatherLimits['relativeSkyTemp'] = [-999,999]

    # get the current weather, timestamp, and Sun's position
    weather = getWeather()
    while weather == -1:
        time.sleep(1)
        weather = getWeather()

    # make sure each parameter is within the limits for safe observing
    for key in weatherLimits:
        if weather[key] < weatherLimits[key][0] or weather[key] > weatherLimits[key][1]:
            # will this screw up the asynchronous-ness?
            logging.info('Not OK to open: ' + key + '=' + str(weather[key]) + '; Limits are ' + str(weatherLimits[key][0]) + ',' + str(weatherLimits[key][1]))
            retval = False    

    return retval

def connectCamera():

    setTemp = -30
    maxCooling = 50
    maxdiff = 1.0 # maximum allowed difference between setpoint and ccdtemp
    settleTime = 600
    xbin = 1
    ybin = 1
    x1 = 0
    y1 = 0

    # Connect to an instance of Maxim's camera control.
    # (This launches the app if needed)
    logging.info('Connecting to Maxim') 
    cam = Dispatch("MaxIm.CCDCamera")

    # Connect to the camera 
    logging.info('Connecting to camera') 
    cam.LinkEnabled = True

    # Prevent the camera from disconnecting when we exit
    logging.info('Preventing the camera from disconnecting when we exit') 
    cam.DisableAutoShutdown = True

    # If we were responsible for launching Maxim, this prevents
    # Maxim from closing when our application exits
    logging.info('Preventing maxim from closing upon exit')
    maxim = Dispatch("MaxIm.Application")
    maxim.LockApp = True

    # Set binning
    logging.info('Setting binning to ' + str(xbin) + ',' + str(ybin) )
    cam.BinX = xbin
    cam.BinY = ybin

    # Set to full frame
    xsize = cam.CameraXSize
    ysize = cam.CameraYSize
    logging.info('Setting subframe to [' + str(x1) + ':' + str(x1 + xsize -1) + ',' +
                 str(y1) + ':' + str(y1 + ysize -1) + ']')

    cam.StartX = 0 #int((cam.CameraXSize/cam.BinX-CENTER_SUBFRAME_WIDTH)/2)
    cam.StartY = 0 #int((cam.CameraYSize/cam.BinY-CENTER_SUBFRAME_HEIGHT)/2)
    cam.NumX = xsize # CENTER_SUBFRAME_WIDTH
    cam.NumY = ysize # CENTER_SUBFRAME_HEIGHT

    # Set temperature
    weather = -1
    while weather == -1:
        weather = getWeather()
        if weather == -1: time.sleep(1)
        
    if weather['outsideTemp'] > (setTemp + maxCooling):
        logging.error('The outside temperature (' + str(weather['outsideTemp']) + ' is too warm to achieve the set point (' + str(setTemp) + ')')
        return -1

    start = datetime.datetime.utcnow()

    logging.info('Turning cooler on')
    cam.TemperatureSetpoint = setTemp
    cam.CoolerOn = True
    currentTemp = cam.Temperature
    elapsedTime = (datetime.datetime.utcnow() - start).total_seconds()

    # Wait for temperature to settle (timeout of 10 minutes)
    while elapsedTime < settleTime and (abs(setTemp - currentTemp) > maxdiff):    
        logging.info('Current temperature (' + str(currentTemp) + ') not at setpoint (' + str(setTemp) +
                     '); waiting for CCD Temperature to stabilize (Elapsed time: ' + str(elapsedTime) + ' seconds)')
        time.sleep(10)
        currentTemp = cam.Temperature
        elapsedTime = (datetime.datetime.utcnow() - start).total_seconds()

    # Failed to reach setpoint
    if (abs(setTemp - currentTemp)) > maxdiff:
        logging.error('The camera was unable to reach its setpoint (' + str(setTemp) + ') in the elapsed time (' + str(elapsedTime) + ' seconds)')
        return -1

    return cam

#def doBias()

def prepNight():

    dirname = "E:/" + night + "/"
    
    if not os.path.exists(dirname):
        os.makedirs(dirname)

    return dirname

# Returns the next file number given an image directory
def getIndex(dirname):
    files = glob.glob(dirname + "/*.fits")

    return str(len(files)+1).zfill(4)

    if len(files) == 0:
        return '0001'

    lastnum = (files[-1].split('.'))[-2]
    index = str(int(lastnum) + 1).zfill(4)
    return index

def getMean(filename):
    image = pyfits.getdata(filename,0)
    return image.mean()

def doBias(cam, num=11):
    doDark(cam,exptime=0,num=num)

def doDark(cam, exptime=60, num=11):

    DARK = 0
    if exptime == 0:
        objectName = 'Bias'
    else:
        objectName = 'Dark'

    # Take num Dark frames
    for x in range(num):
        logging.info('Taking ' + objectName + ' ' + str(x+1) + ' of ' + str(num) + ' (exptime = ' + str(exptime) + ')')
        takeImage(cam,exptime,'V',objectName)

def doSkyFlat(cam, filters, morning=False, num=11):

    minSunAlt = -12
    maxSunAlt = 0

    biasLevel = 3200
    targetCounts = 10000
    saturation = 15000
    maxExpTime = 60
    minExpTime = 10

    obs = setObserver()
    sun = ephem.Sun()
   
    # can we actually do flats right now?
    if datetime.datetime.now().hour > 12:
        # Sun setting (evening)
        if morning:
            logging.info('Sun setting and morning flats requested; skipping')
            return
        if sunAltitude() < minSunAlt:
            logging.info('Sun setting and already too low; skipping')
            return               
        obs.horizon = str(maxSunAlt)
        flatStartTime = obs.next_setting(sun,start=startNightTime, use_center=True).datetime()
        secondsUntilTwilight = (flatStartTime - datetime.datetime.utcnow()).total_seconds() - 300.0
    else:
        # Sun rising (morning)
        if not morning:
            logging.info('Sun rising and evening flats requested; skipping')
            return
        if sunAltitude() > maxSunAlt:
            logging.info('Sun rising and already too high; skipping')
            return  
        obs.horizon = str(minSunAlt)
        flatStartTime = obs.next_rising(sun,start=startNightTime, use_center=True).datetime()
        secondsUntilTwilight = (flatStartTime - datetime.datetime.utcnow()).total_seconds() - 300.0

    if secondsUntilTwilight > 7200:
        logging.info('Twilight too far away (' + str(secondsUntilTwilight) + " seconds)")
        return

    # wait for twilight
    if secondsUntilTwilight > 0 and (sunAltitude() < minSunAlt or sunAltitude() > maxSunAlt):
        logging.info('Waiting ' +  str(secondsUntilTwilight) + ' seconds until Twilight')
        time.sleep(secondsUntilTwilight)

    # Now it's within 5 minutes of twilight flats
    logging.info('Beginning twilight flats')

    # make sure the telescope/dome is ready for obs
    initializeScope()
    
    # start off with the extreme exposure times
    if morning: exptime = maxExpTime
    else: exptime = minExpTime
  
    # filters ordered from least transmissive to most transmissive
    # flats will be taken in this order (or reverse order in the evening)
    masterfilters = ['H-Beta','H-Alpha','Ha','Y','U','up','zp','zs','B','I','ip','V','rp','R','gp','w','solar','air']
    if not morning: masterfilters.reverse()

    for filterInd in masterfilters:
        if filterInd in filters:

            i = 0
            while i < num:
                
                # Slew to the optimally flat part of the sky (Chromey & Hasselbacher, 1996)
                Alt = 75.0 # degrees (somewhat site dependent)
                Az = sunAzimuth() + 180.0 # degrees
                if Az > 360.0: Az = Az - 360.0
            
                # keep slewing to the optimally flat part of the sky (dithers too)
                logging.info('Slewing to the optimally flat part of the sky (alt=' + str(Alt) + ', az=' + str(Az) + ')')
                mountGotoAltAz(Alt,Az)

                if telescopeInPosition():
                    logging.info("Finished slew to alt=" + str(Alt) + ', az=' + str(Az) + ')')
                else:
                    logging.error("Slew failed to alt=" + str(Alt) + ', az=' + str(Az) + ')')

            
                # Take flat fields
                filename = takeImage(cam, exptime, filterInd, 'SkyFlat')
                
                # determine the mode of the image (mode requires scipy, use mean for now...)
                mode = getMean(filename)
                logging.info("image " + str(i+1) + " of " + str(num) + " in filter " + filterInd + "; " + filename + ": mode = " + str(mode) + " exptime = " + str(exptime) + " sunalt = " + str(sunAltitude()))
                if mode > saturation:
                    # Too much signal
                    logging.info("Flat deleted: exptime=" + str(exptime) + " Mode=" + str(mode) + '; sun altitude=' + str(sunAltitude()) +
                                 "; exptime=" + str(exptime) + '; filter = ' + filterInd)
                    os.remove(filename)
                    i-=1
                    if exptime == minExpTime and morning:
                        logging.info("Exposure time at minimum, image saturated, and getting brighter; skipping remaining exposures in filter " + filterInd)
                        break
                elif mode < 2.0*biasLevel:
                    # Too little signal
                    logging.info("Flat deleted: exptime=" + str(exptime) + " Mode=" + str(mode) + '; sun altitude=' + str(sunAltitude()) +
                                 "; exptime=" + str(exptime) + '; filter = ' + filterInd)
                    os.remove(filename)
                    i -= 1

                    if exptime == maxExpTime and not morning:
                        logging.info("Exposure time at maximum, not enough counts, and getting darker; skipping remaining exposures in filter " + filterInd)
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
                    logging.info("Scaling exptime to " + str(exptime))
                i += 1

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

def initializeScope():
    # Open aqawan
    logging.info('Opening Aqawan')
    openAqawan()

    # turning on mount tracking
    logging.info('Turning mount tracking on')
    mountTrackingOn()
    
    # turning on rotator tracking
    logging.info('Turning rotator tracking on')
    rotatorStartDerotating()

def parseTarget(line):

#    # ---- example to create target file ----
#    target = {
#        'name' : 'M77',
#        'ra' : 2.7113055,
#        'dec':-0.013333,
#        'exptime':[240.0,240.0,240.0],
#        'filter':['B','V','rp'],
#        'num':[5,5,5],
#        'starttime': '2015-01-23 05:00:00',
#        'endtime': '2015-01-24 05:00:00',
#        'selfguide': True,
#        'guide':False,
#        'defocus':0.0,
#        'cycleFilter':True,
#    }
#    with open('list.txt','w') as outfile:
#        json.dump(target,outfile)
#    # --------------------------------------

    target = json.loads(line)

    # convert strings to datetime objects
    target['starttime'] = datetime.datetime.strptime(target['starttime'],'%Y-%m-%d %H:%M:%S')
    target['endtime'] = datetime.datetime.strptime(target['endtime'],'%Y-%m-%d %H:%M:%S')

    return target
    
def telescopeInPosition():
    # Wait for telescope to complete motion
    timeout = 60.0
    start = datetime.datetime.utcnow()
    elapsedTime = 0
    telescopeStatus = getStatus()
    while telescopeStatus.mount.moving == 'True' and elapsedTime < timeout:
        time.sleep(0.1)
        elapsedTime = (datetime.datetime.utcnow() - start).total_seconds()
        telescopeStatus = getStatus()
        
    if telescopeStatus.mount.on_target:
        return True
    else: return False

def acquireTarget(ra,dec):
    initializeScope()
    
    logging.info("Starting slew to J2000 " + str(ra) + ',' + str(dec))
    mountGotoRaDecJ2000(ra,dec)

    if telescopeInPosition():
        logging.info("Finished slew to J2000 " + str(ra) + ',' + str(dec))
    else:
        logging.error("Slew failed to J2000 " + str(ra) + ',' + str(dec))

def doScience(cam, target):

    # if after end time, return
    if datetime.datetime.utcnow() > target['endtime']:
        logging.info("Target " + target['name'] + " past its endtime (" + str(target['endtime']) + "); skipping")
        return

    # if before start time, wait
    if datetime.datetime.utcnow() < target['starttime']:
        waittime = (target['starttime']-datetime.datetime.utcnow()).total_seconds()
        logging.info("Target " + target['name'] + " is before its starttime (" + str(target['starttime']) + "); waiting " + str(waittime) + " seconds")
        time.sleep(waittime)

    # slew to the target
    acquireTarget(target['ra'],target['dec'])

    if target['defocus'] <> 0.0:
        logging.info("Defocusing Telescope by " + str(target['defocus']) + ' mm')
        focuserIncrement(target['defocus']*1000.0)

    # take one in each band, then loop over number (e.g., B,V,R,B,V,R,B,V,R)
    if target['cycleFilter']:
        for i in range(max(target['num'])):
            for j in range(len(target['filter'])):

                # if the enclosure is not open, wait until it is
                while not enclosureOpen():
                    response = openAqawan()
                    if response == -1:
                        logging.info('Enclosure closed; waiting for conditions to improve') 
                        time.sleep(60)
                    if datetime.datetime.utcnow() > target['endtime']: return
                    # reacquire the target
                    if enclosureOpen(): acquireTarget(target['ra'],target['dec'])


                if datetime.datetime.utcnow() > target['endtime']: return
                if i < target['num'][j]:
                        logging.info('Beginning ' + str(i+1) + " of " + str(target['num'][j]) + ": " + str(target['exptime'][j]) + ' second exposure of ' + target['name'] + ' in the ' + target['filter'][j] + ' band') 
                        takeImage(cam, target['exptime'][j], target['filter'][j], target['name'])
                
    else:
        # take all in each band, then loop over filters (e.g., B,B,B,V,V,V,R,R,R) 
        for j in range(len(target['filter'])):
            # cycle by number
            for i in range(target['num'][j]):

                # if the enclosure is not open, wait until it is
                while not enclosureOpen():
                    response = openAqawan()
                    if response == -1:
                        logging.info('Enclosure closed; waiting for conditions to improve') 
                        time.sleep(60)
                    if datetime.datetime.utcnow() > target['endtime']: return
                    # reacquire the target
                    if enclosureOpen(): acquireTarget(target['ra'],target['dec'])
                
                if datetime.datetime.utcnow() > target['endtime']: return
                logging.info('Beginning ' + str(i+1) + " of " + str(target['num'][j]) + ": " + str(target['exptime'][j]) + ' second exposure of ' + target['name'] + ' in the ' + target['filter'][j] + ' band') 
                takeImage(cam, target['exptime'][j], target['filter'][j], target['name'])

def parkScope():
    # park the scope (no danger of pointing at the sun if opened during the day)
    parkAlt = 45.0
    parkAz = 0.0 

    logging.info('Parking telescope (alt=' + str(parkAlt) + ', az=' + str(parkAz) + ')')
    mountGotoAltAz(parkAlt, parkAz)
    telescopeInPosition()

    logging.info('Turning mount tracking off')
    mountTrackingOff()
    
    logging.info('Turning rotator tracking off')
    rotatorStopDerotating()

def compressData(dataPath):
    files = glob.glob(dataPath + "/*.fits")
    for filename in files:
        logging.info('Compressing ' + filename)
        subprocess.call(['cfitsio/fpack.exe','-D',filename])

# upload data to google drive
def backup():

    return

    # Copy to a locally mounted drive
    backupPath = "C:/Users/pwi/Google Drive/data/"
    backupPath = "C:/Users/pwi/data/"

    files = glob.glob("E:/n*/*")

    for filename in files:
        subdir = os.path.basename(os.path.dirname(filename))
        backupdir = os.path.join(backupPath, subdir)
        backupname = os.path.join(backupdir, os.path.basename(filename))

        if not os.path.exists(backupdir):
            os.makedirs(backupdir)        

        if not os.path.isfile(backupname):
            logging.info('Backing up ' + filename + ' to ' + backupname)
            shutil.copy2(filename, backupname)
        ipdb.set_trace()
    return

    # Use the google API to upload directly to google drive
    #***NOT WORKING***
    
    # Copy your credentials from the console
    CLIENT_ID = '297286070394-7ntbvh2bo8tuceot54rnai2m04pv78ba.apps.googleusercontent.com'
    CLIENT_SECRET = '5LXpf9lDaVwrO8tPPF5eKhZ9'

    # Check https://developers.google.com/drive/scopes for all available scopes
    OAUTH_SCOPE = 'https://www.googleapis.com/auth/drive'

    # Redirect URI for installed apps
    REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'

    # Run through the OAuth flow and retrieve credentials
    flow = OAuth2WebServerFlow(CLIENT_ID, CLIENT_SECRET, OAUTH_SCOPE,
                               redirect_uri=REDIRECT_URI)
    authorize_url = flow.step1_get_authorize_url()
    print 'Go to the following link in your browser: ' + authorize_url
    code = raw_input('Enter verification code: ').strip()
    credentials = flow.step2_exchange(code)

    # Create an httplib2.Http object and authorize it with our credentials
    http = httplib2.Http()
    http = credentials.authorize(http)

    drive_service = build('drive', 'v2', http=http)

    files = glob.glob(dataPath + "*.fz")
    for filename in files:
                        
        # Insert a file
        media_body = MediaFileUpload(filename, resumable=True)
        body={'name':filename}

        file = drive_service.files().insert(body=body, media_body=media_body).execute()
        logging.info('Uploaded ' + filename + ' to the google drive')

    return


                        
        
def endNight(dataPath):

    # park the scope
    parkScope()

    # Close the aqawan
    closeAqawan()
    
    # Compress the data
    compressData(dataPath)

    #TODO: Back up the data
#    backup(dataPath)

def autoFocus():

    initializeScope()

    nominalFocus = 25500
    focuserConnect()

    logging.info('Moving to nominal focus (' + str(nominalFocus) + ')')
    focuserMove(nominalFocus) # To get close to reasonable. Probably not a good general postion
    status = getStatus()
    while status.focuser.moving == 'True':
        time.sleep(0.3)
        status = getStatus()

    logging.info('Starting Autofocus')
    startAutoFocus()
    status = getStatus()
    while status.focuser.auto_focus_busy == 'True':
        time.sleep(1)
        status = getStatus()


def getweatherlog():
    from paramiko import SSHClient, AutoAddPolicy
    from scp import SCPClient
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(AutoAddPolicy())
    ssh.load_system_host_keys()
    ssh.connect('192.168.1.2',port=22222,username='minerva',password='!bfthg&*9')

    scp = SCPClient(ssh.get_transport())
    scp.get('/home/minerva/Software/Status/weather_status','./')


if __name__ == '__main__':
    getweatherlog()

    # Prepare for the night (define data directories, etc)
    datapath = prepNight()

    # Start a logger
    logging.basicConfig(filename=datapath + night + '.log', format="%(asctime)s [%(filename)s:%(lineno)s - %(funcName)20s()] %(levelname)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S", level=logging.DEBUG)  
    logging.Formatter.converter = time.gmtime

    # define a Handler which writes INFO messages or higher to the sys.stderr
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
#    # set a format which is simpler for console use
#    formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
#    # tell the handler to use this format
#    console.setFormatter(formatter)
    # add the handler to the root logger
    logging.getLogger('').addHandler(console)

    # run the aqawan heartbeat and weather checking asynchronously
    aqawanThread = threading.Thread(target=aqawan, args=(), kwargs={})
    aqawanThread.start()

    # Connect to the Camera
    cam = connectCamera()
    mountConnect()

    # keep trying to open the aqawan every minute
    # (probably a stupid way of doing this)
    response = -1
    while response == -1:
        response = openAqawan()
        if response == -1: time.sleep(60)

    ipdb.set_trace() # stop execution until we type 'cont' so we can keep the dome open 

    # Want to close the aqawan before darks and biases
    # closeAqawan in endNight just a double check
    closeAqawan()

    endNight(datapath)
    
    # Stop the aqawan thread
    Observing = False
