import numpy as np
import matplotlib.pyplot as plt
import glob
import datetime
import ipdb
import utils

def get_cats(telnums,start,end):

    #S make sure we have a list of telnums
    if type(telnums) == int:
        telnums = [telnums]

    start_dt = datetime.datetime.strptime(start,'n%Y%m%d')
    end_dt = datetime.datetime.strptime(end,'n%Y%m%d')
    dates = [start_dt + datetime.timedelta(days=x) for x in range(0, (end_dt-start_dt).days+1)]
    
    for num in telnums:
        for date in dates:
            datestr = date.strftime('n%Y%m%d')
            files = glob.glob('/Data/t'+str(num)+'/'+datestr+'/*backlight*.cat')
            for cat in files:
                print cat
            

if __name__ == '__main__':
    ipdb.set_trace()
    start = 'n20160503'
    end = 'n20160504'
    get_cats(1,start,end)
