from __future__ import division
import ipdb
import warnings
import sys
import os
import glob
import time
import pyfits as pf
#import matplotlib.pyplot as plt
import os
from scipy.ndimage import median_filter
import numpy as np
import cv2

def removebadpix(data, mask):
    medianed_image = median_filter(data, size=2)
    data[np.where(mask>0)] = medianed_image[np.where(mask>0)]
    return data

def load_badpix_data(badpixelfitsfile):
    data, header = pf.getdata(badpixelfitsfile, 
                  0,
                   header = True)
    return data

#def threshold_image(frame):
#    ipdb.set_trace()
#    gray = frame.astype('uint8')#cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
#    recolor = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
#    #ret2,th2 = cv2.threshold(gray,0,255,cv2.THRESH_OTSU) 
#    ret2,th2 = cv2.threshold(gray,200,255,cv2.THRESH_BINARY) 
#    ret3,th3 = cv2.threshold(gray,0,255,cv2.THRESH_TOZERO+cv2.THRESH_OTSU)
#    return {'binary':th2, 'tozero':th3}

def threshold_tozero(frame, otsu = False):
    gray = np.round(frame*255.0/65535).astype('uint8')
    if otsu == False:
        half = np.max(gray)/2
        ret, th2 = cv2.threshold(gray, half, 255, cv2.THRESH_TOZERO)
    if otsu == True:
        ret, th2 = cv2.threshold(gray, 0, 255, cv2.THRESH_TOZERO+cv2.THRESH_OTSU )
    return th2


def threshold_binary(frame, otsu = False):
    gray = np.round(frame*255.0/65535).astype('uint8')
    if otsu == False:
        half = np.max(gray)/2
        ret, th2 = cv2.threshold(gray, half, 255, cv2.THRESH_BINARY)
    if otsu == True:
        ret, th2 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU )
    return th2

def robust_std(x):
    y = x.flatten()
    n = len(y)
    y.sort()
    ind_qt1 = int(round((n+1)/4.))
    ind_qt3 = int(round((n+1)*3/4.))
    IQR = y[ind_qt3]- y[ind_qt1]
    lowFense = y[ind_qt1] - 1.5*IQR
    highFense = y[ind_qt3] + 1.5*IQR
    ok = (y>lowFense)*(y<highFense)
    yy=y[ok]
    return yy.std(dtype='double')

def threshold_robust(frame, otsu = False):
    gray = np.round(frame*255.0/65535).astype('uint8')
    if otsu == False:
        val = np.max(gray)/10
        ret, th2 = cv2.threshold(gray, val, 0, cv2.THRESH_TOZERO)
    if otsu == True:
        ret, th2 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU )
    return th2

def ds9(data):
    writeout(data, 'temp.fits')
    os.system('/Applications/ds9/ds9 temp.fits &')
    pass


def threshold_pyguide(image,level =3):
    stddev = robust_std(image)
    median = np.median(image)
    goodpix = image>median+stddev*level
    return goodpix

def centroid_brightest_blob(thresholded_image):
    
    contours,hierarchy = cv2.findContours(thresholded_image,
                                        cv2.RETR_LIST,
                                        cv2.CHAIN_APPROX_SIMPLE)
    if len(contours)==0:
        return (-1, -1) 
    
    else:
        max_area = 0
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > max_area:
                max_area = area
                best_cnt = cnt

        # finding centroids of best_cnt and draw a circle there
        M = cv2.moments(best_cnt)
        cx,cy = (M['m10']/M['m00']), (M['m01']/M['m00'])
        return (cx, cy)

def centroid_all_blobs(thresholded_image, areacutoff=30):
    thresholded_copy = thresholded_image.copy()
    contours,hierarchy = cv2.findContours(thresholded_copy,
                                        cv2.RETR_LIST,
                                        cv2.CHAIN_APPROX_SIMPLE)
    if len(contours)==0:
        return np.zeros((1, 3)) 
    
    else:
        outarray = np.zeros((1, 3))
        counter = 0
        for cnt in contours:
            M = cv2.moments(cnt)
            if M['m00']<areacutoff:
                counter = counter+1
                continue
            cx,cy,ssum = (M['m10']/M['m00']), (M['m01']/M['m00']), M['m00']
            outarray=np.vstack((outarray, np.array((cx, cy, ssum))))
    return outarray[1:,:]


def grabguiderdata(rootdir):
    files=[] 
    for dirpath,_,filenames in os.walk(rootdir):
        for f in filenames:
            if '.fit' in f:
                files.append(os.path.abspath(os.path.join(dirpath, f)))

    targfile= files[0]
    data, header = pf.getdata(targfile, 0, header=True)
    return (data, header)

def get_centroid(rootdir, badpixelmask = None):
    data, header = grabguiderdata(rootdir)
    if badpixelmask is not None:
        badpixelmask = load_badpix_data(badpixelmask)
        bp_removed = removebadpix(data, badpixelmask)
    else:
        bp_removed = data
    thresholded = threshold_binary(bp_removed)
    cx, cy = centroid_brightest_blob(thresholded)
    #print "Centroid", cx, cy
    return {'data':data,
        'header':header,
        'processed':thresholded,
        'xcen':cx, 
        'ycen':cy}

def writeout(data, outputfile, header=None, comment=None):
    pf.writeto(outputfile, data, header=header, clobber=True)
    writtenfile = pf.open(outputfile)
    if comment is not None:
        writtenfile[0].header.set('COMMENT', comment)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        writtenfile.writeto(outputfile, output_verify='ignore', clobber=True)
        writtenfile.close()
 
def getfitsdata(fname):
    hdulist = pf.open(fname)
    if '.fz' in fname:
        data = hdulist[1].data
    else: data = hdulist[0].data
    hdulist.close()
    return data
   

 
if __name__ == "__main__":

    filepath = "C:\minerva\data\\n20150207\*M77*.fits.fz"
    print glob.glob(filepath)
    print filepath
    for f in glob.glob(filepath):
        print(f)
        d= getfitsdata(f)
        th = threshold_pyguide(d, level = 4)
        imtofeed = np.array(np.round((d*th)/np.max(d*th)*255), dtype='uint8')
        cc = centroid_all_blobs(imtofeed)
        print(cc)
        print('\n')
        ipdb.set_trace()
        #ds9(d)
