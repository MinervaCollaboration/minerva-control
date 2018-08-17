###This is a code meant to check weather and sun position to see if the dome
###should be open or not. Uses observing condition cutoffs from main minerva code

import ephem, time
from win32com.client import Dispatch 
import should_be_open

##Here, we define the location of he MINERVA telescope, used for calculating 
##locations, etc.

hopkins = ephem.Observer()
hopkins.lon='-110:52:44.6'
hopkins.lat='31:40:49.4'
hopkins.elevation= 2345.

dome=Dispatch("ascom.astrohavenpw.dome")
dome.Connected=True

i=0.

##This will run like a loop. Check a bunch of things, see if the telescope 
##should be open open or closed, take action.
while i == 0:
    hopkins.date=ephem.now()
    Sun=ephem.Sun(hopkins)
    sunalt=(float(repr(Sun.alt)))*57.3
    
#Dome shojuld be closed if Sun is more than -5, let's say. 
#This loop checks to make sure that the dome is closed, and if it isn't
#closes. Check and seems to work.  
    if  sunalt >= -5.0:
        domestatus=dome.ShutterStatus
#domestatus = 1 is closed, 0 is open        
        if domestatus == 1:
            print "Sun is UP, dome should be CLOSED, it is Closed"
            time.sleep(30)
            continue
  
        if domestatus ==  0:
            print "Sun is UP, dome should be CLOSED, it is OPEN, CLOSING now"    
            dome= Dispatch("ascom.astrohavenpw.dome")   
            dome.CloseShutter()
            time.sleep(60)
            dome.CloseShutter()
            time.sleep(30)
            continue
                                    
#Now, let's start the logic for the Sun being down

    if sunalt < -3.0:
#First, we have to check the weather            
        domestatus=dome.ShutterStatus
        isgood = should_be_open.should_be_open()       
            
 #First do bad weather logic     
 #When it comes to bad weather closuers, we want to wait 20 minutes, I think to check again 
        if isgood == False:     
            if domestatus == 1:
                print "Sun is DOWN, weather is BAD, dome should be CLOSED, it is Closed, WAITING 20"
                time.sleep(1200)
                continue
#now do bad weather dome open logic  
            if domestatus ==  0:
                print "Sun is DOWN, weather is BAD, dome should be CLOSED, it is OPEN, CLOSING now, WAITING 20"          
                dome.CloseShutter()
                time.sleep(60)
                dome.CloseShutter()
                time.sleep(1200)
                continue

#now do good weather logic       
        if isgood == True:
            
            if domestatus == 0:
                 print "Sun is DOWN, weather is GOOD, dome should be OPEN, it is open"
                 time.sleep(30)
                 continue
           
            if domestatus ==1:
                print "Sun is DOWN, weather is GOOD, dome should be OPEN, it is CLOSED, opening now"
                dome.OpenShutter()
                time.sleep(30)
                dome.OpenShutter()
                time.sleep(30)  
                continue         
                       
                              
            



