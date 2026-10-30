import numpy as np
import matplotlib.pyplot as plt
import glob
import sys
import socket
import os
from astropy.io import fits
import ipdb

def plot_fits(night = 'n20160614'):
    if socket.gethostname() == 'Kevins-MacBook.local': 
        File_path = '/Users/Kevin/Documents/'+night+'.*.fits'
    else: 
        File_path = '/Data/kiwispec/'+night+'/*.*.fits'
    
    F_F = glob.glob(File_path)
    N_images=(len(F_F))
    N_x = np.ceil(np.sqrt(N_images))
    N_y = np.ceil(float(N_images)/(N_x))
    plt.figure(figsize=(6*N_x,4*N_y))

    file_Plot_name = os.path.dirname(File_path)+'/'+night+'.spectra.subplot.png'
    print file_Plot_name
    for i, fitsname in enumerate(F_F):
        
        plt.subplot(N_y,N_x,i+1)
        ax = plt.gca()
        image_data = fits.getdata(fitsname)
        try:
            ax.imshow(image_data[100+25:201+25,100:201],interpolation='None',vmin=np.percentile(image_data[100+25:201+25, 100:201], 5),vmax=np.percentile(image_data[100+25:201+25, 100:201], 95),cmap='gray',aspect=1.,origin='lower')
        except:
            pass
        ax.set_xticks([0,25,50,75,100])
        ax.set_yticks([0,25,50,75,100])
        plt.title(os.path.basename(fitsname))

    plt.tight_layout()
    plt.savefig(file_Plot_name, dpi=300)
    return file_Plot_name

   
   

    
if __name__== '__main__':

    if len(sys.argv)==2:
        end_night = str(sys.argv)[1]
    else: 
        end_night = 'n20160614'
    file_Plot_name = plot_fits(night = end_night)


