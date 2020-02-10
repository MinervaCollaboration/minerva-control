import zwoasi as asi
import numpy as np
import ipdb
from astropy.io import fits
from astropy.io.fits import getdata
import datetime
from get_all_centroids import *
#import pyfits as fits
import datetime
import socket
import sep

class zwo:

	def __init__(self,config, base =''):

                self.base_directory = base

 		# load the SDK library
		asi.init(self.base_directory  + "\dependencies\ASICamera2.dll")

		# initialize the camera
		self.camera = asi.Camera(0)

		# set 16 bit integer image type
		self.camera.set_image_type(asi.ASI_IMG_RAW16)

		# set gain for maximum dynamic range
		self.camera.set_control_value(asi.ASI_GAIN, 0)

		if socket.gethostname() == 'minerva19-01': 
			self.xsize = 3096
			self.ysize = 2080
		else: 
			self.xsize=1936
			self.ysize=1216
                self.guideimagelastupdate = datetime.datetime.utcnow()
                self.guidestarx = np.nan
                self.guidestary = np.nan
		self.x1 = 1
		self.x2 = self.xsize
		self.y1 = 1
		self.y2 = self.ysize
		self.imageReady = False

		# make it full frame
		self.camera.set_roi(start_x=0, start_y=0, width=self.xsize, height=self.ysize)

                self.img = np.asarray([])
		
        def save_image(self, filename):

                #fits.writeto(filename, self.img, clobber=True)
                #return
                hdu = fits.PrimaryHDU(self.img)
                hdulist = fits.HDUList([hdu])
                hdulist.writeto(filename, clobber=True)

        def getGuideStar(self):
                return (self.guideimagelastupdate, self.guidestarx, self.guidestary)

        '''
	def expose(self, exptime, offset = (0.0,0.0)):
		self.camera.set_control_value(asi.ASI_EXPOSURE,int(round(exptime*1e6)))                
                self.img = self.camera.capture()
                self.imageReady = datetime.datetime.utcnow()
				
#		data = getdata(self.img)
#		data = data.astype(float)
                data = self.img.astype(float)
		x1 = 1500
                x2 = 1700
                y1 = 800
                y2 = 1000
		data_subframe = data[x1:x2,y1:y2]
                data_subframe = data_subframe.copy(order='C')
		bkg = sep.Background(data_subframe)
		data_sub = data_subframe-bkg
		objects = sep.extract(data_sub, 40, err=bkg.globalrms, minarea =10, deblend_cont = 1)
				
		# no stars in the image
		if len(objects) <1:
                        self.guidestarx = np.nan
                        self.guidestary = np.nan
                        self.guideimagelastupdate = datetime.datetime.utcnow()
		else:
                        brightest_star = np.argmax(objects['flux'])
					
			dx = objects['x'] - (objects[brightest_star][0] + offset[0]) 
			dy = objects['y'] - (objects[brightest_star][1] + offset[1])
			dist = np.linalg.norm((dx,dy))
                        ndx = np.argmin(dist)

                        self.guidestarx = stars[ndx][0]+x1
                        self.guidestary = stars[ndx][1]+y1
                        self.guideimagelastupdate = datetime.datetime.utcnow()
        '''
        
        def expose(self, exptime,offset=(0.0,0.0)): 
                self.imageReady = False
                self.camera.set_control_value(asi.ASI_EXPOSURE,int(round(exptime*1e6)))                
                self.img = self.camera.capture()
                self.imageReady = True#datetime.datetime.utcnow()
                   
                d = np.array(self.img, dtype='float')
                th = threshold_pyguide(d, level = 4)

                # all zero image
                if np.max(self.img*th) == 0.0:
                        self.guidestarx = np.nan        
                        self.guidestary = np.nan
                        self.guideimagelastupdate = datetime.datetime.utcnow()

                imtofeed = np.array(np.round((d*th)/np.max(d*th)*255), dtype='uint8')
                stars = centroid_all_blobs(imtofeed)
        
                if len(stars) < 1:
                        # no stars in the image
                        self.guidestarx = np.nan
                        self.guidestary = np.nan
                        self.guideimagelastupdate = datetime.datetime.utcnow()

                else:
                        # find the brightest star
                        brightestndx = np.argmax(stars[:,2])
			
			# find the closest star to the the offset position
			dx = stars[:,0] - (stars[brightestndx][0] + offset[0]) 
			dy = stars[:,1] - (stars[brightestndx][1] + offset[1]) 
			dist = np.linalg.norm((dx,dy))
                        ndx = np.argmin(dist)

                        self.guidestarx = stars[ndx][0]
                        self.guidestary = stars[ndx][1]
                        self.guideimagelastupdate = datetime.datetime.utcnow()

        
	def setROI(self, x1=None, x2=None, y1=None, y2=None, fullFrame=False, bins=None):
                if fullFrame:
                        x1 = 1
                        x2 = self.xsize
                        y1 = 1
                        y2 = self.ysize

                if x1 == None: x1 = self.x1
                else: self.x1 = x1

		if x2 == None: x2 = self.x2
		else: self.x2 = x2

		if y1 == None: y1 = self.y1
		else: self.y1 = y1

                if y2 == None: y2 = self.y2
		else: self.y2 = y2

		width = self.x2-self.x1+1
		height = self.y2-self.y1+1
		if width % 8 != 0 or height % 2 != 0:
			self.logger.error("subframe not allowed; using full frame")
                        self.x1 = 1
                        self.x2 = self.xsize
                        self.y1 = 1
                        self.y2 = self.ysize
			width = self.x2-self.x1+1
			height = self.y2-self.y1+1
			
		self.camera.set_roi(start_x=self.x1, start_y=self.y1, width=width, height=height, bins=bins)

        ''' 
        this creates a simple simulated image of a star field
        the idea is to be able to test guide performance without being on sky
        x -- an array of X centroids of the stars (only integers tested!)
        y -- an array of Y centroids of the stars (only integers tested!)
        flux -- an array of fluxes of the stars (electrons)
        fwhm -- the fwhm of the stars (arcsec)
        background -- the sky background of the image
        noise -- readnoise of the image
        '''
        def simulate_star_image(self,x,y,flux,fwhm,background=300.0,noise=0.0):

                self.dateobs = datetime.datetime.utcnow()

                xwidth = self.x2-self.x1
                ywidth = self.y2-self.y1
                self.image = np.zeros((ywidth,xwidth),dtype=np.float64) + background + np.random.normal(scale=noise,size=(ywidth,xwidth))

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
                        self.image[y1:y2,x1:x2] += noisystar
                    else: self.logger.warning("star off image (" + str(xii) + "," + str(yii) + "); ignoring")
                        
                # now convert to 16 bit int
                self.image = self.image.astype(np.int16)
		
