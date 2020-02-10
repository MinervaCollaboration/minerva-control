from configobj import ConfigObj
from scp import SCPClient
from win32com.client import Dispatch
from scipy import stats
import numpy as np
import os,sys,glob, socket, logging, datetime, ipdb, time, json, threading, subprocess, collections
import atexit, win32api
import utils
import math
import ao
import zwo
import ascomcam, ascomfw
from astropy.io import fits

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

		self.logger = utils.setup_logger(self.base_directory,self.night,self.logger_name)
		self.set_data_path()

                self.camera = ascomcam.ascomcam('',base=self.base_directory,driver=self.camera_driver)
                if self.camera_fw_driver != None: self.camera.fw = ascomfw.ascomfw('',base=self.base_directory,driver=self.camera_fw_driver)
                self.guider = zwo.zwo('',self.base_directory)
                self.guider.header_buffer = ''
                if self.guider_fw_driver != None: self.guider.fw = ascomfw.ascomfw('',base=self.base_directory,driver=self.guider_fw_driver)

		self.connect_camera()
		self.file_name = ''
		self.guider_file_name = ''

		if self.ao_ini != None:
			self.ao = ao.ao(self.ao_ini)

#==============utility functions=================#
#these methods are not directly called by client

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
		except:
			print('ERROR accessing configuration file: ' + self.config_file)
			sys.exit()


                today = datetime.datetime.utcnow()
                if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
                        today = today + datetime.timedelta(days=1)
                self.night = 'n' + today.strftime('%Y%m%d')

	def get_index(self,param):
		files = glob.glob(self.data_path + "/*.fits*")
		return 'success ' + str(len(files)+1)

	def get_status(self,param, guider=False):

                if guider: camera = self.guider
                else: camera = self.camera

                try:
                        status = {}
                        status['CoolerOn'] = camera.camera.CoolerOn
                        status['CurrentTemp'] = camera.camera.CCDTemperature
                        status['SetTemp'] = camera.camera.SetCCDTemperature
                        status['BinX'] = camera.camera.BinX
                        status['BinY'] = camera.camera.BinY
                        try: status['filter'] = camera.fw.current_filter()
                        except: status['filter'] = None
                        status['connected'] = camera.camera.connected
                        status['X1'] = camera.x1
                        status['X2'] = camera.x2
                        status['Y1'] = camera.y1
                        status['Y2'] = camera.y2
		except:
                        self.logger.exception("error getting camera status")
                        self.connect_camera()
                        return self.get_status(param)

		return 'success ' + json.dumps(status)

	#return true if temperature settles successfully, false if it fails
	def set_temperature(self,param,guider=False):

                if guider: camera = self.guider
                else: camera = self.camera

		try:
			setTemp = param.split()
			if len(setTemp) != 1:
				self.logger.error('parameter error')
				return 'fail'
			setTemp = float(setTemp[0])
			camera.cool(temp=setTemp)
			return 'success'
		except:
			self.logger.exception("Failed to set the temperature")
			return 'fail'

	def get_temperature(self, guider=False):
                if guider: camera = self.guider
                else: camera = self.camera
                
		try:
			return 'success '+ str(camera.get_temperature())
		except:
			return 'fail'

	def isAOPresent(self):
                if 'ao' in dir(self): return 'success True'
                return 'success False'
        
#==========command functions==============#
#methods directly called by client

	def connect_camera(self):
        
                try:
                        self.camera.initialize()
                        try: self.camera.fw.initialize()
                        except: pass
                        #self.guider.initialize()        
                        return 'success'
                except:
                        self.logger.exception("Failed to connect to the camera")
			return 'fail'

	#set binning
	def set_bin(self,param,guider=False):
                if guider: camera = self.guider
                else: camera = self.camera

		param = param.split()
		if len(param) != 2:
			return 'fail'
		try:
			self.logger.info('Setting binning to ' + param[0] + ',' + param[1] )
			camera.set_bin(int(param[0]),int(param[1]))
			return 'success'
		except:
			self.logger.error('Setting binning to ' + param[0] + ',' + param[1] + ' failed')
			return 'fail'

	def set_roi(self,param, guider=False):
                if guider: camera = self.guider
                else: camera = self.camera
                
		param = param.split()
		if len(param) != 4:
			return 'fail'
		try:
                        x1 = int(param[0])
                        x2 = int(param[1])
                        y1 = int(param[2])
                        y2 = int(param[3])
			# Set to full frame
			self.logger.info('Setting subframe to [' + param[0] + ':' + param[1] + ',' +
						 param[2] + ':' + param[3] + ']')
			if camera.set_roi(x1=x1, x2=x2, y1=y1, y2=y2): return 'success'
			return 'fail'
		except:
			return 'fail'

	def get_filter_name(self,param,guider=False):
                if guider: camera = self.guider
                else: camera = self.camera                

		res = 'success '

		try:
                        names = camera.fw.get_filter_names()
                        res += ' '.join(names)
			return res
		except:
			return 'fail'

        def getGuideStar(self):
                time,x,y = self.guider.getGuideStar()
                timestr = time.strftime('%Y-%m-%dT%H:%M:%S.%f')
                return 'success ' + timestr + ' '+str(x)+' '+str(y)

	def expose(self,param, guider=False):
                t0 = datetime.datetime.utcnow()
                # this should be standardized with ascom
                if guider:
                        try:
                                camera=self.guider
                                param = param.split()
                                exptime = float(param[0])
                                acquisition_offset_x = float(param[1])
                                acquisition_offset_y = float(param[2])
                                offset = (acquisition_offset_x,acquisition_offset_y)
                                filter_num = None
                                open_shutter=True

                                overhead = (datetime.datetime.utcnow() - t0).total_seconds()
        		        self.logger.info("It took " + str(overhead) + " seconds to get to 'expose'")

                                t0 = datetime.datetime.utcnow()
                                kwargs = {"offset":offset} 
                                thread = threading.Thread(target=camera.expose,args=(exptime,),kwargs=kwargs)
                                thread.name = "exposeGuider"
                                thread.start()
#                                camera.expose(exptime,offset=offset)
        

                                overhead = (datetime.datetime.utcnow() - t0).total_seconds()
        		        self.logger.info("It took " + str(overhead) + " seconds to 'expose'")

                                return 'success'
                        except:
                                return 'fail'
                else:
                        try:
                                camera = self.camera
                                param = param.split()
                                exptime = float(param[0])
                                open_shutter = (param[1] == 1)
                                filter_num = param[2]
                                if filter_num != None:
                                        camera.fw.move_and_wait(position=int(filter_num))

                                camera.expose(exptime,open_shutter=open_shutter)
                                return 'success'
                        except:
                                return 'fail'

	def save_image(self,param, guider=False):
                if guider: camera=self.guider
                else: camera=self.camera

                try:
                        filename = self.data_path + '\\' + param.split()[0]
                        camera.filename=filename
                        camera.save_image(filename)
                        return 'success'
                except:         
                        return 'fail'


	def write_header(self,param, guider=False):

                if guider: camera=self.guider
                else: camera=self.camera

                self.logger.info("guider is " + str(guider))

		camera.header_buffer += param
		return 'success'

	def write_header_done(self,param, guider=False):
                if guider: camera=self.guider
                else: camera=self.camera

                self.logger.info("guider is " + str(guider))
                
		try:
			filename=camera.filename
			self.logger.info("Writing header for " + filename)
		except:
			self.logger.error("file name not defined; saving failed earlier")
			camera.header_buffer = ''
			return 'fail'

		header_info = camera.header_buffer + param
		camera.header_buffer = ''

		try:
			# check to see if the image exists
			if os.path.isfile(filename):
                                f = fits.open(filename, 'update')
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

                        print f
			f.flush()
			f.close()
		except:
			self.logger.exception('Error updating header for ' + filename+ "; header string is: " + header_info)
			return 'fail'
		return 'success'

	def set_data_path(self):
		self.data_path = self.data_path_base + '\\' + self.night
		if not os.path.exists(self.data_path):
			os.makedirs(self.data_path)
		return 'success'

	def compress_data(self,night=None):
		try:
			#S This will throw if it doesn;t have data path, which
			#S seems like the only place how compression won't work now.
			#S Still need to practice caution though, as the thread that
			#S this function starts may still barf. I'm not sure if this should
			#S be communicated back to Main, but am still thinking about it.
			#TODO
			if night == None:
				data_path = self.data_path
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
			if guider: mean = fits.getdata(self.file_name,0).mean()
			else: mean = fits.getdata(self.guider_file_name,0).mean()
			mean = str(mean)
			return 'success ' + mean
		except:
			return 'fail'

	def getMode(self,guider=False):
                
		try:
			if guider: image = fits.getdata(self.guider_file_name,0)
			else: image = fits.getdata(self.file_name,0)
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

        def imageReady(self,param,guider=False):
                #imageStart = datetime.datetime.strptime(param,'%Y-%m-%d %H:%M:%S.%f')
                # we're comparing two clocks here (one on main and the local machine)
                #imageStart = imageStart - datetime.timedelta(seconds=0.3) #
                if guider:
                        camera=self.guider
                        #if camera.imageReady > imageStart: return 'success true'
                        if camera.imageReady: return 'success true'
                        return 'success false'
                else:
                        return 'success ' + str(self.camera.camera.ImageReady)                                

	def isSuperSaturated(self, guider=False):
                if guider: camera=self.guider
                else: camera=self.camera                
               
		try:
			image = fits.getdata(camera.filename,0)
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

                if guider: camera=self.guider
                else: camera=self.camera 
                
		try:
			os.remove(camera.filename)
			return 'success'
		except:
			return 'fail'


	def disconnect_camera(self, guider=False):
                if guider:
                        camera=self.guider
                else:
                        disconnect_camera(self,guider=True)
                        camera=self.camera
                
		try:
			self.logger.info('turning cooler off')
			camera.CoolerOn = False
			time.sleep(1)
			self.logger.info('disconnecting camera')
			camera.disconnect()
			return 'success'
		except:
                        self.logger.exception('disconnect failed')
			return 'fail'

                
		
#==================server functions===================#
#used to process communication between camera client and server==#

	#process received command from client program, and send response to given socket object
	def process_command(self, command, conn):
		tokens = command.split(None,1)

		if len(command) < 100:
			self.logger.info('command received: ' + command)

                if len(tokens) == 2:
                        param = tokens[1]
                        if 'guider' in param: guider = True
                        else: guider=False
 		if len(tokens) != 2:
			response = 'fail'
		elif tokens[0] == 'get_guide_star':
			response = self.getGuideStar()
		elif tokens[0] == 'get_filter_name':
			response = self.get_filter_name(tokens[1], guider=guider)
		elif tokens[0] == 'exposeGuider':
			response = self.expose(tokens[1], guider=True)
		elif tokens[0] == 'expose':
			response = self.expose(tokens[1])
		elif tokens[0] == 'save_image':
			response = self.save_image(tokens[1], guider=guider)
		elif tokens[0] == 'image_ready':
                        if guider: tokens[1] = tokens[1][0:-7]
			response = self.imageReady(tokens[1], guider=guider)
		elif tokens[0] == 'set_camera_param':
			response = self.set_camera_param(tokens[1], guider=guider)
		elif tokens[0] == 'set_data_path':
			response = self.set_data_path()
		elif tokens[0] == 'get_status':
			response = self.get_status(tokens[1], guider=guider)
		elif tokens[0] == 'get_index':
			response = self.get_index(tokens[1])
		elif tokens[0] == 'set_bin':
			response = self.set_bin(tokens[1], guider=guider)
		elif tokens[0] == 'set_roi':
			response = self.set_roi(tokens[1], guider=guider)
		elif tokens[0] == 'write_header':
                        if guider: tokens[1] = tokens[1][0:-7]
			response = self.write_header(tokens[1], guider=guider)
		elif tokens[0] == 'write_header_done':
                        if guider: tokens[1] = tokens[1][0:-7]
			response = self.write_header_done(tokens[1], guider=guider)
		elif tokens[0] == 'compress_data':
			response = self.compress_data(night=tokens[1])
		elif tokens[0] == 'getMean':
			response = self.getMean(guider=guider)
		elif tokens[0] == 'getMode':
			response = self.getMode(guider=guider)
		elif tokens[0] == 'isSuperSaturated':
			response = self.isSuperSaturated(guider=guider)
                elif tokens[0] == 'isAOPresent':
                        response = self.isAOPresent() 
                elif tokens[0] == 'get_tip_tilt':
                        response = self.ao.get_tip_tilt()
                elif tokens[0] == 'get_north_east':
                        response = self.ao.get_north_east()
		elif tokens[0] == 'moveAO':
			array = tokens[1].split(',')
			response = self.ao.move(float(array[0]),float(array[1]))
		elif tokens[0] == 'homeAO':
			response = self.ao.home()
		elif tokens[0] == 'remove':
			response = self.remove(guider=guider)
		elif tokens[0] == 'connect_camera':
			response = self.connect_camera()
		elif tokens[0] == 'disconnect_camera':
			response = self.disconnect_camera()
		elif tokens[0] == 'set_temperature':
			response = self.set_temperature(tokens[1], guider=guider)
		elif tokens[0] == 'get_temperature':
			response = self.get_temperature(guider=guider)
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
		#s.listen(True)
                s.listen(4)

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

if __name__ == '__main__':

    hostname = socket.gethostname()

    if hostname == 'Minervared2-PC' or hostname == 'Telcom-PC' or hostname == 'minerva19-01':
        config_file = 'imager_server_red.ini'
    elif hostname == "TacherControl":
        config_file = "imager_server_thach.ini"
    else:
	config_file = 'imager_server_' + hostname[0:2] + '.ini'

    base_directory = 'C:\minerva-control'

    test_server = server(config_file,base_directory)
    test_server.run_server()
