import urllib2, datetime, time
import telnetlib, socket, os
import threading, sys, logging
from win32com.client import Dispatch
#import ephem

Observing = True

night = 'n' + datetime.datetime.utcnow().strftime('%Y%m%d')
logging.basicConfig(filename=night + '.log', format="%(asctime)s %(levelname)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S", level=logging.DEBUG)
logging.Formatter.converter = time.gmtime

def getWeather():

    # the URL for the machine readable weather page for the Ridge
    url = "http://linmax.sao.arizona.edu/weather/weather.cur_cond"

    # read the webpage
    logging.info('Requesting URL: ' + url)
    request = urllib2.Request(url)
    response =  urllib2.urlopen(request)
    data = response.read().split('\n')
    
    # convert the date into a datetime object
    weather = {
        'date':datetime.datetime.strptime(data[0],'%Y, %m, %d, %H, %M, %S, %f')}
    
    # populate the weather dictionary from the webpage
    for parameter in data[1:-1]:
        weather[(parameter.split('='))[0]] = float((parameter.split('='))[1])
        logging.info(parameter)

#    weather['sunAltitude'] = sunAltitude()

    # make sure all required keys are present
    requiredKeys = ['totalRain', 'wxt510Rain', 'barometer', 'windGustSpeed', 
                    'outsideHumidity', 'outsideDewPt', 'outsideTemp', 
                    'windSpeed', 'windDirectionDegrees', 'date']#, 'sunAltitude']
    for key in requiredKeys:
        if not key in weather.keys():
            # if not, return an error
            logging.error('Weather page does not have all required keys')
            return -1

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
        tn = telnetlib.Telnet(IP,port,1)
    except socket.timeout:
        logging.error('Timeout attempting to connect to the aqawan')
        return -1

    tn.write("vt100\r\n")
    tn.write(message + "\r\n")

    response = tn.read_until(b"/r/n/r/n#>",0.5)
    tn.close()
    return response

    return response.split("=")[1].split()[0]
    return tn.read_all()

    time.sleep(2)

# should do this asychronously and continuously
def aqawan():

    while Observing:            
        logging.info(aqawanCommunicate('HEARTBEAT'))
        if not oktoopen():
            closeAqawan()
        time.sleep(15)
        
def setObserver():
    obs = ephem.Observer()

    # MINERVA latitude/longitude at Mt. Hopkins
    obs.lat = 31.680407 # N
    obs.long = -110.878977 # E

def sunAltitude():

    setObserver()
    sun = ephem.Sun()
    return sun.alt

# TODO: open sequentially with status feedback; test carefully!
def openAqawan():
    return -1
    if oktoopen():
        logging.info(aqawanCommunicate('OPEN_SHUTTERS'))
#        logging.info(aqawanCommunicate('OPEN_SHUTTER_1'))
#        logging.info(aqawanCommunicate('OPEN_SHUTTER_2'))


# TODO: check to make sure it's not closed, then close, error handling
def closeAqawan():
    logging.info(aqawanCommunicate('CLOSE_SEQUENTIAL'))       

def oktoopen():
    retval = True    

    # define the safe limits [min,max] for each weather parameter
    weatherLimits = {
        'totalRain':[0.0,1000.0],
        'wxt510Rain':[0.0,0.0], 
        'barometer':[0,2000], 
        'windGustSpeed':[0.0,30.0], 
        'outsideHumidity':[0.0,75.0], 
        'outsideDewPt':[-20.0,50.0],
        'outsideTemp':[-20.0,50.0], 
        'windSpeed':[0.0,30.0], 
        'windDirectionDegrees':[0.0,360.0],
        'date':[datetime.datetime.utcnow()-datetime.timedelta(minutes=5),datetime.datetime(2200,1,1)],
#        'sunAltitude':[-90,6],
        }

    # get the current weather, timestamp, and Sun's position
    weather = getWeather()

    # make sure each parameter is within the limits for safe observing
    for key in weatherLimits:
        if weather[key] < weatherLimits[key][0] or weather[key] > weatherLimits[key][1]:
            # will this screw up the asynchronous-ness?
            logging.info('Not OK to open: ' + key + '=' + str(weather[key]) + '; Limits are ' + weatherLimits[key][0], weatherLimits[key][1])
            retval = False

    return retval

def connectCamera():

    setTemp = -30
    maxCooling = 50
    settleTime = 600
    xbin = 1
    ybin = 1
    x1 = 0
    y1 = 0

    # Connect to an instance of Maxim's camera control.
    # (This launches the app if needed)
    logging.info('Connecting to Maxim') 
    cam = Dispath("MaxIm.CCDCamera")

    # Connect to the camera 
    logging.info('Connecting to camera') 
    cam.LinkEnabled = True

    # Prevent the camera from disconnecting when we exit
    logging.info('Preventing the camera from disconnecting when we exit') 
    cam.DisableAutoShutdown = True

    # If we were responsible for launching Maxim, this prevents
    # Maxim from closing when our application exits
    logging.info('Preventing maxim from cloing upon exit')
    maxim = Dispatch("MaxIm.Application")
    maxim.LockApp = True

    # Set binning
    logging.info('Setting binning to ' + xbin + ',' + ybin )
    cam.BinX = xbin
    cam.BinY = ybin

    # Set to full frame
    xsize = cam.CameraXSize
    ysize = cam.CameraYSize
    logging.info('Setting subframe to [' + str(x1) + ':' + str(x1 + xsize -1) + ',' +
                 str(y1) + ':' + str(y1 + ysize -1) + ']'

    cam.StartX = 0 #int((cam.CameraXSize/cam.BinX-CENTER_SUBFRAME_WIDTH)/2)
    cam.StartY = 0 #int((cam.CameraYSize/cam.BinY-CENTER_SUBFRAME_HEIGHT)/2)
    cam.NumX = xsize # CENTER_SUBFRAME_WIDTH
    cam.NumY = ysize # CENTER_SUBFRAME_HEIGHT

    # Set temperature
    weather = getWeather()
    if weather['outsideTemp'] > (setTemp + maxCooling):
        logging.error('The outside temperature (' + str(weather['outsideTemp']) + ' is too warm to achieve the set point (' + str(setTemp) + ')'
        return -1

    start = datetime.datetime.utcnow()

    logging.info('Turning cooler on')
    cam.TemperatureSetpoint = setTemp
    cam.CoolerOn = True
    currentTemp = cam.CCDTemp
    elapsedTime = (datetime.datetime.utcnow() - start()).total_seconds()

    # Wait for temperature to settle (timeout of 10 minutes)
    while (elapsedTime < settleTime or abs(setTemp - currentTemp) > 0.5:
        logging.info('Current temperature (' + str(currentTemp) + ') not at setpoint (' + str(setTemp) + '); waiting for CCD Temperature to stabilize (Elapsed time: ' + str(elapsedTime) + ' seconds)')
        time.sleep(10)
        currentTemp = cam.CCDTemp
        elapsedTime = (datetime.datetime.utcnow() - start()).total_seconds()

    # Failed to reach setpoint
    if abs(setTemp - currentTemp):
        logging.error('The camera was unable to reach its setpoint (' + str(setTemp) + ') in the elapsed time (' + str(elapsedTime) + ' seconds)'
        return -1

    return cam


    

if __name__ == '__main__':
    
    # run the aqawan heartbeat and weather checking asynchronously
    aqawanThread = threading.Thread(target=aqawan, args=(), kwargs={})
    aqawanThread.start()

    # Do some other stuff
    print 'hello asynchronous world!'
    time.sleep(30)
    print 'why hello!'

    


    # Stop the aqawan thread
    Observing = False
