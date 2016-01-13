import matplotlib.pyplot as plt
import datetime
import numpy as np
import ipdb
import glob
import os
import csv
from scipy.ndimage import gaussian_filter1d


def smooth(y, box_pts):
    return gaussian_filter1d(y,box_pts)
    if len(y) < box_pts:
        return np.nan
    box = np.ones(box_pts)/box_pts
    y_smooth = np.convolve(y, box, mode='same')
    return y_smooth

filename = ['/Data/kiwilog/n20151215/spec_pressure.log']
filename = ['/Data/kiwilog/n20151215/pump_pressure.log']
#filename = ['/home/minerva/minerva-control/log/n20151215/temp.A.1.log']

night = 'n20151227'
expmeter = False
pressure =True
ymin = None
ymax = None
smoothwidth = 20

xtitle = "Time (UTC)"
fig = plt.figure()
ax = fig.add_subplot(121)
#plt.subplot(121)

if expmeter:
    filenames = glob.glob('/Data/kiwilog/' + night + '/expmeter.dat')
    title = 'Exposure Meter'
    ytitle = 'Flux'
    imname = night + '.expmeter.png'
elif pressure:
    filenames = glob.glob('/Data/kiwilog/' + night + '/????_pressure.log')
    title = 'Vacuum Pressure'
    ytitle = 'Pressure (mbar)'
    imname = night + '.pressure.png'
else:
    filenames = glob.glob('/home/minerva/minerva-control/log/' + night + '/temp.?.?.log')
    title = 'Temperatures'
    ytitle = 'Temperature (C)'
    ymin = 22.9
    ymax = 23.3
#    ymin = 17.5
#    ymax = 23.5
    imname = night + '.temperature.png'
    filename = '/Data/thermallog/Thermal Enclosure Log ' + night[1:5] + '-' + night[5:7] + '-' + night[7:9] + ' UTC.csv'
    with open(filename,'rb') as csvfile:
        reader = csv.reader(csvfile)#,delimiter=',')
        temperatures = list(reader)

        labels = temperatures[0]
        dates = []
        for i in range(len(temperatures)-1):
            dates.append(datetime.datetime.strptime(temperatures[i+1][0] + temperatures[i+1][1],"'%Y-%m-%d''%H:%M:%S'"))

        for i in range(len(labels)-4):
            values = np.array([x[i+4] for x in temperatures[1:]])
            valuesf = values.astype(np.float)
            good = np.where(np.isfinite(valuesf))
            aveval = round(np.mean(smooth(valuesf[good],smoothwidth)),5)
            sigma = round(np.std(smooth(valuesf[good],smoothwidth)),5)
            valuesf = smooth(valuesf[good],smoothwidth)
            datesnp = (np.array(dates,dtype='datetime64[us]'))[good].astype(datetime.datetime)
            ax.plot(datesnp,valuesf,label=labels[i+4] + " (" + str(aveval) + " +/- " + str(sigma) + ")")
            

ax.set_title(title)
ax.set_xlabel(xtitle)
ax.set_ylabel(ytitle)
 
for filename in filenames:

    dates = []
    values = []

    with open(filename) as fh:
    
        lines = fh.readlines()
        for line in lines:
            entries = line.split(',')
            if len(entries) >= 2:
                try: 
                    values.append(float(entries[1]))
                    dates.append(datetime.datetime.strptime(entries[0],'%Y-%m-%d %H:%M:%S.%f'))
                except:
                    pass
            if len(entries) == 3:
                label = entries[2].strip()
            else: label = os.path.basename(filename).strip()


        values = np.array(values)
        valuesf = values.astype(np.float)
        good = np.where(np.isfinite(valuesf))
        aveval = round(np.mean(smooth(valuesf[good],smoothwidth)),5)
        sigma = round(np.std(smooth(valuesf[good],smoothwidth)),5)
        datesnp = (np.array(dates,dtype='datetime64[us]'))[good].astype(datetime.datetime)
        ax.plot(datesnp,smooth(valuesf,smoothwidth),label=label + " (" + str(aveval) + " +/- " + str(sigma) + ")")

#        ax.plot(dates,values,label=label)



ax.legend(bbox_to_anchor=(1, 1), loc=2, borderaxespad=0.0)
#ax.locator_params(axis='x',nbins=4)

if ymin <> None and ymax <> None:
    ax.set_ylim([ymin,ymax])

plt.savefig(imname)
plt.show()
#data = np.loadtxt(filename)

#ipdb.set_trace()


