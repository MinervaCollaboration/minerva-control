# First, we must import all necessary libraries
from datetime import datetime, timedelta
import os, matplotlib
matplotlib.use('Agg')
import numpy as np, matplotlib.pyplot as plt

# the path which all of our text files live
path = '/home/minerva/minerva-control/minerva_library/read_temps/stability_txts/'

# extract the Year, Month, Day, hour, minute, and second form our typical date string (YYYY/MM/DD hh:mm:ss)
def get_hms(date_string):

    hour = float(date_string[11:13])
    minute = float(date_string[14:16])
    second = float(date_string[17:19])

    return hour, minute, second

# create a temperature stability dictionary to monitor sall interesting parameters
temp_data = {'date': [], 'return_T': [], 'humidity': [], 'CW_T': [] , 'discharge_T': []}

# get yesterday's date and then determine what the according file name will be
yesterday = datetime.strftime(datetime.now() - timedelta(1), '%Y-%m-%d')
yesterdays_file = yesterday[:4] + yesterday[5:7] + yesterday[-2:] + '.txt'

# grab the lines from the file
lines = open(path + yesterdays_file).readlines()

# the following loop appropriately populates our `temp_data` dictionary
for line in lines[4:]:

    data = [x.strip() for x in line.split(',')]
        
    for key in temp_data.keys():

        if key == 'date':
            
	    h, m, s = get_hms(data[(temp_data.keys()).index(key)])
            temp_data[key].append(h + m / 60. + s / 3600.)
        
        else:
            
            temp_data[key].append(float(data[(temp_data.keys()).index(key)]))

# specify some parameters and plot!
x_axis = 'date'
x_unit = 'h'

fig, axs = plt.subplots(4, 1, sharex = True)

# Remove horizontal space between axes
fig.subplots_adjust(hspace = 0.1)

y_axis = 'CW_T'
y_unit = r'$^\circ$' + 'F'
axs[0].plot(temp_data[x_axis], temp_data[y_axis], color = 'blue')
axs[0].set_ylabel('Chiller [' + y_unit + ']')

y_axis = 'humidity'
y_unit = '%'
axs[1].plot(temp_data[x_axis], temp_data[y_axis], color = 'blue')
axs[1].set_ylabel('Humid. [' + y_unit + ']')
set, error = 25, 15
axs[1].axhline(y = set, ls = '--', color = 'red')
axs[1].axhline(y = set + error, color = 'red')
axs[1].axhline(y = set - error, color = 'red')
if np.max(temp_data[y_axis]) < set + error: axs[1].set_ylim(ymax = set + error + 5)
if np.min(temp_data[y_axis]) > set - error: axs[1].set_ylim(ymin = set - error - 5)

y_axis = 'return_T'
y_unit = r'$^\circ$' + 'F'
axs[2].plot(temp_data[x_axis], temp_data[y_axis], color = 'blue')
axs[2].set_ylabel('Return [' + y_unit + ']')

y_axis = 'discharge_T'
y_unit = r'$^\circ$' + 'F'
axs[3].plot(temp_data[x_axis], temp_data[y_axis], color = 'blue')
axs[3].set_ylabel('Supply [' + y_unit + ']')
set, error = 70, 2
axs[3].axhline(y = set, ls = '--', color = 'red')
axs[3].axhline(y = set + error, color = 'red')
axs[3].axhline(y = set - error, color = 'red')
if np.max(temp_data[y_axis]) < set + error: axs[3].set_ylim(ymax = set + error + 1)
if np.min(temp_data[y_axis]) > set - error: axs[3].set_ylim(ymin = set - error - 1)

plt.xlabel('local time' + ' [' + x_unit + ']')
plt.xlim(0, 24)
plt.suptitle('Stability Measurements for MINERVA Spectrograph Room [' + yesterday + ']')
today = datetime.strftime(datetime.now(), '%Y%m%d')
file_path = '/home/minerva/minerva-control/log/n' + today
if not os.path.isdir(file_path): os.mkdir(file_path)
plt.savefig(file_path + '/n' + today + '.hvac.png', dpi = 500)
plt.clf()
