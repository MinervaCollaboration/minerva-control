import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mpd
import glob
import datetime
import ipdb
import utils

def get_cats(telnums,dates):

    #S make sure we have a list of telnums
    if type(telnums) == int:
        telnums = [telnums]

    
    bl_dict = {}

    for num in telnums:
        bl_dict[str(num)]={}
        for date in dates:
            datestr = date.strftime('n%Y%m%d')
            bl_dict[str(num)][datestr] = {}
            files = glob.glob('/Data/t'+str(num)+'/'+datestr+'/*backlight*.cat')
            for cat in files:
                cata = utils.readsexcat(cat)
                
                for key in cata.keys():
                    if len(cata[key])==0:
                        continue
                    try:
                        bl_dict[str(num)][datestr][key].append(cata[key][0])
                    except:
                        bl_dict[str(num)][datestr][key]=[]
                        bl_dict[str(num)][datestr][key].append(cata[key][0])
            for key in bl_dict[str(num)][datestr].keys():
                bl_dict[str(num)][datestr][key] =  np.array(bl_dict[str(num)][datestr][key])
                
    return bl_dict



if __name__ == '__main__':
    ipdb.set_trace()
    telnums = [1,2,3,4]
    start = 'n20160223'
    end = 'n20160505'
    start_dt = datetime.datetime.strptime(start,'n%Y%m%d')
    end_dt = datetime.datetime.strptime(end,'n%Y%m%d')
    delta = datetime.timedelta(days=1)
    mpldates = mpd.drange(start_dt,end_dt+delta,delta)
    dates = [start_dt + datetime.timedelta(days=x) for x in range(0, (end_dt-start_dt).days+1)]

    bl_dict = get_cats(telnums,dates)
    
#    fig = plt.figure()
    fig,ax = plt.subplots()
    for num in telnums:
#        ax=fig.add_subplot(4,1,num)
        hfrmeans = []
        for date in dates:
            datestr = date.strftime('n%Y%m%d')
            try:
                hfrmeans.append(bl_dict[str(num)][datestr]['FLUX_RADIUS'].mean())
            except:
                hfrmeans.append(0)
        hfrmeans = np.array(hfrmeans)
        dind = 0
#        for date in bl_dict[str(num)].keys():
#            try:
#                plt.plot(mpldates[dind],bl_dict[str(num)][date]['FLUX_RADIUS'],'o')
#            except:
#                plt.plot(mpldates[dind],0,'o')            
#            dind+=1
        ax.plot(mpldates,hfrmeans,'o-',label='T'+str(num))
        ax.xaxis.set_major_locator(mpd.DayLocator())
        ax.xaxis.set_major_formatter(mpd.DateFormatter('n%Y%m%d'))
        ax.set_ylabel('HFR [pixels]')
        ax.set_xlabel('Date')
        
        ax.fmt_xdata = mpd.DateFormatter('n%Y%m%d')
        fig.autofmt_xdate()
        plt.legend()
    plt.show()
    ipdb.set_trace()
