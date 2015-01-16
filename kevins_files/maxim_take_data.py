import os
import time

from win32com.client import Dispatch


EXP_LENGTHS = [1, 2, 3, 4, 5, 6]
NUM_EXPOSURE_PAIRS = 1
CENTER_SUBFRAME_WIDTH = 300
CENTER_SUBFRAME_HEIGHT = 300

# Connect to an instance of Maxim's camera control.
# (This launches the app if needd)
cam = Dispatch("MaxIm.CCDCamera")

# Connect to the camera
cam.LinkEnabled = True

# Prevent the camera from disconnecting when we exit
cam.DisableAutoShutdown = True

# If we were responsible for launching Maxim, this prevents
# Maxim from closing when our application exits
maxim = Dispatch("MaxIm.Application")
maxim.LockApp = True


# Set binning
cam.BinX = 2
cam.BinY = 2

# Set subframe
cam.StartX = int((cam.CameraXSize/cam.BinX-CENTER_SUBFRAME_WIDTH)/2)
cam.StartY = int((cam.CameraYSize/cam.BinY-CENTER_SUBFRAME_HEIGHT)/2)
cam.NumX = CENTER_SUBFRAME_WIDTH
cam.NumY = CENTER_SUBFRAME_HEIGHT


# Take exposures and save images
for expPair in range(NUM_EXPOSURE_PAIRS):
    for expLength in EXP_LENGTHS:
        for pairNum in (0, 1):
            expNum = (2*expPair + pairNum) + 1
            filename = "Lights-%03d_%02d.fit" % (expNum, int(expLength*10))
            print "Exposing", filename, "(expPair=%d, pairNum=%d, expNum=%d, expLength=%.2f)" % (
                    expPair, pairNum, expNum, expLength)

            cam.Expose(expLength, 1)
            while not cam.ImageReady:
                time.sleep(0.1)

            image = cam.Document
            maxPixel, minPixel, average, stddev = image.CalcAreaInfo(0, 0, image.XSize-1, image.YSize-1)
            print "Average: %.2f, StdDev: %.2f" % (average, stddev)

            filePath = os.path.join(os.getcwd(), filename)
            cam.SaveImage(filePath)


