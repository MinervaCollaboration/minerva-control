from configobj import ConfigObj
from scp import SCPClient
from win32com.client import Dispatch
from scipy import stats
import numpy as np
import os,sys,glob, socket, logging, datetime, ipdb, time, json, threading, pyfits, subprocess, collections
import atexit, win32api

# full API at http://www.cyanogen.com/help/maximdl/MaxIm-DL.htm#Scripting.html

# Connect to an instance of Maxim's camera control.
# (This launches the app if needed)
cam = Dispatch("MaxIm.CCDCamera")

# Connect to the camera 
cam.LinkEnabled = True

# Prevent the camera from disconnecting when we exit
cam.DisableAutoShutdown = True

# If we were responsible for launching Maxim, this prevents
# Maxim from closing when our application exits
maxim = Dispatch("MaxIm.Application")
maxim.LockApp = True

#S Turn on the cooler so we don't hit any issues with self.safe_close
cam.CoolerOn = True

cam.GuiderExpose(1.0)
print cam.CameraName
print cam.GuiderName


t0 = datetime.datetime.utcnow()
while cam.GuiderRunning:
        time.sleep(0.1)
print (datetime.datetime.utcnow() - t0).total_seconds()

#allDocs = Dispatch('MaxIm.Document')
#allDocs = maxim.Documents

print maxim.CurrentDocument.SaveFile('C:/minerva/test/test4.fits',3, False, 1)

ipdb.set_trace()


ipdb.set_trace()
for doc in allDocs:
        print doc


image = cam.ImageArray()

ipdb.set_trace()
	
	
	
	
