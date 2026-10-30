import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import glob
from astropy.io import fits

filepath = '/Data/kiwispec/n20210513/'
filename = 'n20210503.TOI1151_01.0022.fits'

hdu_list = fits.open(filepath + filename)

spec = hdu_list[0]
l = hdu_list[1]

for i in range(len(spec[0, :])):
    plt.plot(l[:, i][0], spec[:, i][0], 'o', color = 'C0')
    plt.xlabel(r'Wavelength ($\AA$)')
    plt.ylabel('Intensity')
    plt.xlim(5000, 6500)
    plt.ylim(0, 7e3)
    plt.savefig(filepath + 'testspec_' + str(i+1) + '.png', bbox_inches = 'tight')
