#!/usr/bin/env python

from glob import glob
import pyfits
import segments
import source_extraction
import os.path
import numpy as np
from datetime import datetime, timedelta

# read the camera mappings file
def readcamera():
    filep = open('camera_mappings','rb')
    header = []
    data = {}
    for line in filep:
        
        if line.startswith('# Site'):
            header = [x for x in line.split()][1:-1]
            for h in header:
                data[h] = []
        elif not line.startswith('# Last'):
            values = [x for x in line.split()]
            for h,v in zip(header,values):
                data[h].append(v)

    return data   

# read a sextractor catalog file into a dictionary
def readsexcat(catname):

    filep = open(catname,'rb')
    header = []
    data = {}
    for line in filep:
        
        if line.startswith('#'):
            header.append(line.split()[2])
            for h in header:
                data[h] = []
        elif not line.startswith('-----') and not line.startswith('Measuring') and \
                not line.startswith('(M+D)') and not line.startswith('Objects:'):
            values = [ float(x) for x in line.split() ]
            for h,v in zip(header,values):
                data[h].append(v)

    return data

def findalldays(start_date,end_date):
#    alldays = []

    cd = start_date
    while cd <= end_date:
        daydir = str(cd.year).zfill(4) + str(cd.month).zfill(2) + str(cd.day).zfill(2)
        allcameras = findallcameras(daydir)
#        for series in allcameras:
#            alldays.append(series)
#        cd += timedelta(days=1)
#
#    return alldays

def findallcameras(daydir):
    # read the camera mappings file  
    cameras = readcamera()

#    allcameras = []
    # find all series within start_date, end_date
    for i in range(len(cameras['CameraType'])):
        if 'SciCam' in cameras['CameraType'][i]:
            print daydir,cameras['Site'][i],cameras['Camera'][i]
            
            series = findseries(daydir,cameras['Site'][i],cameras['Camera'][i])
            xmotion, ymotion, rotation, rms = register(series)

#            for series in allseries:
#                allcameras.append(series)
    
    return allseries
                             

def findseries(daydir, site, camera):
    
    imdir = '/archive/engineering/'+site+'/'+camera+'/'+daydir+'/raw/'
    
    images = sorted(glob(imdir+'*-e00.fits'))
    nimage = len(images)

    mintime = 1.0/24.0 # minimum length of series, in days
    minimages = 10 # minimum number of images in a series

    # extract the molecule number and time of observation
    molecule = []
    mjd = []
    proposal = []
    object = []
    for image in images:
        hdulist = pyfits.open(image)
        prihdr = hdulist[0].header

        molecule.append(prihdr['MOLNUM'])
        mjd.append(prihdr['MJD-OBS'])
        proposal.append(prihdr['PROPID'])
        object.append(prihdr['OBJECT'])

    # find unique molecules
    molecules = list(set(molecule))

    # find all series -- sequences of images 
    # longer than 1 hour
    # with at least 10 images
    # with the same MOLNUM

    allseries = []
    for molnum in molecules:
    
        series = ()
        time = []
        
        # find all images that match the molnum
        for i in range(len(images)):
            if molecule[i] == molnum and proposal[i] <> 'LCOELP-001' and \
                    object[i] <> "Flat" and object <> "Moon":

                # use the catalog files instead of the images
                catname = images[i].replace('raw','cat') + '.sex'
                if os.path.isfile(catname):
                    series = series + (catname,)
                    time.append(mjd[i])
                else:
                    print "Catalog for " + images[i] + " does not exist"

        # does the series meet the criteria?
        if len(time) > 0:
            if max(time) - min(time) > mintime and len(series) > minimages:
                allseries.append(series)
    
    return allseries

# given a series of images, find the X, Y, and rotation of the images
def register(catlist):

    INSUFFICIENT_SOURCES_IN_REFERENCE = -1,-1,-1,-1
    REFERENCE_HAS_NO_CATALOG = -1,-1,-1,-1
    NOT_ENOUGH_IMAGES = -1,-1,-1,-1
    MAXSTARS = 50
    naxis1 = 2000
    naxis2 = 2000

    # threshholds for alignment (must be within threshhold to be allowed)
    thet=0.0 # thet +/- dthet (deg)
    dthet = 0.1
    scl = 0.0 # 1 + scl +/- dscl
    dscl = 0.01 

    if len(catlist) == 0:
        return NOT_ENOUGH_IMAGES
    
    print catlist[0]

    if not os.path.isfile(catlist[0]):
        return REFERENCE_HAS_NO_CATALOG

    ref = readsexcat(catlist[0])

    nref = len(ref['X_IMAGE_DBL'])

    # not enough images in the reference file
    if nref < 6:
        return INSUFFICIENT_SOURCES_IN_REFERENCE

    # get the MAXSTARS stars, brightest first
    maxstars = min(MAXSTARS,len(ref['X_IMAGE_DBL']))
    xref = np.array(ref['X_IMAGE_DBL'])
    yref = np.array(ref['Y_IMAGE_DBL'])
    magref = np.array(ref['MAG_AUTO'])
    
    sortndx = np.argsort(magref)
    xref = xref[sortndx[0:maxstars]]
    yref = yref[sortndx[0:maxstars]]
    magref = magref[sortndx[0:maxstars]]
    lindx1,lparm1 = segments.listseg(xref, yref, magref)

    xmotion = []
    ymotion = []
    rotation = []
    rms = []

    for cat in catlist:
        tmp = readsexcat(cat)
        
        nstars = len(tmp['X_IMAGE_DBL'])
        if nstars > 6:

            maxstars = min(MAXSTARS,nstars)
            xtmp = np.array(tmp['X_IMAGE_DBL'])
            ytmp = np.array(tmp['Y_IMAGE_DBL'])
            magtmp = np.array(tmp['MAG_AUTO'])
            
            sortndx = np.argsort(magtmp)
            xtmp = xtmp[sortndx[0:maxstars]]
            ytmp = ytmp[sortndx[0:maxstars]]
            magtmp = magtmp[sortndx[0:maxstars]]
            lindx2,lparm2 = segments.listseg(xtmp, ytmp, magtmp)
            
            # magic
            dx,dy,scale,rot,mat,flag,rmsf,nstf = \
                segments.fitlists4(naxis1,naxis2,lindx1,lparm1,lindx2,lparm2,\
                                       xref,yref,xtmp,ytmp,scl,dscl,thet,dthet)
        
            if flag <> -1:
                xmotion.append(dx)
                ymotion.append(dy)
                rotation.append(rot)
                rms.append(rmsf)

    return xmotion, ymotion, rotation, rms

if __name__ == '__main__':

    start_date = datetime(2013,9,20)
    end_date = datetime(2013,9,22)

    allseries = findseries('20130830','sqa','kb16')    
#    allcameras = findallcameras('20130830')
#    alldays = findalldays(start_date,end_date)

    for series in allseries:
        xmotion, ymotion, rotation, rms = register(series)
        print xmotion, ymotion, rotation, rms
