from get_all_centroids import *
import pyfits
import segments
import os.path
import numpy as np
from datetime import datetime, timedelta
import math

##class guider:
##    
##    def __init__(self,guider_name, configfile=''):
##
##        self.name = guider_name
##
##        #set appropriate parameter based on aqawan_num
##        #create configuration file object 
##        configObj = ConfigObj(configfile)
##        
##        try:
##            guiderconfig = configObj[self.name]
##        except:
##            print('ERROR accessing ', self.name, ".", 
##                self.name, " was not found in the configuration file", configfile)
##            return 
##
##        self.platescale = float(guiderconfig['Setup']['PLATESCALE'])
##        self.filters = guiderconfig['FILTERS']
##        self.setTemp = float(guiderconfig['Setup']['SETTEMP'])
##        self.maxcool = float(guiderconfig['Setup']['MAXCOOLING'])
##        self.maxdiff = float(guiderconfig['Setup']['MAXTEMPERROR'])
##        self.xbin = int(guiderconfig['Setup']['XBIN'])
##        self.ybin = int(guiderconfig['Setup']['YBIN'])
##        self.x1 = int(guiderconfig['Setup']['X1'])
##        self.x2 = int(guiderconfig['Setup']['X2'])
##        self.y1 = int(guiderconfig['Setup']['Y1'])
##        self.y2 = int(guiderconfig['Setup']['Y2'])
##        self.xcenter = int(guiderconfig['Setup']['XCENTER'])
##        self.ycenter = int(guiderconfig['Setup']['YCENTER'])
##        self.pointingModel = guiderconfig['Setup']['POINTINGMODEL']
##        self.port = int(guiderconfig['Setup']['PORT'])
##        
##        logger_name = guiderconfig['Setup']['LOGNAME']
##        log_file = 'logs/' + guiderconfig['Setup']['LOGFILE']
##                        
##        # setting up logger
##        self.logger = logging.getLogger(logger_name)
##        formatter = logging.Formatter(fmt="%(asctime)s [%(filename)s:%(lineno)s - %(funcName)20s()] %(levelname)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
##        fileHandler = logging.FileHandler(log_file, mode='w')
##        fileHandler.setFormatter(formatter)
##        streamHandler = logging.StreamHandler()
##        streamHandler.setFormatter(formatter)
##
##        self.logger.setLevel(logging.DEBUG)
##        self.logger.addHandler(fileHandler)
##        self.logger.addHandler(streamHandler)
##
##        self.cam = Dispatch("MaxIm.CCDCamera")

def getstars(imageName):
    
    d = getfitsdata(imageName)
    th = threshold_pyguide(d, level = 4)
    imtofeed = np.array(np.round((d*th)/np.max(d*th)*255), dtype='uint8')
    cc = centroid_all_blobs(imtofeed)

    return cc

def guide(stars, reference):

    m0= 22
    x = stars[:,0]
    y = stars[:,1]
    mag = -2.5*np.log10(stars[:,2])+m0

    xref = reference[:,0]
    yref = reference[:,1]
    magref = -2.5*np.log10(reference[:,2])+m0

    dx,dy,scale,rot,flag,rmsf,nstf = findoffset(x, y, mag, xref, yref, magref)
    
    return dx,dy,scale,rot,flag,rmsf,nstf

def findoffset(x, y, mag, xref, yref, magref):

    MAXSTARS = 50
    thet=0.0 # thet +/- dthet (deg)
    dthet = 3
    scl = 0.0 # 1 + scl +/- dscl
    dscl = 0.01
    naxis1 = 2048
    naxis2 = 2048

    maxstars = min(MAXSTARS,len(xref))
    sortndx = np.argsort(magref)
#    print maxstars
       
    xreftrunc = xref[sortndx[0:maxstars]]
    yreftrunc = yref[sortndx[0:maxstars]]
    magreftrunc = magref[sortndx[0:maxstars]]
    lindx1,lparm1 = segments.listseg(xreftrunc, yreftrunc, magreftrunc)

    maxstars = min(MAXSTARS,len(x))
#    print maxstars

    sortndx = np.argsort(mag)
    xtrunc = x[sortndx[0:maxstars]]
    ytrunc = y[sortndx[0:maxstars]]
    magtrunc = mag[sortndx[0:maxstars]]
    lindx2,lparm2 = segments.listseg(xtrunc, ytrunc, magtrunc)
    
    # magic
    dx,dy,scale,rot,mat,flag,rmsf,nstf = \
        segments.fitlists4(naxis1,naxis2,lindx1,lparm1,lindx2,lparm2,\
                               xreftrunc,yreftrunc,xtrunc,ytrunc,scl,dscl,thet,dthet)

    return dx,dy,scale,rot,flag,rmsf,nstf

if __name__ == "__main__":

    refimage = "C:\minerva\data\\n20150207\\n20150315.T1.KJ06C006046.rp.0048.fits"
    filepath = "C:\minerva\data\\n20150315\\n20150315.T1.KJ06C006046.rp.????.fits.fz"
    #filepath = "C:\minerva\data\\n20150315\*T3*M77*.fits.fz"

    files = glob.glob(filepath)
    reference = getstars(files[0])

    # fraction of measured correction to apply (dx, dy, dtheta)
    gain = 0.75 

    for f in files:

        stars = getstars(f)
        dx,dy,scale,rot,flag,rmsf,nstf = guide(stars, reference)

        # adjust the rotator angle (sign?)
#        telescope.rotatorIncrement(rot)*gain

        # adjust RA/Dec (need to calibrate PA)
#        deltaRA = (dx*cos(PA) - dy*sin(PA))*cos(dec)*platescale*gain
#        deltaDec = (dx*sin(PA) + dy*cos(PA))*platescale*gain
#        telescope.mountOffsetRaDec(deltaRA,deltaDec)
        
        print os.path.basename(f),dx,dy,rot,nstf, len(stars)#,scale,flag,rmsf,nstf
    
