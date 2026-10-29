import numpy as np
import matplotlib.pyplot as plt
import datetime
import glob
import os
import ipdb

def smooth(y, box_pts):
    return gaussian_filter1d(y,box_pts)
    if len(y) < box_pts:
        return np.nan
    box = np.ones(box_pts)/box_pts
    y_smooth = np.convolve(y, box, mode='same')
    return y_smooth
log_path = '/home/minerva/minerva-control/log/'
therm_enc_path = '/Data/thermallog/'
dtfmt = '%Y-%m-%d'
pathfmt = 'n%Y%m%d'
startdate_str = '2015-12-30'
num_days = 3
startdate = datetime.datetime.strptime(startdate_str,dtfmt)
date_list = [startdate + datetime.timedelta(days = x) for x in range(num_days)]
ipdb.set_trace()
time_ave_list = []
ave_list = []
std_list = []

for date in date_list:
    pt100logs = glob.glob(log_path+date.strftime(pathfmt)+'/temp.?.?.log')
    for log in pt100logs:
        with open(log) as fh:
            lines = fh.readlines()
            lasthour = int(lines[0].split(',')[0][11:12])
            for line in lines:
                entries = line.split(',')

                if int(entries[0][11:12]) != lasthour:
                    time_of_ave = date+datetime.timedelta(hours=lasthour)
                    time_ave_list.append(time_of_ave)
                    ave_list.append(total/n)
                    if n>1:
                        std_list.append(np.sqrt((squared_total-total**2/n)\
                                                    /(n-1)))
                    else:
                        std_list.append(0)

                    lasthour  = int(entries[0][11:12]) 
                    n = 1 
                    total = float(entries[1])
                    squared_total = float(entries[1])**2
                else:
                    n += 1
                    total += float(entries[1])
                    squared_total += float(entries[1])**2
    

