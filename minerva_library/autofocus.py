import matplotlib.pyplot as plt
import numpy as np
import get_all_centroids as gac
from get_all_centroids import *
import astropy
from astropy.modeling import fitting , models
import ipdb


def getstars(imageName):
    d = getfitsdata(imageName)
    th = threshold_pyguide(d, level = 4)
    imtofeed = np.array(np.round((d*th)/np.max(d*th)*255),dtype='uint8')
    cc = centroid_all_blobs(imtofeed)
    return cc

if __name__ == "__main__":
    print 'stop'

    #fh = '/Data/t2/n20150528/n20150528.T2.EPIC2015.B.0041.fits.fz'
    fh = '/Data/t1/n20150928/n20150928.T1.KS14C088137.ip.0166.fits.fz'
    ipdb.set_trace()
    raw = getfitsdata(fh)
    stars = getstars(fh)
    print stars
    star_num = int(raw_input('star number'))
    star = stars[star_num-1]
    xind = int(star[1])
    yind = int(star[0])



