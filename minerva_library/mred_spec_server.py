from configobj import ConfigObj
from scp import SCPClient
from win32com.client import Dispatch
from scipy import stats
import numpy as np
import os,sys,glob, socket, logging, datetime, ipdb, time, json, threading, pyfits, subprocess, collections
import atexit, win32api
import utils
import math
import ao
import pdu, com, mail, ascomcam
import pythoncom

# full API at http://www.cyanogen.com/help/maximdl/MaxIm-DL.htm#Scripting.html

class server:

	def __init__(self, config, base=''):

		self.config_file = config
		self.base_directory = base
		self.load_config()


		# reset the night at 10 am local
		today = datetime.datetime.utcnow()
		if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
                        today = today + datetime.timedelta(days=1)
		night = 'n' + today.strftime('%Y%m%d')

		self.logger = utils.setup_logger(self.base_directory,self.night(),self.logger_name)
		self.set_data_path()
		self.cam = None
                self.maxim = None
		self.connect_camera()
		self.file_name = ''
		self.guider_file_name = ''
                self.calpdu = pdu.pdu('apc_mred_cal.ini', self.base_directory)
                #self.benchpdu = pdu.pdu('apc_mred_bench.ini', self.base_directory)
                self.gaugeController = com.com('gaugeControllerRed',self.base_directory,self.night())
                self.chiller = com.com('chillerRed',self.base_directory,self.night())
                self.chillerlastemailed = datetime.datetime.utcnow() - datetime.timedelta(days=1)
                self.atm_pressure_gauge = com.com('atmPressureGauge',self.base_directory,self.night())
                self.nspecfail = 0
                self.lastemailed = datetime.datetime.utcnow() - datetime.timedelta(days=1)
                self.backlightonrequest = datetime.datetime.utcnow() - datetime.timedelta(days=1)
                self.heneonrequest = datetime.datetime.utcnow() - datetime.timedelta(days=1)
                self.logger_lock = threading.Lock()
                self.log_exposure_meter = True

#		if socket.gethostname() == 't2-PC':
#			self.ao = ao.ao('ao_t' + socket.gethostname()[1] + '.ini')
		#XXX These do not work
		#S Setup shut down procedures
		#win32api.SetConsoleCtrlHandler(self.safe_close,True)
		#atexit.register(self.safe_close,'signal_arguement')

#==============utility functions=================#
#these methods are not directly called by client

	def load_config(self):
		try:
			config = ConfigObj(self.base_directory+ '/config/' + self.config_file)
			self.host = config['HOST']
			self.port = int(config['PORT'])
			self.data_path_base = config['DATA_PATH']
			self.logger_name = config['LOGNAME']
			self.header_buffer = ''
		except:
			print('ERROR accessing configuration file: ' + self.config_file)
			sys.exit()

		today = datetime.datetime.utcnow()
		if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
			today = today + datetime.timedelta(days=1)

	def get_index(self,param):
		files = glob.glob(self.data_path() + "/*.fits*")
		return 'success ' + str(len(files)+1)

	def get_status(self,param):

                try:
                        status = {}
                        status['CoolerOn'] = self.cam.CoolerOn
                        status['CurrentTemp'] = self.cam.Temperature
                        status['SetTemp'] = self.cam.TemperatureSetpoint
                        status['BinX'] = self.cam.BinX
                        status['BinY'] = self.cam.BinY
                        status['filter'] = self.cam.Filter
                        status['connected'] = self.cam.LinkEnabled
                        status['X1'] = self.cam.StartX
                        status['X2'] = self.cam.StartX + self.cam.NumX - 1
                        status['Y1'] = self.cam.StartY
                        status['Y2'] = self.cam.StartY + self.cam.NumY - 1
		except:
                        self.logger.exception("error getting camera status")
                        self.connect_camera()
                        return self.get_status(param)

		return 'success ' + json.dumps(status)

	#return true if temperature settles successfully, false if it fails
	def set_temperature(self,param):

		try:
			setTemp = param.split()
			if len(setTemp) != 1:
				self.logger.error('parameter error')
				return 'fail'
			setTemp = float(setTemp[0])
			self.cam.TemperatureSetpoint = setTemp
			self.cam.CoolerOn = True
			return 'success'
		except:
			self.logger.exception("Failed to set the temperature")
			return 'fail'

	def get_temperature(self):
		try:
			return 'success '+ str(self.cam.Temperature)
		except:
			return 'fail'
#==========command functions==============#
#methods directly called by client

	def connect_camera(self):

		try:
			# Connect to an instance of Maxim's camera control.
			# (This launches the app if needed)
                        if self.maxim == None:
                                self.maxim = Dispatch("MaxIm.Application")
			if self.cam == None:
				self.cam = Dispatch("MaxIm.CCDCamera")

			# Connect to the camera
			self.logger.info('Connecting to camera')
			self.cam.LinkEnabled = True

			#S Turn on the cooler so we don't hit any issues with self.safe_close
			self.cam.CoolerOn = True
			return 'success'
		except:
                        self.logger.exception("Failed to connect to the camera")
			return 'fail'



	#set binning
	def set_binning(self,param):

		param = param.split()
		if len(param) != 2:
			return 'fail'
		try:
			self.logger.info('Setting binning to ' + param[0] + ',' + param[1] )
			self.cam.BinX = int(param[0])
			self.cam.BinY = int(param[1])
			return 'success'
		except:
			self.logger.error('Setting binning to ' + param[0] + ',' + param[1] + ' failed')
			return 'fail'

	def set_size(self,param):
		param = param.split()
		if len(param) != 4:
			return 'fail'
		try:
			# Set to full frame
			xsize = int(param[1])-int(param[0])+1
			ysize = int(param[3])-int(param[2])+1
			self.logger.info('Setting subframe to [' + param[0] + ':' + param[1] + ',' +
						 param[2] + ':' + param[3] + ']')
			self.cam.StartX = int(param[0])
			self.cam.StartY = int(param[2])
			self.cam.NumX = xsize # CENTER_SUBFRAME_WIDTH
			self.cam.NumY = ysize # CENTER_SUBFRAME_HEIGHT
			return 'success'
		except:
			return 'fail'

	def get_filter_name(self,param):
		res = 'success '

		try:
			num = int(param)
			for i in range(int(param)):
				res += self.cam.FilterNames[i] + ' '
			return res
		except:
			return 'fail'

	def exposeGuider(self,param):
		try:
			self.cam.GuiderExpose(float(param))
			return 'success'
		except:
			return 'fail'

	def expose(self,param):
		try:
			param = param.split()
			exptime = float(param[0])
			exptype = int(param[1])
			filter_num = param[2]

			if filter_num == 'None':
				self.cam.Expose(exptime,exptype)
			else:
				self.cam.Expose(exptime,exptype,int(filter_num))
			return 'success'
		except:
                        self.logger.error("Failed to expose")
			return 'fail'

        def set_file_name(self,param):
                if len(param.split()) != 1:
			self.logger.error('parameter mismatch')
			return 'fail'
		self.logger.info('setting name to:' + param)
		self.file_name = self.data_path() + '\\' + param                
                return 'success'

	def save_image(self,param):

                if len(param.split()) == 2:
                        file_name = param.split()[0]
                        guider = True
                elif len(param.split()) == 1:
                        file_name = param.split()[0]
			if file_name == 'guider':
				self.logger.error("empty filename")
				return 'fail'
                        guider = False
                else:
			self.logger.error('parameter mismatch')
			return 'fail'
		try:
                        if guider:
                                self.logger.info('Saving guider image')
                                time.sleep(0.2) # wait for the image to start
                                while self.cam.GuiderRunning:
                                        time.sleep(0.1)
                                self.logger.info('saving image to:' + file_name)
                                self.guider_file_name = self.data_path() + '\\' + file_name
                                self.maxim.CurrentDocument.SaveFile(self.guider_file_name,3, False, 1)
				return 'success'
                        else:
                                time.sleep(0.2) # wait for the image to start
                		print self.cam.ImageReady, self.cam.CameraStatus
                                t0 = datetime.datetime.utcnow()
                                timeElapsed = 0.0
                                timeout = 30
        			while ((not self.cam.ImageReady) or (self.cam.CameraStatus <> 2)) and (timeElapsed < timeout):
                			time.sleep(0.1)
                			timeElapsed = (datetime.datetime.utcnow() - t0).total_seconds()
                		print self.cam.ImageReady, self.cam.CameraStatus
                                self.logger.info('saving image to:' + file_name)
        			self.file_name = self.data_path() + '\\' + file_name
                                try:
                                        if self.cam.SaveImage(self.file_name):
                				return 'success'
                                        self.logger.error("Error saving image")
                                	return 'fail'
                                except:
                                        self.logger.exception("Error saving image")
                                        return 'fail'
                except:
                        self.logger.exception("Error saving image")
			return 'fail'

	def write_header(self,param):

		self.header_buffer = self.header_buffer + param
		return 'success'

	def write_header_done(self,param):

		# the last 7 characters may or may not indicate this is a guider image
		if param[-7:] == ' guider':
			guider = True
			param = param[0:-7]
                else: guider = False

		try:
			if guider: filename=self.guider_file_name
			else: filename=self.file_name
			self.logger.info("Writing header for " + filename)
		except:
			self.logger.error("file name not defined; saving failed earlier")
			self.header_buffer = ''
			return 'fail'

		header_info = self.header_buffer + param
		self.header_buffer = ''

		try:
			# check to see if the image exists
			if os.path.isfile(filename):
				f = pyfits.open(filename, mode='update')
			else:
				self.logger.error("FITS file (" + filename + ") not found")
				return 'fail'

			try:
				hdr = json.loads(header_info,object_pairs_hook=collections.OrderedDict)
			except:
				self.logger.exception('Error updating header for ' + filename+ "; header string is: " + header_info)
				hdr = {}

			for key,value in hdr.iteritems():
				if isinstance(value, (str, unicode, float)):
					if isinstance(value,float):
						if math.isnan(value): value = 'NaN'
					f[0].header[key] = value
				else:
       					if isinstance(value[0],float):
               					if math.isnan(value[0]): value[0] = 'NaN'
                       			f[0].header[key] = (value[0],value[1])

			f.flush()
			f.close()
		except:
			self.logger.exception('Error updating header for ' + filename+ "; header string is: " + header_info)
			return 'fail'
		return 'success'

        # only for backward compatibility
	def set_data_path(self):
		data_path = self.data_path()
		return 'success'

        def data_path(self):
                data_path = self.data_path_base + '\\' + self.night()
		if not os.path.exists(data_path):
			os.mkdir(data_path)
                return data_path

	def compress_data(self,night=None):
		try:
			#S This will throw if it doesn;t have data path, which
			#S seems like the only place how compression won't work now.
			#S Still need to practice caution though, as the thread that
			#S this function starts may still barf. I'm not sure if this should
			#S be communicated back to Main, but am still thinking about it.
			#TODO
			if night == None:
				data_path = self.data_path()
			else:
				data_path = self.data_path_base+'\\'+night
			files = glob.glob(data_path + "/*.fits")
			compress_thread = threading.Thread(target = self.compress_thread,args = (files,))
			compress_thread.start()
			return 'success'

		except:
                        self.logger.exception('Compress thread failed to start')
			return 'fail'

	def compress_thread(self, files):
		for filename in files:
			logging.info('Compressing ' + filename)
			subprocess.call([self.base_directory + '/cfitsio/fpack.exe','-D',filename])


	def getMean(self,guider=False):
		try:
			if guider: mean = pyfits.getdata(self.file_name,0).mean()
			else: mean = pyfits.getdata(self.guider_file_name,0).mean()
			mean = str(mean)
			res = 'success ' + mean
		except:
			res = 'fail'
		return res

	def getMode(self,guider=False):
		try:
			if guider: image = pyfits.getdata(self.guider_file_name,0)
			else: image = pyfits.getdata(self.file_name,0)
			# mode is slow; take the central 100x100 region
			# (or the size of the image, which ever is smaller)
			nx = len(image)
			ny = len(image[1])
			size = 100
			x1 = int(max(nx/2.0 - size/2.0,0))
			x2 = int(min(nx/2.0 + size/2.0,nx-1))
			y1 = int(max(ny/2.0 - size/2.0,0))
			y2 = int(min(ny/2.0 + size/2.0,ny-1))

			mode = stats.mode(image[x1:x2,y1:y2],axis=None)[0][0]
			res = 'success ' + str(mode)
		except:
			res = 'fail'
                return res

	def isSuperSaturated(self, guider=False):
		try:
			if guider: image = pyfits.getdata(self.guider_file_name,0)
			else: image = pyfits.getdata(self.file_name,0)
			# mode is slow; take the central 100x100 region
			# (or the size of the image, which ever is smaller)
			nx = len(image)
			ny = len(image[1])
			size = 100
			x1 = max(nx/2.0 - size/2.0,0)
			x2 = min(nx/2.0 + size/2.0,nx-1)
			y1 = max(ny/2.0 - size/2.0,0)
			y2 = min(ny/2.0 + size/2.0,ny-1)

			photonNoise = 10.0 # made up, should do this better
			if np.std(image[x1:x2,y1:y2],axis=None) < photonNoise:
				return 'success true'
			else:
				return 'success false'
		except:
			return 'fail'

	def remove(self, guider=False):
		try:
			if guider: os.remove(self.guider_file_name)
			else: os.remove(self.file_name)
			return 'success'
		except:
			return 'fail'

        def quit_maxim(self):
                try:
                        self.cam = None
                        self.maxim = None
                        return 'success'
                except:
                        self.logger.exception("quitting maxim failed")
                        return 'fail'

	def disconnect_camera(self):
		try:
			self.logger.info('turning cooler off')
			self.cam.CoolerOn = False
			time.sleep(1)
			self.logger.info('disconnecting camera')
			self.cam.LinkEnabled = False
			return 'success'
		except:
                        self.logger.exception('disconnect failed')
			return 'fail'

        def backlight_on(self):
                self.backlightonrequest = datetime.datetime.utcnow()
                self.calpdu.laser.on()
                time.sleep(0.5)
                
		# failsafe so backlight doesn't stay on
		# backlight creates heat that disrupts the thermal stability of the spectrograph!!
		backlight_failsafe_thread = threading.Thread(target = self.backlight_failsafe)
		backlight_failsafe_thread.name = 'MRED'
		backlight_failsafe_thread.start()
                return 'success'

                
        def backlight_off(self):
                self.calpdu.laser.off()
		return 'success'

	# a failsafe so the backlight doesn't stay on
	# called by backlight_on in a separate thread
	def backlight_failsafe(self, timeout=60):
		t0 = datetime.datetime.utcnow()
		timeElapsed = 0
		while timeElapsed < timeout:
			timeElapsed = (datetime.datetime.utcnow() - t0).total_seconds()
			if (datetime.datetime.utcnow() - self.backlightonrequest).total_seconds() > timeout:
				self.logger.error("encountered failsafe; turning off the backlight")
				self.backlight_off()
				return
			time.sleep(1)
			
        def hene_on(self):
                self.heneonrequest = datetime.datetime.utcnow()
                self.calpdu.henelamp.on()
                time.sleep(0.5)
                
		# failsafe so hene doesn't stay on
		hene_failsafe_thread = threading.Thread(target = self.hene_failsafe)
		hene_failsafe_thread.name = 'MRED'
		hene_failsafe_thread.start()
                return 'success'

                
        def hene_off(self):
                self.calpdu.henelamp.off()
		return 'success'

	# a failsafe so the hene doesn't stay on
	# called by hene_on in a separate thread
	def hene_failsafe(self, timeout=60):
		t0 = datetime.datetime.utcnow()
		timeElapsed = 0
		while timeElapsed < timeout:
			timeElapsed = (datetime.datetime.utcnow() - t0).total_seconds()
			if (datetime.datetime.utcnow() - self.heneonrequest).total_seconds() > timeout:
				self.logger.error("encountered failsafe; turning off the hene lamp")
				self.hene_off()
				return
			time.sleep(1)
 	def get_spec_pressure(self):
                response = str(self.gaugeController.send('#  RDCG2'))

                if '*' in response:
                        try:
                                pressure = float(response.split()[1])
                        except:
                                self.logger.exception("Unexpected response: " + response)
                                return 'fail'
                        return 'success ' + str(pressure)
                return 'fail'

        def get_pump_pressure(self):
                response = str(self.gaugeController.send('#  RDCG1'))
                
                if '*' in response:
                        try:
                                pressure = float(response.split()[1])
                        except:
                                self.logger.exception("Unexpected response: " + response)
                                return 'fail'
                        return 'success ' + str(pressure)
                return 'fail'

                #S going to log the pressures of the chamber and the pump
        def log_pressures(self):
		
                while True:
                        path = self.base_directory + "/log/" + self.night() + "/"
                        if not os.path.exists(path): os.mkdir(path)
                        
			# get the pressure in the spectrograph
                        with open(path + 'spec_pressure.log','a') as fh:
                                now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')
                                response = self.get_spec_pressure()
                                if response <> 'fail':
                                        specpres = float(response.split()[1])
                                        fh.write('%s,%s\n'%(now,specpres))
					self.nfailspec = 0 
				else:
					specpres = 'UNKNOWN'
					self.nfailspec += 1

			# get the pressure in the lines before the spectrograph
                        with open(path + 'pump_pressure.log','a') as fh:
                                now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')
                                response = self.get_pump_pressure()
                                if response <> 'fail':
                                        pumppres = float(response.split()[1])
                                        fh.write('%s,%s\n'%(now,pumppres))
					self.nfailpump = 0 
				else: 
					pumppres = 'UNKNOWN'
					self.nfailpump += 1

			# get the status of each port
        		try:
                                ventvalveopen = self.benchpdu.ventvalve.status()
        			if ventvalveopen: ventvalvetxt = "open"
                		else: ventvalvetxt = "closed"
                        except:
                                ventvalveopen = "unknown"
        			ventvalvetxt = "unknown"
                		
                        try:
        			pumpvalveopen = self.benchpdu.pumpvalve.status()
                		if pumpvalveopen: pumpvalvetxt = "open"
                        	else: pumpvalvetxt = "closed"
                        except:
                                pumpvalveopen = "unknown"
        			pumpvalvetxt = "unknown"

                        try:        
                                pumpon = self.controlroompdu.pump.status()
                		if pumpon: pumptxt = 'on'
        			else: pumptxt = 'off'
                        except:
                                pumpon = "unknown"
                                pumptxt = 'unknown'

                        try:
        			compressoron = self.controlroompdu.compressor.status()
                		if compressoron: compressortxt = 'on'
                        	else: compressortxt = 'off'
                        except:
                                compressoron = "unknown"
                                compressortxt = "unknown"

			# Catch potential failure modes
			# spectrograph pressure gauge failed
			if specpres == 'UNKNOWN':
				self.logger.error('The spectograph gauge has failed to read ' + str(self.nfailspec) + ' consecutive times')
				if self.nfailspec > 3 and (datetime.datetime.utcnow() - self.lastemailed).total_seconds() > 86400:
					mail.send("Spectrograph pressure gauge failed?",
						  "Dear Benevolent Humans,\n\n"+
						  "The spectrograph pressure gauge has failed to return a value 3\n"+
						  "consecutive times. Please investigate.\n\n"
						  "Love,\nMINERVA",level="serious")
					self.lastemailed = datetime.datetime.utcnow()
			elif not compressoron:
				self.logger.error('The air compressor is off.')
				if (datetime.datetime.utcnow() - self.lastemailed).total_seconds() > 86400:
					mail.send("Air compressor failed?",
						  "Dear Benevolent Humans,\n\n"+
						  "The air compressor is off. It is required to control the vacuum valves " + 
						  "and stabilize the optical bench. Please investigate immediately.\n\n"+
						  "Love,\nMINERVA",level="serious")
					self.lastemailed = datetime.datetime.utcnow()
			elif specpres > 0.1:
				self.logger.error("the spectrograph pressure is out of range")
				self.logger.info("The pump pressure is " + str(pumppres) + " mbar")
                                self.logger.info("The spectrograph pressure is " + str(specpres) + " mbar")
				self.logger.info("The compressor is " + compressortxt)
				self.logger.info("The vacuum pump is " + pumptxt)
				self.logger.info("The vent valve is " + ventvalvetxt)
				self.logger.info("The pump valve is " + pumpvalvetxt)

				if pumppres != 'UNKNOWN' and pumppres < specpres and pumpon and (not ventvalveopen) and pumpvalveopen:
					# 0) pumping down after venting
					# diagnosis:
					#    spec pressure > 0.1
					#    pump pressure < spec pressure
					# action:
					# email in case of misdiagnosis
					if (datetime.datetime.utcnow() - self.lastemailed).total_seconds() > 86400:
						mail.send("Spectrograph pressure out of range!",
							  "Dear Benevolent Humans,\n\n"+
							  "The spectrograph pressure (" + str(specpres) + " mbar) is out of range. " +
							  "I believe I am just pumping down after being vented and no action is required. "+
							  "If that is not the case, this should be investigated immediately.\n\n"
							  "The pump pressure is " + str(pumppres) + " mbar\n"+
							  "The spectrograph pressure is " + str(specpres) + " mbar\n"+
							  "The compressor is " + compressortxt + '\n'+
							  "The vacuum pump is " + pumptxt + '\n'+
							  "The vent valve is " + ventvalvetxt + '\n'+
							  "The pump valve is " + pumpvalvetxt + '\n\n'+
							  "Love,\nMINERVA",level="serious")
						self.lastemailed = datetime.datetime.utcnow()
				elif pumppres != 'UNKNOWN' and pumppres < 0.1 and pumpon and (not ventvalveopen) and pumpvalveopen:
					# 1) a power outage closed the pump valve and the leak rate 
					# caused it to slowly come back up slowly (bad, but not terrible)
					# diagnosis:
					#    spec pressure > 3
					#    pump pressure < 3
					#    pump on
					#    vent valve closed (off)
					#    pump valve open (on)
					# action:
					# email only asking user to open the pump valve after confirmation of situation (serious)
					# too risky to automate
					if (datetime.datetime.utcnow() - self.lastemailed).total_seconds() > 86400:
						mail.send("Spectrograph pressure out of range!",
							  "Dear Benevolent Humans,\n\n"+
							  "The spectrograph pressure (" + str(specpres) + " mbar) is out of range. " +
							  "While this could be a catastrophic and unplanned venting that could " + 
							  "damage the spectrograph and should be investigated immediately, this " +
							  "is usually caused by a power outage that closed the pump valve.\n\n."
							  "The pump pressure is " + str(pumppres) + " mbar\n"+
							  "The spectrograph pressure is " + str(specpres) + " mbar\n"+
							  "The compressor is " + compressortxt + '\n'+
							  "The vacuum pump is " + pumptxt + '\n'+
							  "The vent valve is " + ventvalvetxt + '\n'+
							  "The pump valve is " + pumpvalvetxt + '\n\n'+
							  "Please\n\n" +
							  "1) log on to 192.168.1.40\n"	
							  "2) Confirm the pump is on\n"+
							  "3) log on to 192.168.1.40\n"
							  "4) Check to make sure the vent valve is closed (off)\n"+
							  "5) Open the pump valve by turning it on.\n\n" +
							  "The spectrograph pressure is currently unstable and our RV precision will suffer until this is addressed.\n\n"
							  "Love,\nMINERVA",level="serious")
						self.lastemailed = datetime.datetime.utcnow()
				elif (pumppres != 'UNKOWN') and (pumppres > 3) and pumpvalveopen:
					# 2) the pump failed and it's venting through the pump (very bad)
					#    spec pressure > 3
					#    pump pressure > 3
					#    pump valve open (on)
					#    pump on (probably, but not necessarily)
					#    vent valve closed (probably, but not necessarily)
					# action:
					# Close pump valve immediately
					# Turn off pump?
					# Email asking user to investigate (critical)
					try: self.benchpdu.pumpvalve.off()
                                        except: pass
					if (datetime.datetime.utcnow() - self.lastemailed).total_seconds() > 86400:
						mail.send("Spectrograph vacuum failure!!!",
							  "Dear Benevolent Humans,\n\n"+
							  "The spectrograph pressure (" + str(specpres) + " mbar) is out of range " +
							  "and the pump valve is open. This probably means THE PUMP HAS FAILED " + 
							  "CATASTROPHICALLY AND DAMAGE TO THE SPECTOGRAPH COULD OCCUR! " + 
							  "I have closed the pump valve, but this should be investigated in " + 
							  "person and remotely as soon as possible.\n\n"
							  "The pump pressure is " + str(pumppres) + " mbar\n"+
							  "The spectrograph pressure is " + str(specpres) + " mbar\n"+
							  "The compressor is " + compressortxt + '\n'+
							  "The vacuum pump is " + pumptxt + '\n'+
							  "The vent valve is " + ventvalvetxt + '\n'+
							  "The pump valve is " + pumpvalvetxt + '\n\n'+
							  "Love,\nMINERVA",level="critical")
						self.lastemailed = datetime.datetime.utcnow()
				elif pumppres != 'UNKNOWN' and pumppres > 0.1 and (not pumpvalveopen) and ventvalveopen and (not pumpon):
					# 3) we intentionally vented the spectrograph (probably fine as this is intentional)
					#    spec pressure > 3
					#    pump pressure > 3
					#    pump off
					#    vent valve open
					#    pump valve closed
					# action:
					# Email just in case venting was not intentional (serious)
					if (datetime.datetime.utcnow() - self.lastemailed).total_seconds() > 86400:
						mail.send("Spectrograph intentionally venting?",
							  "Dear Benevolent Humans,\n\n"+
							  "The spectrograph pressure (" + str(specpres) + " mbar) is out of range, " +
							  "but the vent valve is open, the pump is off, and the pump valve is closed, "+
							  "which means the spectrograph is likely being vented intentionally. "+
							  "If that is not the case, immediate investigation is required.\n\n"
							  "The pump pressure is " + str(pumppres) + " mbar\n"+
							  "The spectrograph pressure is " + str(specpres) + " mbar\n"+
							  "The compressor is " + compressortxt + '\n'+
							  "The vacuum pump is " + pumptxt + '\n'+
							  "The vent valve is " + ventvalvetxt + '\n'+
							  "The pump valve is " + pumpvalvetxt + '\n\n'+
							  "Love,\nMINERVA",level="serious")
						self.lastemailed = datetime.datetime.utcnow()
				else:
					# 4) unknown failure (gauge failure?)
					#    spec pressure > 3
					#    any other configuration
					# action:
					# close pump valve
					# close vent valve
					# turn off pump?
					# email asking user to investigate (critical)
					#self.benchpdu.pumpvalve.off()
					#self.benchpdu.ventvalve.off()
					if (datetime.datetime.utcnow() - self.lastemailed).total_seconds() > 86400:				
						mail.send("Spectrograph pressure in unknown state!!!",
							  "Dear Benevolent Humans,\n\n"+
							  "The spectrograph pressure (" + str(specpres) + " mbar) is out of range, " +
							  "and I'm not sure what's going on. It could be a catastrophic problem. "+
							  "You need to investigate immediately. SERIOUS DAMAGE IS POSSIBLE.\n\n"
							  "The pump pressure is " + str(pumppres) + " mbar\n"+
							  "The spectrograph pressure is " + str(specpres) + " mbar\n"+
							  "The compressor is " + compressortxt + '\n'+
							  "The vacuum pump is " + pumptxt + '\n'+
							  "The vent valve is " + ventvalvetxt + '\n'+
							  "The pump valve is " + pumpvalvetxt + '\n\n'+
							  "Love,\nMINERVA",level="critical")
						self.lastemailed = datetime.datetime.utcnow()

                        time.sleep(0.5)
	def update_logpaths(self,path):
		self.logger.info('Updating log paths!')
		
		if not os.path.exists(path): os.mkdir(path)
		
		fmt = "%(asctime)s [%(filename)s:%(lineno)s,%(thread)d - %(funcName)s()] %(levelname)s: %(message)s"
		datefmt = "%Y-%m-%dT%H:%M:%S"
		formatter = logging.Formatter(fmt,datefmt=datefmt)
		formatter.converter = time.gmtime
		
                self.logger_lock.acquire()

		for fh in self.logger.handlers: self.logger.removeHandler(fh)
		fh = logging.FileHandler(path + '/' + self.logger_name + '.log', mode='a')
                fh.setFormatter(formatter)
		self.logger.addHandler(fh)

                self.logger_lock.release()

	def logpath_watch(self):
                lastnight = ''
                #S update the logger, similar to in domeControl
		while True:
                        t0 = datetime.datetime.utcnow()
			
                        # roll over the logs to a new day                                                                                                                   
                        thisnight = datetime.datetime.strftime(t0,'n%Y%m%d')
                        if thisnight != lastnight:
                                self.update_logpaths(self.base_directory + '/log/' + thisnight)
                                lastnight = thisnight
                                
                        #S sleep until tomorrow
                        tomorrow = datetime.datetime.replace(t0 + datetime.timedelta(days=1),hour=0,minute=0,second=0)
                        tomorrow_wait = (tomorrow - t0).total_seconds()
                        sleep_time = max(1.,0.99*tomorrow_wait)
                        self.logger.info('Waiting %.2f to update log paths'%(sleep_time))
                        time.sleep(sleep_time)

        #S Power on the exposure meter and make continuous
        #S readings that are logged. A maxsafecount variable is
        #S defined here that will act as a catch if there
        #S is an overexposure hopefully before any damage is done.         
        def logexpmeter(self, exptime=1):

                pythoncom.CoInitialize()
                atik = ascomcam.ascomcam('atik.ini', self.base_directory, driver="ASCOM.AtikCameras.Camera")
                atik.initialize()
                atik.set_roi(x1=550,x2=750,y1=450,y2=650)
                
                #S Loop for catching exposures.
                while self.log_exposure_meter:

                        basepath = "C:/minerva/data/" + self.night() 
                        if not os.path.exists(basepath): os.mkdir(basepath)
                        path = basepath + "/expmeter/"
                        if not os.path.exists(path): os.mkdir(path)

                        files = glob.glob(path + self.night() + '.expmeter.?????.fits') 
                        index = str(len(files)+1).zfill(5)

                        filename = path + self.night() + '.expmeter.' + index + '.fits'
                        atik.expose(exptime)
                        atik.save_image(filename)
                        
                        #with open(path + "expmeter.dat", "a") as fh:
                        #       fh.write(datetime.datetime.strftime(datetime.datetime.utcnow(),'%Y-%m-%d %H:%M:%S.%f') + "," + str(reading) + "\n")
                        #self.expmeter_com.logger.info("The exposure meter reading is: " + str(reading))

                
        def get_expmeter_total(self):
                #S put this in a try in case we aren't logging the exposure meter
                #S because we initialize the self.expmeter_total in 
                try:
                        total = self.expmeter_total
                        return 'success ' + str(total)
                except:
                        self.logger.error('No expmeter_total being tracked')
                        return 'fail'

        def reset_expmeter_total(self):
                try:
                        self.expmeter_total = 0
                        return 'success'
                except:
                        self.logger.exception('Failed to reset the expmeter total')
                        return 'fail'
         

#==================server functions===================#
#used to process communication between camera client and server==#

	#process received command from client program, and send response to given socket object
	def process_command(self, command, conn):
		tokens = command.split(None,1)
		if len(command) < 100:
			self.logger.info('command received: ' + command)
		if len(tokens) != 2:
			response = 'fail'
		elif tokens[0] == 'get_filter_name':
			response = self.get_filter_name(tokens[1])
		elif tokens[0] == 'exposeGuider':
			response = self.exposeGuider(tokens[1])
		elif tokens[0] == 'expose':
			response = self.expose(tokens[1])
		elif tokens[0] == 'save_image':
			response = self.save_image(tokens[1])
		elif tokens[0] == 'set_camera_param':
			response = self.set_camera_param(tokens[1])
		elif tokens[0] == 'set_data_path':
			response = self.set_data_path()
		elif tokens[0] == 'get_status':
			response = self.get_status(tokens[1])
		elif tokens[0] == 'get_index':
			response = self.get_index(tokens[1])
		elif tokens[0] == 'set_binning':
			response = self.set_binning(tokens[1])
		elif tokens[0] == 'set_file_name':
			response = self.set_file_name(tokens[1])
		elif tokens[0] == 'set_size':
			response = self.set_size(tokens[1])
		elif tokens[0] == 'write_header':
			response = self.write_header(tokens[1])
		elif tokens[0] == 'write_header_done':
			response = self.write_header_done(tokens[1])
		elif tokens[0] == 'compress_data':
			response = self.compress_data(night=tokens[1])
		elif tokens[0] == 'getMean':
			guider = (tokens[1] == 'guider')
			response = self.getMean(guider=guider)
		elif tokens[0] == 'getMode':
			guider = (tokens[1] == 'guider')
			response = self.getMode(guider=guider)
		elif tokens[0] == 'isSuperSaturated':
			guider = (tokens[1] == 'guider')
			response = self.isSuperSaturated(guider=guider)
		elif tokens[0] == 'moveAO':
			array = tokens[1].split(',')
			response = self.ao.move(array[0],array[1])
		elif tokens[0] == 'homeAO':
			response = self.ao.home()
		elif tokens[0] == 'remove':
			guider = (tokens[1] == 'guider')
			response = self.remove(guider=guider)
		elif tokens[0] == 'connect_camera':
			response = self.connect_camera()
		elif tokens[0] == 'disconnect_camera':
			response = self.disconnect_camera()
		elif tokens[0] == 'set_temperature':
			response = self.set_temperature(tokens[1])
		elif tokens[0] == 'get_temperature':
			response = self.get_temperature()
		elif tokens[0] == 'quit_maxim':
			response = self.quit_maxim()
                elif tokens[0] == 'backlight_on':
                        response = self.backlight_on()
                elif tokens[0] == 'backlight_off':
                        response = self.backlight_off()
                elif tokens[0] == 'hene_on':
                        response = self.backlight_on()
                elif tokens[0] == 'hene_off':
                        response = self.backlight_off()
                elif tokens[0] == 'get_pump_pressure':
                        response = self.get_pump_pressure()
                elif tokens[0] == 'get_spec_pressure':
                        response = self.get_pump_pressure()
                else:
			self.logger.info('command not recognized: (' + tokens[0] +')')
			response = 'fail'
		try:
			conn.settimeout(3)
			conn.sendall(response)
			conn.close()
		except:
			self.logger.exception('failed to send response, connection lost')
			return

		if response.split()[0] == 'fail':
			self.logger.info('command failed: (' + tokens[0] +')')
		else:
			self.logger.info('command succeeded(' + tokens[0] +')')

	#server loop that handles incoming command
	def run_server(self):

		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try: s.bind((self.host, self.port))
		except:
			self.logger.exception("Error connecting to server")
			raise
		s.listen(True)
		while True:
			print 'listening to incoming connection on port ' + str(self.port)
			conn, addr = s.accept()
			try:
				conn.settimeout(3)
				data = conn.recv(1024)
			except:
				break
			if not data:break
			self.process_command(repr(data).strip("'"),conn)
		s.close()
		self.run_server()

        def chiller_status_dict(self):

                status_dict = {}
                status = self.get_chiller_status()
                if status != 'fail':
                        status = int(float(status.split()[1]))
                        status_dict['run']                    = bool(status & 0x000000001)
                        status_dict['remote_lock']            = bool(status & 0b000000010)
                        status_dict['ready']                  = bool(status & 0b000000100)
                        status_dict['less_than_set_point']    = bool(status & 0b000001000)
                        status_dict['greater_than_set_point'] = bool(status & 0b000010000)
                        status_dict['tec_heating']            = bool(status & 0b000100000)
                        status_dict['general_warning']        = bool(status & 0b001000000)
                        status_dict['general_alarm']          = bool(status & 0b010000000)
                        status_dict['autotune']               = bool(status & 0b100000000)

                faults = self.get_chiller_faults()
                if faults != 'fail':
                        faults = int(float(faults.split()[1]))
                        status_dict['rtd']       = bool(faults & 0b0001)
                        status_dict['tank_low']  = bool(faults & 0b0010)
                        status_dict['pump_fail'] = bool(faults & 0b0100)
                        status_dict['fan_fail']  = bool(faults & 0b1000)
                return status_dict

        def get_chiller_status(self):
                try:
                        status = float(self.chiller.send('STAT1A?'))
                except:
                        self.logger.exception("Unexpected response: " + response)
                        return 'fail'
                return 'success ' + str(status)

        def get_chiller_faults(self):
                try:
                        faults = float(self.chiller.send('FLTS1A?'))
                except:
                        self.logger.exception("Unexpected response: " + response)
                        return 'fail'
                return 'success ' + str(faults) 

        def get_chiller_temp(self):
                try:
                        temp = float(self.chiller.send('TEMP?'))
                except:
                        self.logger.exception("Unexpected response: " + response)
                        return 'fail'
                return 'success ' + str(temp)
        def get_chiller_settemp(self):
                try:
                        temp = float(self.chiller.send('SETTEMP?'))
                except:
                        self.logger.exception("Unexpected response: " + temp)
                        return 'fail'
                return 'success ' + str(temp)
        def get_chiller_pumptemp(self):
                try:
                        temp = float(self.chiller.send('PUMPTEMP?'))
                except:
                        self.logger.exception("Unexpected response: " + temp)
                        return 'fail'
                return 'success ' + str(temp)

	def logchiller(self):
                while True:
                        t0 = datetime.datetime.utcnow()
                        path = self.base_directory + "/log/" + self.night() + "/"
                        if not os.path.exists(path): os.mkdir(path)

                        # watch dog for chiller failures
                        status = self.chiller_status_dict()
			if 'rtd' in status.keys():
                                if status['rtd'] and (datetime.datetime.utcnow() - self.chillerlastemailed).total_seconds() > 86400:
                                        mail.send("Chiller RTD failed",
                                                  "Dear Benevolent Humans,\n\n"+
                                                  "The chiller's RTD failed. Please investigate.\n\n"
                                                  "Love,\nMINERVA",level="serious")
                                        self.chillerlastemailed = datetime.datetime.utcnow()
			if 'fan_fail' in status.keys():
                                if status['fan_fail'] and (datetime.datetime.utcnow() - self.chillerlastemailed).total_seconds() > 86400:
                                        mail.send("Chiller fan failed",
                                                  "Dear Benevolent Humans,\n\n"+
                                                  "The chiller's fan failed. Please investigate.\n\n"
                                                  "Love,\nMINERVA",level="serious")
                                        self.chillerlastemailed = datetime.datetime.utcnow()
			if 'pump_fail' in status.keys():
                                if status['pump_fail'] and (datetime.datetime.utcnow() - self.chillerlastemailed).total_seconds() > 86400:
                                        mail.send("Chiller pump failed",
                                        	  "Dear Benevolent Humans,\n\n"+
                                        	  "The chiller's pump failed. Please investigate.\n\n"
                                        	  "Love,\nMINERVA",level="serious")
                                        self.chillerlastemailed = datetime.datetime.utcnow()
			if 'tank_low' in status.keys():
                                if status['tank_low'] and (datetime.datetime.utcnow() - self.chillerlastemailed).total_seconds() > 86400:
                                        mail.send("Chiller tank level is low",
                                                  "Dear Benevolent Humans,\n\n"+
                                                  "The chiller's tank level is low. Please fill.\n\n"
                                                  "Love,\nMINERVA",level="serious")
                                        self.chillerlastemailed = datetime.datetime.utcnow()                        
                        
			# get the pressure in the spectrograph
                        with open(path + 'chiller_temps.log','a') as fh:
                                now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')
                                response = self.get_chiller_temp()
                                if response <> 'fail': temp = str(response.split()[1])
                                else: temp = 'UNKNOWN'
                                        
                                response = self.get_chiller_settemp()
                                if response <> 'fail': settemp = str(response.split()[1])
                                else: settemp = 'UNKNOWN'

                                response = self.get_chiller_pumptemp()
                                if response <> 'fail': pumptemp = str(response.split()[1])
                                else: pumptemp = 'UNKNOWN'
                                fh.write('%s,%s,%s,%s\n'%(now,temp, settemp, pumptemp))
                        sleeptime = 5.0 - (datetime.datetime.utcnow() - t0).total_seconds()
                        if sleeptime > 0.0: time.sleep(sleeptime)
                return

        def get_atmreading(self):
                self.atm_pressure_gauge.open()
                for i in range(14):
                        line = self.atm_pressure_gauge.ser.readline()
                self.atm_pressure_gauge.close()
                try:
                        pressure = float(line[0:7])
                        temp = float(line[8:13])
                        alt = float(line[14:19])
                        return 'success ' + str(pressure) + ' ' + str(temp) + ' ' + str(alt)
                except:
                        self.logger.exception("Unexpected response: " + line)
                        return 'fail'
                
        def log_atmpressure(self):
                while True:
                        t0 = datetime.datetime.utcnow()
                        path = self.base_directory + "/log/" + self.night() + "/"
                        if not os.path.exists(path): os.mkdir(path)

                        with open(path + 'atm_reading.log','a') as fh:
                                now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')
                                response = self.get_atmreading()
                                if response <> 'fail':
                                        pressure = str(response.split()[1])
                                        temp = str(response.split()[2])
                                        alt = str(response.split()[3])
                                else:
                                        pressure = 'UNKNOWN'
                                        temp = 'UNKNOWN'
                                        alt = 'UNKNOWN'

                                fh.write('%s,%s,%s,%s\n'%(now,pressure, temp, alt))
                        sleeptime = 10.0 - (datetime.datetime.utcnow() - t0).total_seconds()
                        if sleeptime > 0.0: time.sleep(sleeptime)
                return

        def fiber_switch(self,pos):
                return
                self.fiberSwitch(p)

        def night(self):
		return 'n' + datetime.datetime.utcnow().strftime('%Y%m%d')

if __name__ == '__main__':
        config_file = 'spectrograph_mred_server.ini'
        base_directory = 'C:\minerva-control'

        test_server = server(config_file,base_directory)
        #test_server.log_atmpressure()

        #status = test_server.chiller_status_dict()
        #ipdb.set_trace()

        # make sure it didn't die with the backlight on
        test_server.backlight_off()

        # update the log and data path
        logpath_thread = threading.Thread(target=test_server.logpath_watch)
        logpath_thread.name = 'MRED'
        logpath_thread.start()

        # log the spectrograph and pump pressures
        pressure_thread = threading.Thread(target=test_server.log_pressures)
        pressure_thread.name = 'MRED'
        pressure_thread.start()

        # log the exposure meter
        expmeter_thread = threading.Thread(target=test_server.logexpmeter)
        expmeter_thread.name = 'MRED'
        expmeter_thread.start()

        # log the chiller temps
        chiller_thread = threading.Thread(target=test_server.logchiller)
        chiller_thread.name = 'MRED'
        chiller_thread.start()

        # log the atmospheric pressure
        atmpressure_thread = threading.Thread(target=test_server.log_atmpressure)
        atmpressure_thread.name = 'MRED'
        atmpressure_thread.start()

        # listen for commands
        test_server.run_server()
