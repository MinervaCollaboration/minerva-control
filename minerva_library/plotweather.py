import matplotlib
matplotlib.use('Agg',warn=False)

import matplotlib.pyplot as plt
import datetime
import numpy as np
import ipdb
import glob
import os
import csv
from scipy.ndimage import gaussian_filter1d
import argparse, warnings
import env
import control
import re
from collections import OrderedDict
import sys
import ephem

def plotweather(minerva, night=None):

    if night == None:
#        minerva.night
        night = datetime.datetime.strftime(datetime.datetime.utcnow(),'n%Y%m%d')        

    logs = glob.glob(minerva.base_directory + '/log/' + night + '/*.log')

    weatherstats = OrderedDict()
    weatherstats['wxt510Rain'] = {'values':[],'ytitle':'Rain (mm)','yrange':[0.0,None]}
    weatherstats['barometer'] = {'values':[],'ytitle':'Pressure (mbar)','yrange':[990.0,1040.0]}
    weatherstats['windGustSpeed'] = {'values':[],'ytitle':'Wind Gust (mph)','yrange':[0.0,None]}
    weatherstats['windSpeed'] = {'values':[],'ytitle':'Wind Speed (mph)','yrange':[0.0,None]}
    weatherstats['windDirectionDegrees'] = {'values':[],'ytitle':'Wind Dir (Deg E of N)','yrange':[None,None]}
    weatherstats['outsideHumidity'] = {'values':[],'ytitle':'Humidity (%)','yrange':[0.0,100.0]}
    weatherstats['outsideDewPt'] = {'values':[],'ytitle':'Dewpoint (C)','yrange':[None,None]}
    weatherstats['outsideTemp'] = {'values':[],'ytitle':'Temp (C)','yrange':[None,None]}
    weatherstats['MearthCloud'] = {'values':[],'ytitle':'Mearth Sky (C)','yrange':[-50.0,0.0]}
    weatherstats['HATCloud'] = {'values':[],'ytitle':'HAT Sky (C)','yrange':[-60.0,0.0]}
    weatherstats['AuroraCloud'] = {'values':[],'ytitle':'Aurora Sky (C)','yrange':[-50.0,0.0]}
    weatherstats['MINERVACloud'] = {'values':[],'ytitle':'MINERVA Sky (C)','yrange':[-40.0,0.0]}

    domestate = []
    domex = []
    domey = []
#    ipdb.set_trace()
    for log in logs:
        with open(log,'r') as f:
            for line in f:
                # Search for weather lines
                if re.search('=',line):
                    try: key = line.split('=')[-2].split()[-1]
                    except: key = 'fail'
                    if key in weatherstats.keys():
                        try: time = datetime.datetime.strptime(line.split()[0],"%Y-%m-%dT%H:%M:%S")
                        except: time = datetime.datetime.strptime(line.split()[0],"%Y-%m-%dT%H:%M:%S.%f")
                        try:
                            value = float(line.split('=')[-1].strip())
                            weatherstats[key]['values'].append((time,value))
                        except: pass
#                if re.search('DEBUG: aqawan.: Enclosure ',line):   # works fine when domes open and close together
                if re.search('DEBUG: aqawan1: Enclosure ',line):    # temp fix for aqawan2 being broken now
                    try: time = datetime.datetime.strptime(line.split()[0],"%Y-%m-%dT%H:%M:%S")
                    except: time = datetime.datetime.strptime(line.split()[0],"%Y-%m-%dT%H:%M:%S.%f")
                    domex.append(time)
                    domey.append(line.split(' ')[7])
#                    ipdb.set_trace()

    startnight = datetime.datetime.strptime(night,"n%Y%m%d")
    minerva.site.obs.horizon = '-12'
    sunset = minerva.site.obs.next_setting(ephem.Sun(), start=startnight, use_center=True).datetime()
    sunrise = minerva.site.obs.next_rising(ephem.Sun(), start=startnight, use_center=True).datetime()
    

    nx = 4
    ny = 3
    fig, ax = plt.subplots(nx,ny)
    fig.tight_layout()
    fig.set_size_inches(13,8.5)
    filename = minerva.base_directory + '/log/' + night  + '.weather.png'

    nplots = 0
    for key in weatherstats.keys():
        x = [a[0] for a in weatherstats[key]['values']]
        y = np.asarray([a[1] for a in weatherstats[key]['values']])

        t0 = datetime.datetime.strptime(night,'n%Y%m%d')
#        t0 = datetime.datetime(x[0].year,x[0].month,x[0].day)
        time = np.asarray([(a - t0).total_seconds()/3600.0 for a in x])
        xtitle = "Hours since UTC " + datetime.datetime.strftime(t0,'%Y-%m-%d')

        sunrisehr = (sunrise - t0).total_seconds()/3600.0
        sunsethr = (sunset - t0).total_seconds()/3600.0

        yi = nplots/nx 
        xi = nplots -yi*nx

        # Wind Gust values are littered with zeros that make the plot messy; take them out
#        if 'Gust' in key:
#            good = np.where(y != 0.0)
#            time = time[good]
#            y = y[good]


        # wrap around effects (0 to 359) make the plot messy, fix that
        if 'Direction' in key:
            for i in range(len(y)-1):
                if y[i] - y[i+1] > 180.0:
                    y[i+1] += 360.0
                if y[i] - y[i+1] < -180.0:
                    y[i+1] -= 360.0
            # there are no limits
            minerva.site.closeLimits[key][0] = -9999
            minerva.site.closeLimits[key][1] = 9999
            minerva.site.openLimits[key][0] = -9999
            minerva.site.openLimits[key][1] = 9999

        print nplots, xi, yi, minerva.site.openLimits[key][0], minerva.site.openLimits[key][1], minerva.site.closeLimits[key][0], minerva.site.closeLimits[key][1],key

        # plot the value of the key (i.e., the weather parameter) vs time
        ax[xi,yi].plot(time,y,label=key)

        # shade extreme low values red
        ax[xi,yi].axhspan(-9999, minerva.site.closeLimits[key][0],facecolor='r',alpha=0.5)

        # shade extreme high values red
        ax[xi,yi].axhspan(minerva.site.closeLimits[key][1],9999,facecolor='r',alpha=0.5)

        # denote the (less conservative) open limits with a horizontal line
        ax[xi,yi].axhline(y=minerva.site.openLimits[key][0])
        ax[xi,yi].axhline(y=minerva.site.openLimits[key][1])

        # shade the regions where the sun is up yellow
        ax[xi,yi].axvspan(-999,sunsethr,facecolor='y',alpha=0.5)
        ax[xi,yi].axvspan(sunrisehr,999,facecolor='y',alpha=0.5)

        # set the axis labels
        ax[xi,yi].set_ylabel(weatherstats[key]['ytitle'])
        ax[xi,yi].set_xlabel(xtitle)

        # shade the times when the dome was closed grey
        dometime = [(a - t0).total_seconds()/3600.0 for a in domex]
        lastdome = 'open;'
        for i in range(len(domey)):
            if domey[i] == 'closed;':
                if lastdome == 'open;':
                    startshade = dometime[i]
                    lastdome = 'closed;'
                elif lastdome == 'closed;':
                    pass # was closed, stayed closed
            elif domey[i] == 'open;':
                if lastdome == 'open;':
                    pass # was open, stayed open
                elif lastdome == 'closed;':
                    ax[xi,yi].axvspan(startshade,dometime[i],facecolor='black',alpha=0.5)
#                    print startshade, dometime[i]
                    lastdome = 'open;'
        if lastdome == 'closed;':
            ax[xi,yi].axvspan(startshade,dometime[-1],facecolor='black',alpha=0.5)

        # set the plotting ranges
        if weatherstats[key]['yrange'][0] == None: weatherstats[key]['yrange'][0] = min(y)
        if weatherstats[key]['yrange'][1] == None: weatherstats[key]['yrange'][1] = max(y)
        if weatherstats[key]['yrange'][0] == weatherstats[key]['yrange'][1]: 
            weatherstats[key]['yrange'][1] = weatherstats[key]['yrange'][0] + 1.0
        ax[xi,yi].set_ylim(weatherstats[key]['yrange'])
        ax[xi,yi].set_xlim([min(time),max(time)])

        # don't subtract an arbitrary amount from the y axis before plotting
        y_formatter = matplotlib.ticker.ScalarFormatter(useOffset=False)
        ax[xi,yi].yaxis.set_major_formatter(y_formatter)

        nplots += 1

    plt.savefig(filename,dpi=72)
    #plt.show()
    return filename



def smooth(y, box_pts):
    return gaussian_filter1d(y,box_pts)
    if len(y) < box_pts:
        return np.nan
    box = np.ones(box_pts)/box_pts
    y_smooth = np.convolve(y, box, mode='same')
    return y_smooth

if __name__ == "__main__":
#    import matplotlib
#    matplotlib.use('Agg')
#    matplotlib.get_backend()

    minerva = control.control('control.ini','/home/minerva/minerva-control')
    plotweather(minerva)
    sys.exit()

    ipdb.set_trace()

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


