
import glob
import os
import numpy
import logging

# ask to use numpy
os.environ["NUMERIX"] = "numpy"
from astropy.io import fits as pyfits

from si.commands import *

class Imager (object):

	def __init__ (self, client):

		self.client = client

		self.nexp = None
		self.texp = None
		self.nome = None
		self.type = None
		self.dark = None
		self.frametransfer = None
		self.getpars = None


		# private
		self._term = False

	def doSingleFrame (self):

		print 'do single frame'
		
		self.client.executeCommand (SetAcquisitionMode (0)) # SINGLE FRAMES

		if self.dark:
			self.client.executeCommand (SetAcquisitionType (1)) # DARK, BUFFER 1
		else:
			self.client.executeCommand (SetAcquisitionType (0)) # LIGHT, BUFFER 1

		self.client.executeCommand (SetExposureTime(float(self.texp)))

		self.client.executeCommand (Acquire ())

		return True
		
	def doFrameTransfer (self):

		if self.dark:
			self.client.executeCommand (SetAcquisitionType (1, 1)) # BUFFER 1, DARK
		else:
			self.client.executeCommand (SetAcquisitionType (1, 0)) # BUFFER 1, LIGHT
			
		self.client.executeCommand (SetMultipleFrameBufferMode (1)), # GET ALL FRAMES
		self.client.executeCommand (SetAcquisitionMode (3)) # MULTIPLE FRAMES
		self.client.executeCommand (SetExposureTime (int(self.texp*1000)))

		comments = []
		comments.append (("NOTE1", "WARNING!!! The DATE-OBS and DATE-END headers are accurate "))
		comments.append (("NOTE2", "WARNING!!! only for the first frame of a sequence."))
		comments.append (("NOTE3", "WARNING!!! Other frames use an estimated value based "))                                 
		comments.append (("NOTE4", "WARNING!!! on the exposure time of the sequence."))
		
		m = int(self.nexp) / 10
		n = int(self.nexp) % 10

		sets = []

		for k in range(m):
			sets.append (10)

		if n != 0:
			sets.append (n)

		for run in sets:
									   
			self.client.executeCommand (SetNumberOfFrames (run))

			serial_length, parallel_length, img_buffer = self.client.executeCommand (Acquire (3, 1, 0, self.nome))

			header = self.client.executeCommand (GetImageHeader (1))
			headers = self._processHeader (header)          
 
			for i in range(run):

				pix_range = serial_length * (parallel_length / run)
				img = img_buffer[(i*pix_range):(pix_range*(i+1))]

				img_array = numpy.array (img, dtype=numpy.float32)
				new_array = img_array.reshape (parallel_length / run, serial_length)            

				new_array.byteswap (True)
				del img
				del img_array

				# fix date header
				date_headers = self._updateDateHeader (headers["TIME"][0], i)

				self._saveFITS (new_array, date_headers + comments, self._getNextName())
				del new_array

			return True


	def do (self):

		if self.getpars:
			print self.getCameraPars()
		elif self.frametransfer:
			return self.doFrameTransfer ()
		else:
			return self.doSingleFrame ()

	def getCameraPars(self):

		#cpars = '%s'%self.client.executeCommand(GetSIImageSGLIISettings())

		#cpars =  self.client.executeCommand(GetStatusFromCamera())

		cpars = self.client.executeCommand(GetCameraParameter())

		from StringIO import StringIO

		xcpars = StringIO()
		xcpars.write('%s'%cpars)
		xcpars.seek(0)
		a = np.loadtxt(xcpars,delimiter=',',dtype=[('group','S30'),('name','S30'),('value','int') ])
		print '->',a

		return cpars

        #S TerminateAcquisition command empties buffers, and htus does not save an image. I want to try
	#S just get image, but we'll see if that'll work.
	def interrupt (self):

		self.client.executeCommand (TerminateAcquisition ())

	def retrieve_image(self):
                self.client.executeCommand (RetrieveImage())
			
	def _saveFITS (self, img, headers, filename):

		hdu  = pyfits.PrimaryHDU(img)

		# Deprecated!
		#for header in headers:
		#    hdu.header.update (*header)
			
		fits = pyfits.HDUList([hdu])
		fits.writeto(filename, clobber=False, output_verify='silentfix')
		return True

	def _getNextName (self):

		idx = self._getNextId (self.nome)

		return "%s-%05d.fits" % (self.nome, idx)

	def _getNextId (self, nome):

		file_list = glob.glob ("%s-*" % nome)

		if not file_list:
			return 1

		idxs = []

		for f in file_list:
			idxs.append (int (f[f.rfind('-')+1:f.rfind('.')]))

		return max (idxs) + 1

	def _processHeader (self, header):

		headers = {}
		n_headers = len(header) / 80        
		
		for k in range(n_headers):
			line = header[k*80:(k+1)*80]
			
			name = line[0:8].strip()
			rest = line[9:]

			if rest.find ('/'):
				l = rest.split ("/")
				if len(l) != 2:
					continue
				
				value, comment = l[0], l[1]
				value = value.strip ()
				comment = comment[0:comment.rfind(',')].strip ()
				
				headers[name] = (value, comment)
			else:
				value = rest.strip ()
				headers[name] = (value, "")

		return headers

	def _updateDateHeader (self, orig_header, idx):

		ut = time.gmtime ()

		start_hour = int(orig_header[1:3])
		start_min = int(orig_header[4:6])
		start_sec = float(orig_header[7:12].replace(',', '.'))

		start_time = time.mktime ((ut.tm_year, ut.tm_mon, ut.tm_mday, start_hour, start_min, int(start_sec), ut.tm_wday, ut.tm_yday, ut.tm_isdst))

		end_hour = int(orig_header[17:19])
		end_min = int(orig_header[20:22])
		end_sec = float(orig_header[23:28].replace(',', '.'))
		
		end_time = time.mktime ((ut.tm_year, ut.tm_mon, ut.tm_mday, end_hour, end_min, int(end_sec), ut.tm_wday, ut.tm_yday, ut.tm_isdst))
   
		fits_date_format = "%Y-%m-%dT%H:%M:%S.%%03d"
		date = time.strftime(fits_date_format, time.gmtime())
		date = date % 0
		
		dateobs = time.strftime(fits_date_format, time.gmtime(start_time + (idx*(self.texp+1.0))))
		dateobs = dateobs % ((start_sec - int(start_sec))*1000)
		
		dateend = time.strftime(fits_date_format, time.gmtime(end_time + (idx*(self.texp+1.0))))
		dateend = dateend % ((end_sec - int(end_sec))*1000)

		headers = [("DATE", date, "date of file creation"),
				   ("DATE-OBS", dateobs, "date of the start of the observation"),
				   ("DATE-END", dateend, "date of the end of the observation")]

		return headers

	#(0=Single Image, 1=Average, 2=Multiple Images, 3=Multiple Frames, 4=Focus)
	def setAcquisitionMode(self,mode=0):
		self.client.executeCommand (SetAcquisitionMode (mode)) # SINGLE FRAMES
		
	#true for dark exposure, default light exposure
	def setDark(self,dark=False):
		
		if self.dark:
			self.client.executeCommand (SetAcquisitionType (1)) # DARK, BUFFER 1
		else:
			self.client.executeCommand (SetAcquisitionType (0)) # LIGHT, BUFFER 1
	
	#time in seconds
	def setExposureTime(self,time=1):
		self.client.executeCommand (SetExposureTime(float(time)))
		
	def acquire(self):
		self.client.executeCommand (Acquire ())
		
		
	def takeImage(self):

		print 'taking image'
		
		#use default parameters to save a temporary image named 'I' in si imager server folder
		self.setAcquisitionMode()
		self.setDark()
		self.setExposureTime()
		self.acquire()
		
	
if __name__ == '__main__':
	pass
