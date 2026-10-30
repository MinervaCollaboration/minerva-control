import warnings
import numpy as np
from scipy.ndimage import sobel
import os
import commands
import pyfits
import time
import sys
from datetime import datetime,timedelta
import urllib2
warnings.simplefilter("ignore")
import Image
from scipy import fftpack
import matplotlib
matplotlib.use('Agg')
import pylab as pl

def imsub():

    current = 'http://skycam.mmto.arizona.edu/skycam/latest_image.png'

    current = commands.getoutput('ls /data/images/AllSky/AllSkyImage0*.FIT | tail -2').split('\n')[1]

    try:
        im2 = np.array(pyfits.getdata(current),dtype=float)
    except:
        print "Error reading", im2
        return

    hdr2 = pyfits.getheader(current)
    last = commands.getoutput('ls /data/images/AllSky/AllSkyImage0*.FIT | tail -2').split('\n')[0]
    im1 = np.array(pyfits.getdata(last),dtype=float)
    head = pyfits.getheader(last)
    t = datetime.fromtimestamp(os.path.getctime(last))
    expcurrent = float(hdr2['EXPTIME'])
    explast = float(head['EXPTIME'])
    exp2 = expcurrent
    exp1 = explast
#    mask = pyfits.getdata('/var/www/cgi-bin/cloudsensor/mask.fits')

    print last, current
    if expcurrent == 0 or explast == 0:
        expcurrent = explast = exp1 = exp2 = 0.00001
        print "Exposure too short", expcurrent, explast
        #return

    if np.mean(im2) < 2000.0 or np.mean(im1) < 2000:
        print "Mean of too low: %6.1f < 2500.0" % np.mean(im2)
        return

    #print exp2,exp1
    # Use scaled .jpgs for image subtraction
    #jpg2 = Image.open(current.replace('.FIT','.JPG'))
    #jpg2 = np.sum(np.array(jpg2,dtype=float),axis=2)
    #jpg1 = Image.open(last.replace('.FIT','.JPG'))
    #jpg1 = np.sum(np.array(jpg1,dtype=float),axis=2)
    #diff = np.abs(jpg2 - jpg1)

    diff =  np.abs(im2 - im1)
    sx = sobel(im2,axis=0,mode='constant')
    sy = sobel(im2,axis=1,mode='constant')
    sob = np.hypot(sx,sy)

    fimage = fftpack.fftshift(fftpack.fft2(fftpack.fftshift(sob)))#*mask)))
    ft = np.abs(fimage)*np.abs(fimage)
    pl.clf()
    fig = pl.figure()
    pl.imshow(np.log10(ft))
    pl.savefig('/data/images/AllSky/clouds/ft.png')

    diffim = current.replace('AllSkyCurrent','DiffCurrent')
    edgeim = current.replace('AllSkyCurrent','EdgeCurrent')
    diffim = '/data/images/AllSky/DiffCurrentImage.FIT'
    edgeim = '/data/images/AllSky/EdgeCurrentImage.FIT'
    os.system('rm -f %s' % diffim)
    os.system('rm -f %s' % edgeim)
    pyfits.writeto('%s' % diffim, diff)
    pyfits.writeto('%s' % edgeim, sob)
    head = pyfits.getheader(diffim)
    head.update('DATE-OBS',datetime.strftime(t,format='%Y-%m-%dT%H:%M:%S.%f'))
    pyfits.writeto('%s' % diffim, diff,head,clobber=True)
    pyfits.writeto('%s' % edgeim, sob,head,clobber=True)
    os.system('/usr/local/bin/fits2jpeg -fits %s -jpeg %s -min 0.0 -max 10000 ; convert %s -flip -quality 70 %s' % (edgeim,edgeim.replace('.FIT','.JPG'),edgeim.replace('.FIT','.JPG'),edgeim.replace('.FIT','.JPG')))
    os.system('/usr/local/bin/fits2jpeg -fits %s -jpeg %s -min 0.0 -max 2000 -nonLinear ; convert %s -flip -quality 70 %s' % (diffim,diffim.replace('.FIT','.JPG'),diffim.replace('.FIT','.JPG'),diffim.replace('.FIT','.JPG')))

    os.system('rsync -az %s bfulton@pydevsba:public_html/cgi-bin/cloudsensor/' % edgeim.replace('.FIT','.JPG'))
    os.system('rsync -az %s bfulton@pydevsba:public_html/cgi-bin/cloudsensor/' % diffim.replace('.FIT','.JPG'))

def stats():

    print "Calculating image statistics"
    try:
        im2 = pyfits.getdata(current)
    except ValueError:
        print "Error reading image, returning defaults."
        return defaults

    hdr2 = pyfits.getheader(current)
    last = commands.getoutput('ls /data/images/AllSky/AllSkyImage0*.FIT | tail -2').split('\n')[0]
    im1 = pyfits.getdata(last)
    head = pyfits.getheader(last)
    t = datetime.fromtimestamp(os.path.getctime(last))
    expcurrent = float(hdr2['EXPTIME'])
    explast = float(head['EXPTIME'])
    mask = np.array(pyfits.getdata('mask.fits'),dtype=bool)

    #from scipy.signal import correlate2d
    #corr = correlate2d(im1,im2)
    #pyfits.writeto('corr.fits',corr,clobber=True)

    if expcurrent == 0 or explast == 0:
        expcurrent = 0.00001
        print "Exposure too short"
        #return
   
    head = pyfits.getheader(current)
    diff = pyfits.getdata(diff_file)
    sob = pyfits.getdata(edge_file)
    im2 = im2[mask]
    diff = diff[mask]
    sob = sob[mask]

    newdiff = np.median(diff)

    try:
        olddiffs = np.genfromtxt('/data/images/AllSky/clouds/%s.txt' % datetime.strftime(datetime.utcnow(),format="%Y%m"),dtype=float,invalid_raise=False,usecols=(2))
        alldiffs = np.hstack((newdiff,olddiffs[-3:]))
        print alldiffs
        diffval = np.mean(alldiffs)
    except (TypeError,IOError):
        print "Error reading old diff values."
        diffval = newdiff

    bright = -2.5*np.log10((np.median(im2)-1000.0)/(expcurrent*1090.26**2)) + skyzpt
    #bright = np.log10(np.median(im2)/expcurrent) * bright_scale
    edges = np.mean(sob)
    tstamp = pyfits.getheader('/data/images/AllSky/DiffCurrentImage.FIT')['DATE-OBS']
    stddev = np.std(im2)
    #print "Standard deviation =", std

    diffok = (diffval < diff_limit)
    edgeok = (edges < edge_high) and (edges > edge_low)
    brightok = (bright > bright_limit)

    clear = int(diffok)+int(edgeok)+int(brightok) >= 2
    clearvotes = int(diffok)+int(edgeok)+int(brightok)

    ##Foggy conditions
    if edges < 800.0 and bright > 20.0:
        clearvotes -= 1
        verdict,reason = ("Foggy"," (too few stars)")
    #print diffok,edgeok,brightok,clearvotes

    if (bright < 8.0):
        verdict = "Daylight"
        values = {'verdict':verdict,'bright':bright,'diffval':diffval,'edges':edges,'stddev':stddev,'votes':clearvotes,'tstamp':tstamp}
        return values
    elif clearvotes >= 2:
        verdict = "Clear"
    elif clearvotes == 1:
        verdict = "Partly Cloudy"
    elif clearvotes == 0:
        verdict = "Cloudy"

    if not brightok:
        reason = " (too bright)"
    elif (edges < (edge_low)):
        reason =" (too few stars)"
    elif not diffok:
        reason = " (too much motion)"
    elif (edges > (edge_high)):
        reason = " (too many edges)"

    if verdict != "Daylight" and verdict != "Clear":
        verdict += reason

    values = {'verdict':verdict,'bright':bright,'diffval':diffval,'edges':edges,'stddev':stddev,'votes':clearvotes,'tstamp':tstamp}
    return values

def readvals():
    clouds = urllib2.urlopen('http://cc1.sqa.lco.gtn/images/AllSky/clouds/simple.html')
    data = clouds.read().split()
    tstamp = data[0]
    bright = float(data[1])
    diffval = float(data[2])
    edges = float(data[3])
    clearvotes = int(data[5])
    verdict = (' ').join(data[6:])
    stddev = float(data[4])

    values = {'verdict':verdict,'bright':bright,'diffval':diffval,'edges':edges,'stddev':stddev,'votes':clearvotes,'tstamp':tstamp}
    return values

def moonphase(outfile='/var/www/html/moonphase/moon_current.png'):
    print "Creating moon image."
    os.system('xplanet -config /var/www/html/moonphase/moon.conf -origin earth -target moon -geometry 200x200 -num_times 1 -transpng %s' % outfile)
    os.system('rsync -az %s bfulton@pydevsba:public_html/cgi-bin/cloudsensor/' % outfile)

def mkplot(input='/data/images/AllSky/clouds/%s.txt' % datetime.strftime(datetime.utcnow(),format="%Y%m"),output='/data/images/AllSky/clouds/plot_current.png'):
    print "Generating plot"
    import matplotlib
    matplotlib.use('Agg')
    import pylab as pl
    data = np.genfromtxt(input,dtype=str,invalid_raise=False,usecols=(0,1,2,3,4,5))
    tstamps = data[:,0]
    tstamps = [datetime.strptime(t,'%Y-%m-%dT%H:%M:%S.%f') for t in tstamps]
    brightness = np.array(data[:,1],dtype=float)
    diffvals = np.array(data[:,2],dtype=float)
    edgevals = np.array(data[:,3],dtype=float)
    stddevs = np.array(data[:,4],dtype=float)
    clearvotes = np.array(data[:,5],dtype=int)
    
    #brightness = (-brightness + 19.5 + 2.0) / 2.0
    diffvals /= 150.0
    edgevals /= 1800.0
    edgevals = (edgevals*1.25) - 0.25
    clearvotes = (-clearvotes/3.0 + 1) * 2.48
    stddevs /= 2000.0
    
    fig = pl.figure(figsize=(8,3.70))
    #b = pl.plot(tstamps,brightness,'.-',linewidth=2.0)
    d = pl.plot(tstamps,diffvals,'go',linewidth=2.0)
    e = pl.plot(tstamps,edgevals,'ro',linewidth=2.0)
    v = pl.plot(tstamps,clearvotes,'m-',linewidth=3.0)
    s = pl.plot(tstamps,stddevs,'ko',linewidth=3.0)
    
    pl.grid(True)
    pl.ylim(0.0,2.5)
    
    pl.xlabel('Time')
    pl.ylabel('Low                      High')

    ax = pl.gca()
    ax2 = ax.twinx()
    ax2.set_ylim(22.0,16.0)
    b = ax2.plot(tstamps,brightness,'bo',linewidth=2.0)
    pl.ylabel('Brightness (mag/")')

    dateFmt = pl.matplotlib.dates.DateFormatter('%H:%M')
    ax.xaxis.set_major_formatter(dateFmt)
    ax.yaxis.set_major_formatter(pl.matplotlib.ticker.NullFormatter())
    pl.xlim(datetime.utcnow() - timedelta(hours=8),datetime.utcnow())

    pl.legend((b[0],d[0],e[0],s[0],v[0]),('Brightness','Motion','Edges','StdDev','Cloud Cover'),loc=2,numpoints=1,handletextpad=0.5,handlelength=0.5,labelspacing=0.3)

    #hourLoc = pl.matplotlib.dates.HourLocator()
    #ax.xaxis.set_major_locator(hourLoc)
    pl.savefig(output)
    os.system('rsync -az %s bfulton@pydevsba:public_html/cgi-bin/cloudsensor/' % output)
