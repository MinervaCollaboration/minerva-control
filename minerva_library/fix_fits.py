#!/usr/bin/env python 2.7

#Trying to re-write headers, etc with pyfits
import pyfits
import numpy as np
import os
import datetime
import argparse
import ipdb
import glob
import warnings

def fix_fits(filename, newfilename=None, newpath=None, logger=None):

    # Load in "raw" data
    t0 = datetime.datetime.utcnow()
    py1 = pyfits.open(os.path.join(filename),ignore_missing_end=True,uint=True)
    data = py1[0].data
    hdr = py1[0].header

    # if PARAM0 keyword is present, this is the original header -- this image did not complete successfully
    if 'PARAM0' in hdr:
        print 'Warning: ' + filename + ' has the original header; skipping'
        return

    # this header has already been fixed!
    if hdr['SIMPLE']:
        print filename + ' is already a legal FITS image'
        return

    # delete COMMENT
    del hdr['COMMENT']

    # Dimensions
    naxis1 = hdr['NAXIS1']
    naxis2 = hdr['NAXIS2']

    # Test to make sure this logic is robust enough for varying inputs
    if np.shape(data)[0] > naxis1:
        data_new = np.resize(data,[naxis2,naxis1,2])
    else: ipdb.set_trace()

    # Data is split into two 8 bit sections (totaling 16 bit).  Need to join
    # these together to get 16 bit number.  There must be a faster way...
    data_16bit = np.zeros((naxis2,naxis1),dtype=np.uint16)
    for row in range(naxis2):
        for col in range(naxis1):
            #Join binary strings
            binstr = "{:08d}{:08d}".format(int(bin(data_new[row,col,0])[2:]),
                                           int(bin(data_new[row,col,1])[2:]))
            data_16bit[row,col] = int(binstr,base=2)

    # make new hdu, hdulist, then write to file
    hdu_new = pyfits.PrimaryHDU(data_16bit,uint=True)

    # transfer all the header keywords (hdr not legal either)
    for card in hdr.cards:
        # skip the standard ones already created
        if card.keyword not in hdu_new.header:
            hdu_new.header.append(card)
    hdu_new.header['BZERO'] = 0

    # the original DATE-OBS keyword, identified by its comment, is in local time; update to UTC
    if hdr.comments['DATE-OBS'] == 'DATE-OBS Format is YYYY-MM-DDThh:mm:ss.sss':
        fmt = '%Y-%m-%dT%H:%M:%S.%f'
        dateobs = (datetime.datetime.strptime(hdr['DATE-OBS'],fmt) + datetime.timedelta(hours=7)).strftime(fmt)[:-3]
        hdu_new.header['DATE-OBS'] = (dateobs,'UTC at exposure start')

    # if new filename not specified, clobber the old one
    if newfilename == None:
        newfilename = os.path.basename(filename)

    if newpath <> None:
        path = newpath
        if not os.path.exits(path):
            os.mkdir(path)
    else: path = os.path.dirname(filename)
    
    newfilename = os.path.join(path,newfilename)

    # write the fixed file
    hdulist_out = pyfits.HDUList([hdu_new])

    # suppress the overwriting warning
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        hdulist_out.writeto(os.path.join(newfilename),clobber=True)

def fix_dir(directory,newpath=None):
    files = glob.glob(directory + '/*.fits')

    for filename in files:
        print 'Fixing ' + filename
        fix_fits(filename,newpath=newpath)

if __name__ == "__main__":

    fix_dir('/Data/kiwispec/n20160115/',newpath='/Data/kiwispec/n20160115/bak/')

    ipdb.set_trace()

    parser = argparse.ArgumentParser(description='Standardize the FITS image from Spectral Instruments')
    parser.add_argument('--filename'   , dest='filename'   , action='store', type=str              , help='filename of the original FITS image to fix')
    parser.add_argument('--newfilename', dest='newfilename', action='store', type=str, default=None, help='filename of the new (fixed) FITS image, if not specified, it will clobber the original')
    parser.add_argument('--newpath'    , dest='newpath'    , action='store', type=str, default=None, help='path of the new (fixed) FITS image, if not specified, it will place it in the same path as the original')

    opt = parser.parse_args()

    fix_fits(opt.filename, newfilename=opt.newfilename, newpath=opt.newpath)
