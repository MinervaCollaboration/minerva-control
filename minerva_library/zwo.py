import zwoasi as asi
import numpy as np
import ipdb
from astropy.io import fits
import datetime
from get_all_centroids import *
#import pyfits as fits
import datetime

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

                self.xsize=1936
                self.ysize=1216
                self.guideimagelastupdate = datetime.datetime.utcnow()
                self.guidestarx = np.nan
                self.guidestary = np.nan

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

        def expose(self, exptime,offset=(0.0,0.0)): 
                self.camera.set_control_value(asi.ASI_EXPOSURE,int(round(exptime*1e6)))                
                self.img = self.camera.capture()
                   
                d = np.array(self.img, dtype='float')
                th = threshold_pyguide(d, level = 4)

                # all zero image
                if np.max(self.img*th) == 0.0:
                        self.guidestarx = np.nan        
                        self.guidestary = np.nan
                        self.guideimagelastupdate = datetime.datetime.utcnow()

                imtofeed = np.array(np.round((d*th)/np.max(d*th)*255), dtype='uint8')
                stars = centroid_all_blobs(imtofeed)

                print stars
        
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
			dist = np.sqrt(dx^2 + dy^2)
                        ndx = np.argmin(dist)

                        self.guidestarx = stars[ndx][0]
                        self.guidestary = stars[ndx][1]
                        self.guideimagelastupdate = datetime.datetime.utcnow()

                        


		
