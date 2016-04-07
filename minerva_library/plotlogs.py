import matplotlib.pyplot as plt
import datetime
import numpy as np
import ipdb
import glob
import os
import csv
from scipy.ndimage import gaussian_filter1d
import argparse, warnings


def smooth(y, box_pts):
    return gaussian_filter1d(y,box_pts)
    if len(y) < box_pts:
        return np.nan
    box = np.ones(box_pts)/box_pts
    y_smooth = np.convolve(y, box, mode='same')
    return y_smooth

def plotlogs(night, expmeter=False, pressure=False,ymin=None, ymax=None, smoothwidth=20):

#    night = 'n20160119'
#    expmeter = False
#    pressure =False
#    ymin = None
#    ymax = None
#    smoothwidth = 20

    xtitle = "Time (UTC)"
    fig = plt.figure()
    ax = fig.add_subplot(121)

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
#        ymin = 22.9
#        ymax = 23.3
#        ymin = 17.5
#        ymax = 23.5
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
                    except: pass
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


    ax.legend(bbox_to_anchor=(1, 1), loc=2, borderaxespad=0.0)

    if ymin <> None and ymax <> None:
        ax.set_ylim([ymin,ymax])

    plt.savefig(imname)
    plt.show()

if __name__ == "__main__":


    today = 'n' + datetime.datetime.utcnow().strftime('%Y%m%d')

    parser = argparse.ArgumentParser(description='Plot the temperatures, pressures, or exposure meter data for a given night')
    parser.add_argument('--night'      , dest='night'       , action='store'     , type=str  , default=today, help='the night to plot')
    parser.add_argument('--pressure'   , dest='pressure'    , action='store_true'            , default=False, help='plot the pressure for the night')
    parser.add_argument('--expmeter'   , dest='expmeter'    , action='store_true'            , default=False, help='plot the expmeter for the night')
    parser.add_argument('--ymin'       , dest='ymin'        , action='store'     , type=float, default=None , help='the minimum y value to plot')
    parser.add_argument('--ymax'       , dest='ymax'        , action='store'     , type=float, default=None , help='the minimum y value to plot')
    parser.add_argument('--smoothwidth', dest='smoothwidth' , action='store'     , type=float, default=20.0 , help='the number of points to smooth over for plotting')

    opt = parser.parse_args()

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        plotlogs(opt.night, pressure=opt.pressure, expmeter=opt.expmeter, ymin=opt.ymin, ymax=opt.ymax, smoothwidth=opt.smoothwidth)


