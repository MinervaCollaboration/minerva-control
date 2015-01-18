import urllib2, datetime
import socket
import time
import threading

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

    messages = ['HEARTBEAT','STOP','OPEN_SHUTTERS','CLOSE_SHUTTERS','CLOSE_SEQUENTIAL','OPEN_SHUTTER_1','CLOSE_SHUTTER_1','OPEN_SHUTTER_2','CLOSE_SHUTTER_2','LIGHTS_ON','LIGHTS_OFF','ENC_FANS_HI','ENC_FANS_MED','ENC_FANS_LOW','ENC_FANS_OFF','PANEL_LED_GREEN','PANEL_LED_YELLOW','PANEL_LED_RED','PANEL_LED_OFF','DOOR_LED_GREEN','DOOR_LED_YELLOW','DOOR_LED_RED','DOOR_LED_OFF','SON_ALERT_ON','SON_ALERT_OFF','LED_STEADY','LED_BLINK','MCB_RESET_POLE_FANS','MCB_RESET_TAIL_FANS','MCB_RESET_OTA_BLOWER','MCB_RESET_PANEL_FANS','MCB_TRIP_POLE_FANS','MCB_TRIP_TAIL_FANS','MCB_TRIP_PANEL_FANS','STATUS','GET_ERRORS','GET_FAULTS','CLEAR_ERRORS','CLEAR_FAULTS','RESET_PAC']

    # not an allowed message
    if not message in messages:
        return -1

    TCP_IP = '127.0.0.1'
    TCP_PORT = 23
    BUFFER_SIZE = 1024
    
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((TCP_IP, TCP_PORT))
    s.send(message)
    data = s.recv(BUFFER_SIZE)
    s.close()
    return data

# should do this asychronously and continuously
def aqawan():

    while True:            
#        aqawanCommunicate('HEARTBEAT')
        if not oktoopen():
#            aqawanCommunicate('CLOSE_SEQUENTIAL')
            print 'ldjf'
        time.sleep(5)
        return

        
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
    aqawanthread = threading.Thread(target=aqawan, args=(), kwargs={})
    aqawanthread.start()



    print 'hello asynchronous world!'
    time.sleep(10)
    print 'why hello!'
    

    
    
