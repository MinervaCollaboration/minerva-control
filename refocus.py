import subprocess, os, glob

import numpy as np
import matplotlib
matplotlib.use('Agg')

import ipdb

from astropy.io import fits
from minerva_library import af_utils


def sextract(datapath, imagefile, savepath=None, sexfile='autofocus.sex', 
            catfile = None, checkimage=None, params=None):
    '''
        Extract sources from a specific fits file
    '''
    sexpath = '/usr/share/sextractor/'
    sexcommand = 'sex '+ datapath+imagefile +' -c ' + sexpath+sexfile

    if savepath == None:
        savepath = datapath

    if catfile == None:
        catfile = imagefile.split('.fits')[0] + '.cat'
        sexcommand += ' -CATALOG_NAME ' + savepath+catfile

    if checkimage != None:
        sexcommand += ' -CHECKIMAGE_TYPE ' + checkimage
        check_file = imagefile.split('.fits')[0] + 'check.fits'
        sexcommand += ' -CHECKIMAGE_NAME ' + savepath+check_file

    if params != None:
        for key, value in params.items():
            sexcommand += ' -{} {}'.format(key, value)

    subprocess.call(sexcommand.split())

    return savepath+catfile

def redo_sextract(datapath, imagefile, param, values, savepath = None, checkimage=None):
    '''
        Try source extracting a specific fits file with over a range of values for some parameter
    '''
    files = []
    for value in values:
        if savepath == None:
            savefile = param.lower() + '_' + str(value).replace('.', '-') 
            savepath = datapath+savefile+'/'
        files.append(sextract(datapath, imagefile, savepath = savepath, 
                 checkimage = checkimage, params = {param:value}))

    return files

def getFocuserPosition(imagefile):
    '''
        Get the focuser position for one autofocus image
    '''
    hdu_list = fits.open(imagefile)
    try:
        pos = hdu_list[0].header['FOCPOS']
    except:
        ipdb.set_trace()

    return pos

def getFocus(catfile):
    '''
        Get FWHM of source for one catalog file
    '''
    try:
        fwhm, std, numstars = af_utils.new_get_hfr(f)
    except:
        fwhm, std, numstars = np.nan, np.inf, 0
    return fwhm


if __name__ == '__main__':

    telescopes = ['T1']
    night = 'n20220111'

    param = 'BACK_SIZE'
    param_values = [32, 64, 128, 256]

    for tel in telescopes:
        datapath = '/Data/' + tel.lower() + '/' + night + '/'
        os.chdir(datapath)

        savepaths = []

        for value in param_values:
            savefile = param.lower() + '_' + str(value).replace('.', '-') 
            if not os.path.exists(datapath+savefile):
                os.mkdir(datapath+savefile)
            savepaths.append(datapath+savefile+'/')

        imagefiles = glob.glob('*autofocus*.fits*')

#        ipdb.set_trace()

        imnum_all = np.array([int(image.split('.')[4]) for image in imagefiles])
        order = np.argsort(imnum_all)
        imnum_all = imnum_all[order]
        imagefiles = np.array(imagefiles)[order]

        splits = np.array([0])
        di = imnum_all[:-1] - imnum_all[1:]
        splits = np.append(splits, np.where(di < - 1)[0])
        splits = np.append(splits, -1)

        af_runs = []

        for i in range(len(splits)):
            af_runs.append(imagefiles[splits[i]+1:splits[i+1]])
#        ipdb.set_trace()
        for run in af_runs:
            pos_list = np.zeros(len(run))
            fwhm_list = np.zeros((4, len(run)))
            for i, image in enumerate(run):
#                ipdb.set_trace()

                funpack = 'funpack ' + image
                subprocess.call(funpack.split())

                uncomp_im = image.split('.fz')[0]
                pos = getFocuserPosition(uncomp_im)

                catfiles = redo_sextract(datapath, uncomp_im, param, param_values, checkimage='BACKGROUND')
                for j, cat in enumerate(catfiles):
                    fwhm_list[j, i] = getFocus(cat)
            
            for i in range(4):
                for j in range(len(af_runs)):
                    im0 = int(af_runs[j][0].split('.')[4])
                    imf = int(af_runs[j][-1].split('.')[4])
                    ar_filename = savepaths[i] + night + '.' + tel + '.autorecord.' + str(im0)+ '.'  + str(imf) + '.txt'

                    autodata = np.array([np.arange(im0, imf+1, 1), pos_list, fwhm_list[i]]).T
                    header =  'Column 1\tImage number\n'+\
                              'Column 2\tFocuser position\n'+\
                              'Column 3\tMedian focus measure'
                    np.savetxt(ar_filename, autodata, fmt='%s', header=header)


