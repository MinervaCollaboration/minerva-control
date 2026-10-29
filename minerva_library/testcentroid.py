import utils2
import ipdb
from astropy.io import fits as pyfits
import glob
import datetime
import numpy as np
import os

filenames = glob.glob('/Data/t1/n20230213/*.fits')


for filename in filenames:
    image = pyfits.getdata(filename)

    t0 = datetime.datetime.utcnow()
    xybrightest = utils2.get_stars_brightest(image)
    if len(xybrightest) != 0:
        brightestndx = np.argmax(xybrightest[:,2])
        xbrightest = xybrightest[brightestndx][0]
        ybrightest = xybrightest[brightestndx][1]
    else:
        xbrightest = None
        ybrightest = None
    
    t1 = datetime.datetime.utcnow()
#    xydao = utils2.get_stars_dao(image)
#    if len(xydao) != 0:
#        brightestndx = np.argmax(xydao[:,2])
#        xdao = xydao[brightestndx][0]
#        ydao = xydao[brightestndx][1]
#    else:
#        xdao = None
#        ydao = None
    
    t2 = datetime.datetime.utcnow()
    xycv = utils2.get_stars_cv(image)
    if len(xycv) != 0:
        brightestndx = np.argmax(xycv[:,2])
        xcv = xycv[brightestndx][0]
        ycv = xycv[brightestndx][1]
    else:
        xcv = None
        ycv = None
    t3 = datetime.datetime.utcnow()

    xycom = utils2.get_stars_com(image)
    if len(xycom) != 0:
        brightestndx = np.argmax(xycom[:,2])
        xcom = xycom[brightestndx][0]
        ycom = xycom[brightestndx][1]
    else:
        xcom = None
        ycom = None
    t4 = datetime.datetime.utcnow()

    timebrightest = (t1-t0).total_seconds()
    timedao = (t2-t1).total_seconds()
    timecv = (t3-t2).total_seconds()
    timecom = (t4-t3).total_seconds()

#    print ''
#    print os.path.basename(filename), xbrightest, ybrightest, xdao, ydao, xcv, ycv, xcom, ycom, timebrightest, timedao, timecv, timecom
    print os.path.basename(filename), xbrightest, ybrightest, xcv, ycv, xcom, ycom, timebrightest, timecv, timecom
    f = open("centroid.txt", "a")
#    f.write(os.path.basename(filename)+' '+str(xbrightest)+' '+str(ybrightest)+' '+str(xdao)+' '+str(ydao)+' '+str(xcv)+' '+str(ycv)+' '+str(xcom)+' '+str(ycom)+' '+str(timebrightest)+' '+str(timedao)+' '+str(timecv)+' '+str(timecom)+'\n')
    f.write(os.path.basename(filename)+' '+str(xbrightest)+' '+str(ybrightest)+' '+str(xcv)+' '+str(ycv)+' '+str(xcom)+' '+str(ycom)+' '+str(timebrightest)+' '+str(timecv)+' '+str(timecom)+'\n')
    f.close()
    #print(os.path.basename(filename)+' '+str(xbrightest)+' '+str(ybrightest)+' '+str(xdao)+' '+str(ydao)+' '+str(xcv)+' '+str(ycv)+' '+str(timebrightest)+' '+str(timedao)+' '+str(timecv))
    #ipdb.set_trace()

#    print 'Brightest algorithm found star at ' + str(xbrightest) + ',' + str(ybrightest) + ' in ' + str(timebrightest) + ' seconds'
#    print 'DAO algorithm found star at ' + str(xdao) + ',' + str(ydao) + ' in ' + str(timedao) + ' seconds'
#    print 'CV algorithm found star at ' + str(xcv) + ',' + str(ycv) + ' in ' + str(timecv) + ' seconds'

    #ipdb.set_trace()
