import glob
import plotlogs
import ipdb
import os

nights = glob.glob('/home/minerva/minerva-control/log/n2016????')

#ipdb.set_trace()
for night in nights: plotlogs.plotlogs(os.path.basename(night))
