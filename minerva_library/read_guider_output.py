from __future__ import division
from configobj import ConfigObj
#import matplotlib
#matplotlib.use('Agg')
import sys
import time
import pyfits as pf
import matplotlib.pyplot as plt
import os
import ipdb
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

def threshold_robust(frame, otsu = False):
    gray = np.round(frame*255.0/65535).astype('uint8')
    if otsu == False:
        val = np.max(gray)/10
        ret, th2 = cv2.threshold(gray, val, 0, cv2.THRESH_TOZERO)
    if otsu == True:
        ret, th2 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU )
    return th2

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

        if max_area == 0.0:
            return (-1,-1)

        # finding centroids of best_cnt and draw a circle there
        M = cv2.moments(best_cnt)
        cx,cy = (M['m10']/M['m00']), (M['m01']/M['m00'])
        
        return (cx, cy)

def grabguiderdata(filename):
    data, header = pf.getdata(filename, 0, header=True)
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

if __name__ == "__main__":
    rootdir = '/home/minerva/Desktop/test1'
    badpixelmask = load_badpix_data('/home/minerva/Desktop/minerva_fiber_guiding/guider/SBIG_11411_2x2badpixelmask.fits')
    if len(sys.argv)>1:
        outfile=sys.argv[1]
    else:
        outfile = 'read_guider_output_data.txt'
            
    plt.ion()
    plt.show()
    i=0
    while True:
        time.sleep(1)
        try:
            data, header = grabguiderdata(rootdir)
        except:
            pass
        bp_removed = removebadpix(data, badpixelmask)
        thresholded = threshold_binary(bp_removed)
        try:
            cx, cy = centroid_brightest_blob(thresholded)
            print cx, cy
            lx, ly = data.shape
            plt.imshow(data, origin='lower')
            plt.vlines([cx],0,lx, color = 'pink')
            plt.hlines([cy],0,ly, color = 'pink')
	    plt.title('Centroid: '+str(cx)+', '+str(cy))
            plt.draw()
            plt.clf()
            stringtowrite=(str(time.time())+", "+
             time.strftime("%D %H:%M:%S",time.localtime(time.time()))+", "+
             str(cx)+", "+
             str(cy)+"\n")
            print(stringtowrite)
        except:
            plt.imshow(data, origin='lower')
            plt.title("no centroid found")
            #plt.vlines([cx],0,lx, color = 'pink')
            #plt.hlines([cy],0,ly, color = 'pink')
            plt.draw()
            plt.clf()
            i=i+1
