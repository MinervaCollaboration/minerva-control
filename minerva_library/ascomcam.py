import numpy as np
import win32com.client
from astropy.io import fits
import datetime, time
import ipdb

class ascomcam:

	def __init__(self, config, base='', driver=None):


                self.base_directory = base

                # if you don't know what your driver is called, use the ASCOM Chooser
                # this will give you a GUI to select it
		if driver==None:
                        x = win32com.client.Dispatch("ASCOM.Utilities.Chooser")
                        x.DeviceType = 'Camera'
                        driver = x.Choose(None)
                        print("The driver is " + driver)

		# initialize the camera
		self.camera = win32com.client.Dispatch(driver)

		today = datetime.datetime.utcnow()
                if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
                        today = today + datetime.timedelta(days=1)
                self.night = 'n' + today.strftime('%Y%m%d')

        def initialize(self):
                self.connect()
                self.cool()
                self.setROI(fullFrame=True)
                self.setBin(1)

	def connect(self):
                self.camera.connected = True
                return self.camera.connected


	def get_temperature(self):
		return self.camera.CCDTemperature

	def cool(self, temp=None, wait=False, settleTime=1200.0, oscillationTime=120.0, maxdiff = 1.0):
                if not self.camera.CanSetCCDTemperature:
                        self.logger.error("Camera cannot cool")
                        return False
                
                if temp != None:
                        self.camera.SetCCDTemperature = temp
                       
                self.camera.CoolerOn = True

                if not wait: return

                t0 = datetime.datetime.utcnow()
                elapsedTime = (datetime.datetime.utcnow() - t0).total_seconds()
                lastTimeNotAtTemp = datetime.datetime.utcnow() - datetime.timedelta(seconds=oscillationTime)
                elapsedTimeAtTemp = oscillationTime
                currentTemp = self.camera.CCDTemperature
                setTemp = self.camera.SetCCDTemperature

                while elapsedTime < settleTime and ((abs(setTemp - currentTemp) > maxdiff) or elapsedTimeAtTemp < oscillationTime):
                        self.logger.info('Current temperature (' + str(currentTemp) +
                                         ') not at setpoint (' + str(setTemp) +
                                         '); waiting for CCD Temperature to stabilize (Elapsed time: '
                                         + str(elapsedTime) + ' seconds)')

			# has to maintain temp within range for 1 minute
			if (abs(setTemp - currentTemp) > self.maxdiff):
                                lastTimeNotAtTemp = datetime.datetime.utcnow()
			elapsedTimeAtTemp = (datetime.datetime.utcnow() - lastTimeNotAtTemp).total_seconds()

                        time.sleep(10)
			#S update the temperature
                        currentTemp = self.camera.CCDTemperature
                        elapsedTime = (datetime.datetime.utcnow() - start).total_seconds()

                        
                # Failed to reach setpoint
                if (abs(setTemp - currentTemp)) > maxdiff:
                        self.logger.error('The camera was unable to reach its setpoint (' +
                                          str(setTemp) + ') in the elapsed time (' +
                                          str(elapsedTime) + ' seconds)')
                        return False

                return True

        def setBin(self,xbin,ybin=None):
                if ybin==None: ybin=xbin

                # if asymmetric binning requested, make sure we can do that
                if xbin != ybin:
                        if not self.camera.CanAsymmetricBin:
                                self.logger.error('The camera cannot bin asymmetrically')
                                return False
                
                self.camera.BinX = xbin
                self.camera.BinY = ybin
                self.xbin = xbin
                self.ybin = ybin
		return True

        def set_roi(self, x1=None, x2=None, y1=None, y2=None, fullFrame=False):

                if fullFrame:
                        x1 = 1
                        x2 = self.camera.CameraXSize
                        y1 = 1
                        y2 = self.camera.CameraYSize

                if x1 != None: self.camera.StartX = x1
                else: x1 = self.camera.StartX
                self.x1 = x1

                if x2 != None: self.camera.NumX = x2-x1
                else: x2 = self.camera.StartX+x1
                self.x2 = x2

                if y1 != None: self.camera.StartY = y1
                else: y1 = self.camera.StartY
                self.y1 = y1
                
                if y2 != None: self.camera.NumY = y2-y1
                else: y2 = self.camera.StartY+y1
                self.y2 = y2
                return True

        def save_image(self,filename, timeout=10, hdr=None, overwrite=False):

                t0 = datetime.datetime.utcnow()
                elapsedTime = (t0 - datetime.datetime.utcnow()).total_seconds()
                while elapsedTime < timeout and not self.camera.ImageReady:
                        time.sleep(0.05)
                        elapsedTime = (t0 - datetime.datetime.utcnow()).total_seconds()

                if not self.camera.ImageReady: return False

                if hdr == None: hdr = fits.Header()
                hdr['DATE-OBS'] = (self.dateobs.strftime('%Y-%m-%dT%H:%M:%S.%f'),'Observation start, UTC')
                hdr['EXPTIME'] = (self.exptime,'Exposure time in seconds')
                hdr['CCDSUM'] = (str(self.xbin) + ' ' + str(self.ybin),'CCD on-chip binning')
                datasec = '[' + str(self.x1) + ':' + str(self.x2) + ',' + str(self.y1) + ':' + str(self.y2) + ']'
                hdr['DATASEC'] = (datasec, 'Region of CCD read')
                hdr['CCDTEMP'] = (self.camera.CCDTemperature,'CCD Temperature (C)')
                hdr['SETTEMP'] = (self.camera.SetCCDTemperature,'CCD Set Temperature (C)')
                #hdr['GAIN'] = (self.camera.ElectronsPerADU,'Gain (e/ADU)')
                
                hdu = fits.PrimaryHDU(self.camera.ImageArray, header=hdr)
                hdu.writeto(filename, overwrite=overwrite)
                return True

        def expose(self,exptime, openShutter=True):
                self.exptime = exptime
                self.dateobs = datetime.datetime.utcnow()
                self.camera.StartExposure(exptime,openShutter)


if __name__ == '__main__':

        config_file = ''
        base_directory = ''
        camera = ascomcam(config_file, base_directory, driver="ASCOM.AtikCameras.Camera")
        ipdb.set_trace()

