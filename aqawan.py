import urllib2, datetime
import telnetlib
import time
import threading

Observing = True

def getWeather():

    # the URL for the machine readable weather page for the Ridge
    url = "http://linmax.sao.arizona.edu/weather/weather.cur_cond"

    # read the webpage
    request = urllib2.Request(url)
    response =  urllib2.urlopen(request)
    data = response.read().split('\n')
    
    # convert the date into a datetime object
    weather = {
        'date':datetime.datetime.strptime(data[0],'%Y, %m, %d, %H, %M, %S, %f')}

    # populate the weather dictionary from the webpage
    for parameter in data[1:-1]:
        weather[(parameter.split('='))[0]] = float((parameter.split('='))[1])

    # make sure all required keys are present
    requiredKeys = ['totalRain', 'wxt510Rain', 'barometer', 'windGustSpeed', 
                    'outsideHumidity', 'outsideDewPt', 'outsideTemp', 
                    'windSpeed', 'windDirectionDegrees', 'date']
    for key in requiredKeys:
        if not key in weather.keys():
            # if not, return an error
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
        return -1

    IP = '192.168.1.14'
    port = 22004
    tn = telnetlib.Telnet(IP,port,1)

    tn.write("vt100\r\n")
    tn.write(message + "\r\n")

    response = tn.read_until(b"/r/n/r/n#>",0.5)
    return response

    return response.split("=")[1].split()[0]
    return tn.read_all()

    time.sleep(2)

# should do this asychronously and continuously
def aqawan():

    while Observing:            
        print aqawanCommunicate('HEARTBEAT')
        if not oktoopen():
            print aqawanCommunicate('CLOSE_SEQUENTIAL')
        time.sleep(15)
        
def oktoopen():
    # define the safe limits [min,max] for each weather parameter
    weatherLimits = {
        'totalRain':[0.0,0.0],
        'wxt510Rain':[0.0,0.0], 
        'barometer':[0,2000], 
        'windGustSpeed':[0.0,30.0], 
        'outsideHumidity':[0.0,75.0], 
        'outsideDewPt':[-20.0,50.0],
        'outsideTemp':[-20.0,50.0], 
        'windSpeed':[0.0,30.0], 
        'windDirectionDegrees':[0.0,360.0],
        'date':[datetime.datetime.utcnow()-datetime.timedelta(minutes=5),datetime.datetime(2200,1,1)]
        }

    retval = True
    
    weather = getWeather()
    for key in weatherLimits:
        if weather[key] < weatherLimits[key][0] or weather[key] > weatherLimits[key][1]:
            # should print to a log
            print key + '=' + str(weather[key]), '; Limits are', weatherLimits[key][0], weatherLimits[key][1], '; not ok to open!'
            retval = False

    return retval

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
