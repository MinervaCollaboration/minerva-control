import zwoasi as asi
import numpy as np
import ipdb
from astropy.io import fits
import datetime

class zwo:

	def __init__(self,config, base =''):

		self.lock = threading.Lock()
		self.config_file = config
		self.base_directory = base
		self.load_config()
		self.logger = utils.setup_logger(self.base_directory,self.night,self.logger_name)
		self.initialize()
		self.telcom = telcom_client.telcom_client(self.telcom_client_config,base)
		

	def initialize(self):
		
 		# load the SDK library
		asi.init("C:\minerva-control\dependencies\ASICamera2.dll")

		# initialize the camera
		self.camera = asi.Camera(0)

		# set 16 bit integer image type
		self.camera.set_image_type(asi.ASI_IMG_RAW16)

		# set gain for maximum dynamic range
		self.camera.set_control_value(asi.ASI_GAIN, 0)

		# make it full frame
		self.camera.set_roi(start_x=0, start_y=0, width=self.xsize, height=self.ysize)


	def load_config(self):
		try:
                        # common to spectrograph detector and imaging camera
                        config = ConfigObj(self.base_directory + '/config/' + self.config_file)
			self.ip = config['Setup']['SERVER_IP']
			self.port = int(config['Setup']['SERVER_PORT'])
			self.logger_name = config['Setup']['LOGNAME']
			self.setTemp = float(config['Setup']['SETTEMP'])
			self.maxcool = float(config['Setup']['MAXCOOLING'])
			self.maxdiff = float(config['Setup']['MAXTEMPERROR'])
			self.xbin = int(config['Setup']['XBIN'])
			self.ybin = int(config['Setup']['YBIN'])
			self.xcenter = config['Setup']['XCENTER']
			self.ycenter = config['Setup']['YCENTER']
			self.x1 = config['Setup']['X1']
			self.x2 = config['Setup']['X2']
			self.y1 = config['Setup']['Y1']
			self.y2 = config['Setup']['Y2']
			self.biaslevel = float(config['Setup']['BIASLEVEL'])
			self.saturation = float(config['Setup']['SATURATION'])
			self.flattargetcounts = float(config['Setup']['FLATTARGETCOUNTS'])
			self.flatminexptime = float(config['Setup']['FLATMINEXPTIME'])
			self.flatmaxexptime = float(config['Setup']['FLATMAXEXPTIME'])
			self.flatminsunalt = float(config['Setup']['FLATMINSUNALT'])
			self.flatmaxsunalt = float(config['Setup']['FLATMAXSUNALT'])
			self.datapath = ''
			self.gitpath = ''
			self.file_name = 'test'
			self.night = 'test'
			self.nfailed = 0
			self.nserver_failed = 0
			self.pdu_config = config['Setup']['PDU']

			# imaging camera
			self.telcom_client_config = config['Setup']['TELCOM']
			self.platescale = float(config['Setup']['PLATESCALE'])
			self.filters = config['FILTERS']
			self.pointingModel = config['Setup']['POINTINGMODEL']
			self.telid = config['Setup']['TELESCOPE']
			self.telnum = self.telid[1]
			self.exptypes = {'Dark' : 0,'Bias' : 0,'SkyFlat' : 1,}
			self.fau_config = config['Setup']['FAU_CONFIG']
                        try: self.telescope_config = config['Setup']['TELESCOPE_CONFIG']
			except: self.telescope_config = ''

			try: self.PBfilters = config['PBFILTERS']
			except: self.PBfilters = None
			try: self.PBflatminsunalt = config['PBFLATMINSUNALT']
			except: self.PBflatminsunalt = None
			try: self.PBflatmaxsunalt = config['PBFLATMAXSUNALT']
			except: self.PBflatmaxsunalt = None
			try: self.PBflattargetcounts = config['PBFLATTARGETCOUNTS']
			except: self.PBflattargetcounts = None
			try: self.PBbiaslevel = config['PBBIASLEVEL']
			except: self.PBbiaslevel = None
			try: self.PBsaturation = config['PBSATURATION']
			except: self.PBsaturation = None
			try: self.PBflatmaxexptime = config['PBFLATMAXEXPTIME']
			except: self.PBflatmaxexptime = None
			try: self.PBflatminexptime = config['PBFLATMINEXPTIME']
			except: self.PBflatminexptime = None

			# fau
                        if not self.thach:
                                self.fau = fau.fau(self.fau_config,self.base_directory)

 		except:
			print('ERROR accessing config file: ' + self.config_file)
			sys.exit()

                today = datetime.datetime.utcnow()
                if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
                        today = today + datetime.timedelta(days=1)
                self.night = 'n' + today.strftime('%Y%m%d')


	


# set exposure time
exptime = 10 # microseconds
camera.set_control_value(asi.ASI_EXPOSURE, exptime)

start_x = 300
start_y = 450
box = 96
#

t0 = datetime.datetime.utcnow()
for i in range(10):
  img = camera.capture()
print (datetime.datetime.utcnow()-t0).total_seconds()/10.0 - exptime/1e6

ipdb.set_trace()

hdu = fits.PrimaryHDU(img)
hdul = fits.HDUList([hdu])
hdul.writeto('test1.fits')

ipdb.set_trace()