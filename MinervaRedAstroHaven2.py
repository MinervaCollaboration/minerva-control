# -*- coding: utf-8 -*-
import cgi
import cgitb; 
cgitb.enable()  
import math
import time
import datetime
import urllib2
import serial 
import string
import site 

"""Display an html in the local default browser"""
 
def fileToStr(fileName): 
    """Return a string containing the contents of the named file."""
    fin = open(fileName); 
    contents = fin.read();  
    fin.close() 
    return contents

def strToFile(text, filename):
    """Write a file with the given name and the given text."""
    output = open(filename,"w")
    output.write(text)
    output.close()

def RH_Temp(port, baud):
    """Open a serial connection with the arduino connected to the specified 
    port and return the list of data"""
#Boolean to represent whether arduino is connected 
    connected = False
    
#Open a connection to the serial port. This resets the arduino and makes the 
#LED flash once. 
    ser = serial.Serial(port, baud)
 
#Allow the arduino some time to initialize before requesting information
    time.sleep(1.5)

    hexcode="\x49" #this is the proper formatting for the C9 hex command to 
                   #send over the serial line

#This starts an infinite loop that reads the humidity, temp, and heat index 
#every 5 seconds  
    while not connected: 
    
#send a request for the data
        ser.write(hexcode)
    
#listen for a 10 byte response
        time.sleep(0.25)
        out=ser.read(size=10)
        #print out
    
#Relative humidity is the first 5 bytes recieved, celcius temp is last 5.  
#This order is determined by the arduino code that was uploaded to the board.  
        RH = float(out[:5])
        #print "humidity is a: " , type(RH)
        T = float(out[5:])
        #print "tempc is a: " , type(T)
        
#Calculate the dew point and dew point depression. Here gamma is a function of
#the relative humidity and the temperature and 'P' is the actual water vapor
#pressure: 
        gamma = math.log(RH / 100) + (17.67 * T / (243.5 + T))
        P = 6.112 * (math.exp(gamma))
        #dew point:
        dew_point = round((243.5*(math.log(P/6.112)))/(17.67 - (math.log(P/6.112))),1)
        #dew point depression:
        dew_point_dep = round(T - dew_point,1)
        
        
#create an array that holds the data:  
#[temperature, relative humidity, dew point, dew point depression] 
        data = [T, RH, dew_point, dew_point_dep]
        
        #print data
        
        connected = False
        time.sleep(2)
        break 
        
    ser.close()
    
#return the data
    return data
    
def Dome(port, baud, force_closed = 350):
    
#Boolean to represent whether arduino is connected 
    connected = False
    
#Open a connection to the serial port. This resets the arduino and makes the 
#LED flash once. 
    ser = serial.Serial(port, baud)
 
#Allow the arduino some time to initialize before requesting information
    time.sleep(1.5)

    hexcode="\x49" #this is the proper formatting for the C9 hex command to 
                   #send over the serial line

#This starts an infinite loop that reads the humidity, temp, and heat index 
#every 5 seconds  
    while not connected: 
    
#send a request for the data
        ser.write(hexcode)
        
#listen for a 7 byte response (depends on arduino code)
        #time.sleep(0.25)
        out=ser.read(size=8)
        print out
        
#Resistance is the first 6 bytes recieved, and the applied force is the last 6
#this depends on the arduino code that was uploaded to the board
        #Rfsr = float(out[:6])
        #print "Rfsr is a: " , type(Rfsr)
        #Force = float(out[6:])
        #print "Force is a: " type(Force)
        Force = float(out) 
        
        dome_status = ""
        
        if Force <= force_closed:
            dome_status = "Astro haven is closed"
        else:
            dome_status = "Astro haven is not closed"
        
        #print dome_status
         
        connected = False
        time.sleep(2)
        break
        
    ser.close()

#return the status of the dome     
    return dome_status

def browseLocal(webpageText, filename='tempBrowseLocal.html'):
    '''Start your webbrowser on a local file containing the text
    with given filename.'''
    import webbrowser, os.path
    strToFile(webpageText, filename)
    webbrowser.open_new("file:///" + os.path.abspath(filename)) #elaborated for Mac

def main():
    browseLocal(contents)

#get the current weather conditions in Santa Cruz from the following website and 
#process the information to be inserted into the html code  
url = "http://linmax.sao.arizona.edu/weather/weather.cur_cond"
response = urllib2.urlopen(url)
output = response.read()
weather = string.split(output, '\n')
print weather
#print output
currmttime = weather[0][:4]+'-'+weather[0][6:8]+'-'+weather[0][10:12]+' '+weather[0][22:24]+':'+weather[0][18:20]+':'+weather[0][14:16]+'.'+weather[0][26:]
mttemp = weather[1][12:]
windspeed = weather[2][10:]
gustspeed = weather[3][14:]
windDir = weather[4][21:]
barometer = weather[5][10:]
outHum = weather[6][16:]
wxt510Rain = weather[7][11:]
totalRain = weather[8][10:]
outDewPt = weather[9][13:]
outDPD = str(float(mttemp)-float(outDewPt))

#Determines if the shell can be opened/ should be closed
boolean = site.oktoopen()
if float(outDPD) > 3.0 and boolean:
    permission = "Astro haven is okay to open"
    color = "rgb(51, 204, 0)" 
else: 
    permission = "Astro haven should be closed"
    color = "red" 

#call the function to get temperature and humidity inside the astro haven
datastr = RH_Temp("COM3", 9600)
temp = str(datastr[0])
rh = str(datastr[1])
dp = str(datastr[2])
dpd = str(datastr[3])

rectime = datetime.datetime.now() #gets a timestamp for the data received 

#call the function to get whether the dome is open or closed 
forceOne = Dome("COM4", 9600)
forceTwo = Dome("COM18", 9600)

#check to make sure the two pressure sensors agree on the status of the dome

if forceOne != forceTwo:
    message = "Sensors do not agree on the astro haven's status."
else:
    message = forceOne

#html file 
contents ='''<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>
<head>
  <meta content="text/html; charset=ISO-8859-1"
 http-equiv="content-type">
  <title>Minerva-Red</title>
</head>
<body>
<div style="color: rgb(0, 0, 153);" class="jumbotron">
<div class="container">
<h1 style="text-align: center;">Minerva-Red Telescope</h1>
</div>
</div>
<div class="dome-live-feed">
<h2 style="color: rgb(0, 0, 153);">Live
feed</h2>
<div style="text-align: left;"><img
 style="width: 45%; height: 400px;" alt="Inside astro haven"
 src="../Pictures/Minera-Red%2520FULLv2.jpg" hspace="20"><img
 style="width: 45%; height: 400px;" alt="Mt Hopkins site"
 src="../Pictures/image_mini.jpg" hspace="20"></div>
</div>
<div class="local-weather">
<h2 style="color: rgb(0, 0, 153);">Weather conditions on
Mount Hopkins</h2>
<div style="text-align: center;">
<table
 style="width: 60%; text-align: left; margin-left: auto; margin-right: auto;"
 border="1" cellpadding="2" cellspacing="2">
  <tbody>
    <tr>
      <td style="text-align: center;">Recording time (MT)</td>
      <td style="text-align: center;">{5}</td>
    </tr>
    <tr>
      <td style="text-align: center;">Temperature</td>
      <td style="text-align: center;">{6} C</td>
    </tr>
    <tr>
      <td style="text-align: center;">Wind speed</td>
      <td style="text-align: center;">{7} m/s</td>
    </tr>
    <tr>
      <td style="text-align: center;">Wind gust speed</td>
      <td style="text-align: center;">{8} m/s</td>
    </tr>
    <tr>
      <td style="text-align: center;">Wind direction</td>
      <td style="text-align: center;">{9} degrees</td>
    </tr>
    <tr>
      <td style="text-align: center;">Barometric pressure</td>
      <td style="text-align: center;">{10} hPa</td>
    </tr>
    <tr>
      <td style="text-align: center;">Relative humidity</td>
      <td style="text-align: center;">{11} %</td>
    </tr>
    <tr>
      <td style="text-align: center;">Rainfall (since last
reset)</td>
      <td style="text-align: center;">{12}</td>
    </tr>
    <tr>
      <td style="text-align: center;">Total rainfall</td>
      <td style="text-align: center;">{13}</td>
    </tr>
    <tr>
      <td style="text-align: center;">Dew point</td>
      <td style="text-align: center;">{14} C</td>
    </tr>
    <tr>
      <td style="text-align: center;">Dew point depression</td>
      <td style="text-align: center;">{17} C</td>
    </tr>
  </tbody>
</table>
<br>
</div>
</div>
<div class="astrohaven-status">
<h2 style="color: rgb(0, 0, 153);">Status of the astro
haven</h2>
<p style="text-align: center; font-weight: bold; color: {15};"><big>{16}</big></p>
<p style="text-align: center; font-weight: bold; color: rgb(0, 0, 153);"><big> {18} </big></p>
<table
 style="width: 60%; text-align: left; margin-left: auto; margin-right: auto;"
 border="1" cellpadding="2" cellspacing="2">
  <tbody>
    <tr>
      <td style="text-align: center;">Temperature</td>
      <td style="text-align: center;">{0} C</td>
    </tr>
    <tr>
      <td style="text-align: center;">Relative Humidity</td>
      <td style="text-align: center;">{1} %</td>
    </tr>
    <tr>
      <td style="text-align: center;">Dew point</td>
      <td style="text-align: center;">{2} C</td>
    </tr>
    <tr>
      <td style="text-align: center;">Dew point depression</td>
      <td style="text-align: center;">{3} C</td>
    </tr>
    <tr>
      <td style="text-align: center;">Recording time (MT)</td>
      <td style="text-align: center;">{4}</td>
    </tr>
  </tbody>
</table>
<br>
</div>
</body>
</html>
'''.format(temp,rh,dp,dpd,rectime,currmttime,mttemp,windspeed,gustspeed,windDir,barometer,outHum,wxt510Rain,totalRain,outDewPt,color,permission,outDPD,message)

main()
