import numpy as np
import win32com.client
from astropy.io import fits
import datetime, time
import ipdb
import utils
import win32api
import atexit
import sys

class ascomcam:

	def __init__(self, config, base='', driver=None):


                self.base_directory = base
		today = datetime.datetime.utcnow()
                if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
                        today = today + datetime.timedelta(days=1)
                self.night = 'n' + today.strftime('%Y%m%d')

                self.logger_name = 'ASCOM_CAMERA'
                self.logger = utils.setup_logger(self.base_directory,self.night,self.logger_name)
                self.header_buffer = ''

                # if you don't know what your driver is called, use the ASCOM Chooser
                # this will give you a GUI to select it
		if driver==None:
                        x = win32com.client.Dispatch("ASCOM.Utilities.Chooser")
                        x.DeviceType = 'Camera'
                        driver = x.Choose(None)
                        print("The driver is " + driver)

		# initialize the camera
		try:
			self.camera = win32com.client.Dispatch(driver)
		except:
                        x = win32com.client.Dispatch("ASCOM.Utilities.Chooser")
                        x.DeviceType = 'Camera'
                        driver = x.Choose(None)
                        print("The driver is " + driver)

                win32api.SetConsoleCtrlHandler(self.safe_close,True)
                atexit.register(self.safe_close,'signal_argument')

	def load_config(self):
		try:
			config = ConfigObj(self.base_directory+ '/config/' + self.config_file)
			self.host = config['HOST']
			self.port = int(config['PORT'])
			self.data_path_base = config['DATA_PATH']
			self.logger_name = config['LOGNAME']
			self.camera_driver = config['CAMERADRIVER']
        		try: self.camera_fw_driver = config['FWDRIVER']
                        except: self.camera_fw_driver = None
        		try: self.guider_fw_driver = config['GUIDERFWDRIVER']
                        except: self.guider_fw_driver = None
			try: self.ao_ini = config['AOINI']
			except: self.ao_ini = None
			self.header_buffer = ''

                        self.gain = ['Setup']['GAIN']
                        self.platescale = ['Setup']['PLATESCALE']
                        self.camera_pdu_config = ['Setup']['CAMERA_PDU_CONFIG']
                        try: self.camera_pdu = pdu.pdu(self.camera_pdu_config,self.base_directory)
                        except: self.camera_pdu = None
                        self.camera_pdu_port = ['Setup']['CAMERA_PDU_PORT']                      
		except:
			print('ERROR accessing configuration file: ' + self.config_file)
			sys.exit()


                today = datetime.datetime.utcnow()
                if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
                        today = today + datetime.timedelta(days=1)
                self.night = 'n' + today.strftime('%Y%m%d')

        def power_on(self):
                exec('self.camera_pdu.' + self.camera_pdu_port + '.on()')
                time.sleep(5.0)
                self.initialize()
                
        def power_off(self):
                self.disconnect()
                exec('self.camera_pdu.' + self.camera_pdu_port + '.off()')               

        def power_cycle(self,downtime=30):
                self.power_off()
                time.sleep(downtime)
                self.power_on()

        def initialize(self, recover=False):
                try:
                        self.connect()
                except AttributeError:
                        self.logger.error("Cannot connect to camera")
                        if recover:
                                self.logger.error("Power cycling camera to recover")
                                self.power_cycle()
                                return
                        else: sys.exit() # return?
                self.cool()
                self.set_roi(fullFrame=True)
                self.set_bin(1)

	def connect(self):
                self.camera.connected = True
                return self.camera.connected

	def disconnect(self):
                self.camera.connected = False
                return not self.camera.connected

        # if we don't disconnect before exiting Python,
        # it crashes the DLL and we need to power cycle the camera
        def safe_close(self,signal):
                self.logger.info("Disconnecting before exit")
                self.disconnect()

        def starcat(self, ra, dec, width, height):
                result = Vizier.query_region(coord.SkyCoord(ra=ra, dec=dec,unit=(u.deg, u.deg),frame='icrs'),width="30m",catalog=["I/337/gaia"])
                ra = result[0]['RA_ICRS']
                dec = result[0]['DE_ICRS']
                mag = result[0]['__Gmag_']
                x = 0
                y = 0
                flux = 10**(-0.4*mag)

        '''                                                                                                                                                       
        this creates a simple simulated image of a star field                                                                                                     
        the idea is to be able to test guide performance, acquisition, etc, without being on sky                                                                                     
        x -- an array of X centroids of the stars (only integers tested!)                                                                                         
        y -- an array of Y centroids of the stars (only integers tested!)                                                                                         
        flux -- an array of fluxes of the stars (e-)                                                                                                       
        fwhm -- the fwhm of the stars (arcsec)                                                                                                                    
        background -- the sky background of the image, in ADU
        exptime -- the exposure time, in seconds. This will be written to the header, but will not impact the runtime unless wait=True
        noise -- readnoise of the image, in ADU
        wait -- boolean; wait for exptime to elapse
        '''
        def simulate_star_image(self,x,y,flux,fwhm=1.0,background=300.0,exptime=1.0,noise=10.0, wait=False, ra=None, dec=None):

                t0 = datetime.datetime.utcnow()
                self.exptime = exptime
                self.dateobs = datetime.datetime.utcnow()

                # query a catalog to simulate a star field 
                if ra !=None and dec != None:
                        pass

                xwidth = self.x2-self.x1
                ywidth = self.y2-self.y1
                image = np.zeros((ywidth,xwidth),dtype=np.float64) + background + np.random.normal(scale=noise,size=(ywidth,xwidth))

                # add a guide star?                                                                                                                               
                sigma = fwhm/self.platescale
                mu = 0.0
                boxsize = math.ceil(sigma*10.0)

                # make sure it's even to make the indices/centroids come out right                                                                                
                if boxsize % 2 == 1: boxsize+=1

                xgrid,ygrid = np.meshgrid(np.linspace(-boxsize,boxsize,2*boxsize+1), np.linspace(-boxsize,boxsize,2*boxsize+1))
                d = np.sqrt(xgrid*xgrid+ygrid*ygrid)
                g = np.exp(-( (d-mu)**2 / ( 2.0 * sigma**2 ) ) )
                g = g/np.sum(g) # normalize the gaussian                                                                                                          

                # add each of the stars                                                                                                                           
                for ii in range(len(x)):

                    xii = x[ii]-self.x1+1
                    yii = y[ii]-self.y1+1

                    # make sure the stamp fits on the image (if not, truncate the stamp)                                                                          
                    if xii >= boxsize:
                        x1 = xii-boxsize
                        x1stamp = 0
                    else:
                        x1 = 0
                        x1stamp = boxsize-xii
                    if xii <= (xwidth-boxsize):
                        x2 = xii+boxsize+1
                        x2stamp = 2*boxsize+1
                    else:
                        x2 = xwidth
                        x2stamp = xwidth - xii + boxsize
                    if yii >= boxsize:
                        y1 = yii-boxsize
                        y1stamp = 0
                    else:
                        y1 = 0
                        y1stamp = boxsize-yii
                    if yii <= (ywidth-boxsize):
                        y2 = yii+boxsize+1
                        y2stamp = 2*boxsize+1
                    else:
                        y2 = ywidth
                        y2stamp = ywidth - yii + boxsize

                    if (y2-y1) > 0 and (x2-x1) > 0:
                        # normalize the star to desired flux                                                                                                      
                        star = g[y1stamp:y2stamp,x1stamp:x2stamp]*flux[ii]

                        # add Poisson noise; convert to ADU
                        noise = np.random.normal(size=(y2stamp-y1stamp,x2stamp-x1stamp))
                        noisystar = (star + np.sqrt(star)*noise)/self.gain

                        # add the star to the image                                                                                                      
                        image[y1:y2,x1:x2] += noisystar
                    else: self.logger.warning("star off image (" + str(xii) + "," + str(yii) + "); ignoring")

                # simulate the exposure time, too
                if wait:
                        sleeptime = (datetime.datetime.utcnow() - t0).total_seconds() - exptime
                        if sleeptime > 0: time.sleep(sleeptime)
                
                # now convert to 16 bit int                                                                                                                       
                self.image = image.astype(np.int16)
                self.ready = True
                
                
	def get_temperature(self):
		return self.camera.CCDTemperature               

	def cool(self, temp=None, wait=False, settleTime=1200.0, oscillationTime=120.0, maxdiff = 1.0):
                if not self.camera.CanSetCCDTemperature:
                        self.logger.error("Camera does not support cooling")
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

        def set_bin(self,xbin,ybin=None):
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
                while elapsedTime < timeout and not self.camera.ImageReady and not self.ready:
                        time.sleep(0.05)
                        elapsedTime = (t0 - datetime.datetime.utcnow()).total_seconds()
                if not self.camera.ImageReady and not self.ready: return False

                if hdr == None: hdr = fits.Header()
                hdr['DATE-OBS'] = (self.dateobs.strftime('%Y-%m-%dT%H:%M:%S.%f'),'Observation start, UTC')
                hdr['EXPTIME'] = (self.exptime,'Exposure time in seconds')
                hdr['CCDSUM'] = (str(self.xbin) + ' ' + str(self.ybin),'CCD on-chip binning')
                datasec = '[' + str(self.x1) + ':' + str(self.x2) + ',' + str(self.y1) + ':' + str(self.y2) + ']'
                hdr['DATASEC'] = (datasec, 'Region of CCD read')
                hdr['CCDTEMP'] = (self.camera.CCDTemperature,'CCD Temperature (C)')
                hdr['SETTEMP'] = (self.camera.SetCCDTemperature,'CCD Set Temperature (C)')
                hdr['GAIN'] = (self.gain,'Gain (e/ADU)')

                if self.image != None:
                        # this is a simulated image
                        hdu = fits.PrimaryHDU(self.image, header=hdr)
                        self.image = None
                        self.ready = False
                else:
                        hdu = fits.PrimaryHDU(self.camera.ImageArray, header=hdr)
                hdu.writeto(filename, overwrite=overwrite)

                return True

        def expose(self,exptime, open_shutter=True):
                self.exptime = exptime
                self.dateobs = datetime.datetime.utcnow()
                self.camera.StartExposure(exptime,open_shutter)


if __name__ == '__main__':

        config_file = 'imager_mred.ini'
        base_directory = 'C:/minerva-control/'
        #camera = ascomcam(config_file, base_directory, driver="ASCOM.AtikCameras.Camera")
        camera = ascomcam(config_file, base_directory, driver="ASCOM.Apogee.Camera")
        camera.initialize()
        ipdb.set_trace()

