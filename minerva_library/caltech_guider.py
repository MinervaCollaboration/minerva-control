######## caltech_guider.py ###############################

# Import the COM interfacing library
from win32com.client import Dispatch

import time  # Includes the sleep() function
import math  # Trig functions, etc
import sys   # sys.exit() and other misc functions


##### CONFIGURATION PARAMETERS #####

# Configure the reference pixel coordinates where the fiber will be located
FIBER_X = 128
FIBER_Y = 128

# When doing initial/approximate centering, star must be within
# this many pixels before we star to subframe and do precise guiding
ROUGH_TOLERANCE_PIXELS = 800.0

# Star must be within this many pixels of target to be on the fiber
FIBER_TOLERANCE_PIXELS = 1.0

# Guide exposure length
EXPOSURE_LENGTH_SECONDS = 1

# Do we want to recalibrate the guider orientation each time?
PERFORM_CALIBRATION = False

##### END OF CONFIGURATION PARAMETERS #####


def main():
    """
    When called as a script, code starts running here.
    This assumes that you are already pointed at a bright star
    and it is visible in the CCD field.
    """

    # Create an instance of our Star Targeter tool
    starTargeter = StarTargetTool()

    # Connect to Maxim and perform basic setup
    starTargeter.connect()


    # Calibrate the autoguider orientation and scale if requested
    if PERFORM_CALIBRATION:
        starTargeter.calibrateAutoGuider(EXPOSURE_LENGTH_SECONDS) 

    # When autoguiding, Maxim normally creats a tiny subframe around
    # the target star. Since our star may be hundreds of pixels off
    # from the desired fiber position, first call this routine to
    # take some full-frame exposures and perform coarse adjustments
    # to get the star near the target
    starCenteredSuccessfully = starTargeter.findStarAndMoveToTarget(EXPOSURE_LENGTH_SECONDS, FIBER_X, FIBER_Y, ROUGH_TOLERANCE_PIXELS, maxIterations=5)

    if starCenteredSuccessfully:
        # Use Maxim's built-in star tracking routine to
        # accurately position the star and keep it
        # on target
        starTargeter.subframeAndKeepStarOnTarget(EXPOSURE_LENGTH_SECONDS, FIBER_X, FIBER_Y, ROUGH_TOLERANCE_PIXELS)
    else:
        print "STAR CENTERING FAILED"


class StarTargetTool:
    def connect(self):
        """
        Establish a connection to Maxim and the guide camera.
        Call this method first before doing anything else
        """

        # Obtain a reference to a Maxim DL CCDCamera object.
        # See the Maxim DL Help file under "Scripting" for more details.
        print "Loading Maxim DL..."
        self.camera = Dispatch("MaxIm.CCDCamera")

        print "Connecting to cameras..."
        self.camera.LinkEnabled = True
        self.camera.DisableAutoShutdown = True

        # Tell Maxim to automatically identify the brightest star in the 
        # guider's field when taking an exposure
        self.camera.GuiderAutoSelectStar = True

    def calibrateAutoGuider(self, exposureLengthSeconds):
        """
        Run a routine in Maxim to identify a bright star and issue
        a series of movements to establish a relationship between
        RA/Dec and the CCD frame
        """

        print "Calibrating autoguider orientation..."
        self.camera.GuiderCalibrate(exposureLengthSeconds)
        while self.camera.GuiderRunning:
            sys.stdout.write(".")
            time.sleep(1)
        print
        print "Calibration finished"


    def findStarAndMoveToTarget(self, exposureLengthSeconds, targetPixelX, targetPixelY, tolerancePixels, maxIterations=5):
        """
        Assuming that Maxim has a valid set of autoguider parameters
        (e.g. following a call to calibrateAutoGuider), take a series
        of full-frame images, identify the brightest star, and issue
        autoguider commands to move the star to approximately
        the specified X and Y pixel position. The procedure will
        iterate until the star is within some specified tolerance.

        If the procedure has iterated too many times without the star 
        converging on the target, return False to indicate failure.
        Otherwise, return True to indicate success.
        """

        for iteration in range(1, maxIterations+1):
            print "Attempting to roughly center brightest star (iteration %d of %d)..." % (iteration, maxIterations)

            print "  Exposing guider to find star"
            self.camera.GuiderExpose(exposureLengthSeconds)

            # Poll the guider until the image is ready
            while self.camera.GuiderRunning:
                time.sleep(0.1) # Wait 100 milliseconds before asking again

            print "  Exposure complete"
            print "  Guide star found at pixel (%.2f, %.2f)" % (self.camera.GuiderXStarPosition, self.camera.GuiderYStarPosition)

            # Calculate how far off we are in X and Y pixels
            targetErrorXPixels = self.camera.GuiderXStarPosition - targetPixelX
            targetErrorYPixels = self.camera.GuiderYStarPosition - targetPixelY

            print "  Pointing error: X = %.2f pixels, Y = %.2f pixels" % (targetErrorXPixels, targetErrorYPixels)

            # Are we close enough to consider the procedure complete?
            if targetErrorXPixels < tolerancePixels and targetErrorYPixels < tolerancePixels:
                print "Star is on target (within %.2f-pixel tolerance)" % tolerancePixels
                return True


            # Need to make an adjustment. Transform error from pixel 
            # coordinates to guider coordinates
            guiderAngleRads = math.radians(self.camera.GuiderAngle)

            guiderErrorX = targetErrorXPixels*math.cos(guiderAngleRads) - targetErrorYPixels*math.sin(guiderAngleRads)
            guiderErrorY = targetErrorXPixels*math.sin(guiderAngleRads) + targetErrorYPixels*math.cos(guiderAngleRads)
            
            # GuiderXSpeed and GuiderYSpeed are in pixels per second
            guideDurationX = float(guiderErrorX) / self.camera.GuiderXSpeed
            guideDurationY = float(guiderErrorY) / self.camera.GuiderYSpeed

            # Convert +/- guide durations into direction code and positive duration

            if guideDurationX > 0:
                xSign = "+"
                xDirection = 0 # Positive X direction
            else:
                xSign = "-"
                xDirection = 1 # Negative X direction
                guideDurationX = -guideDurationX

            if guideDurationY > 0:
                ySign = "+"
                yDirection = 2 # Positive Y direction
            else:
                ySign = "-"
                yDirection = 3 # Negative Y direction
                guideDurationY = -guideDurationY


            # Make the X guider adjustment if necessary
            if guideDurationX > 0:
                print "  Moving in %sX for %f sec..." % (xSign, guideDurationX)
                self.camera.GuiderMove(xDirection, guideDurationX)
                while self.camera.GuiderMoving:
                    time.sleep(0.1)

            # Make the Y guider adjustment if necessary
            if guideDurationY > 0:
                print "  Moving in %sY for %f sec..." % (ySign, guideDurationY)
                self.camera.GuiderMove(yDirection, guideDurationY)
                while self.camera.GuiderMoving:
                    time.sleep(0.1)

            print "  Guide adjustment finished"
            # Loop again to see if we are on target

        print "DID NOT CONVERGE AFTER %d ITERATIONS" % maxIterations
        return False

    def subframeAndKeepStarOnTarget(self, exposureLengthSeconds, targetPixelX, targetPixelY, tolerancePixels):
        """
        Once a star is near the target pixel, call this method to use
        Maxim's autoguider tracking routine to subframe around the
        star and make adjustments to maintain the star's position
        on the target pixel.
        """

        # Set the target pixel position that the autoguider tracking
        # routine will try to achieve
        self.camera.GuiderMoveStar(targetPixelX, targetPixelY)

        print "Begin tracking with guider..."
        self.camera.GuiderTrack(EXPOSURE_LENGTH_SECONDS)

        # Run Maxim's guider routine in a continuous tracking loop until either 
        # GuiderStop() is called, somebody clicks the Stop button in Maxim,
        # or the script is aborted
        while self.camera.GuiderRunning:
            if self.camera.GuiderNewMeasurement:
                message = ""
                if abs(self.camera.GuiderXError) < tolerancePixels and abs(self.camera.GuiderYError) < tolerancePixels:
                    message = "STAR IS ON THE FIBER"
                print "Guide star position error: %.2f, %.2f %s" % (self.camera.GuiderXError, self.camera.GuiderYError, message)
            time.sleep(0.1)



if __name__ == "__main__":
    try:
        main()
    finally:
        print
        raw_input("Press Enter to continue...")
