"""
This program will create an array of all the stability measurements for
general use. It will be used by plotting scripts, and potentially data
analysis pipelines, etc. I think it will be best to output to a csv or 
something right now. Look into save files for python again.
"""

import numpy as np
import datetime
import glob
import ipdb


def gen_times(start_time, stop_time):
    """
    Takes two datetime objects or stings that it will convert to datetime 
    objects, then figure the number of minutes (the total points we will find).
    
    This has the potential to be very big. I'm still deciding how to go about
    it. The intended use of this function will be to set what points to 
    dredge for in the temperature/pressure logs. 
    """

    dtdtfmt = '%Y-%m-%d %H:%M:%S'

    if type(start_time) == datetime.datetime:
        pass
    if type(start_time) == str:
        try:
            start_time = datetime.datetime.strptime(start_time,dtdtfmt)
        except:
            print(start_time+' not in format '+dtdtfmt)
    else:
        print("'"+start_time+"' is not a compatible type")
        return False

    if type(stop_time) == datetime.datetime:
        pass
    if type(stop_time) == str:
        try:
            stop_time = datetime.datetime.strptime(stop_time,dtdtfmt)
        except:
            print(stop_time+' not in format '+dtdtfmt)
    else:
        print("'"+stop_time+"' is not a compatible type")
        return False
    
    num_minutes = int((stop_time - start_time).total_seconds()/60)

    return start_time, stop_time, num_minutes

#    moving_end = stop_time
#    dt_list = []
#    while start_time != moving_end:
#        dt_list.append(moving_end)
#        moving_end -= datetime.timedelta(minutes=1)
#
#    dt_list.append(start_time)
#        
#    return dt_list


def get_main_temps(start_time,stop_time):
    """
    Dredge all logs that are in the range of the specified times. Take the
    average of all temperatures in the minutes specified, and return an array
    of those. 

    Filters for those that are nan/unreadable. Need a clean way of tracking 
    labels.

    This is only for temperature logs that are recorded by the PT100s on MAIN.
    """
    logpath = '/home/minerva/minerva-control/log/'
    pathfmt = 'n%Y%m%d'
    minutefmt = '%Y-%m-%d %H:%M'
    start_time,stop_time,num_mintes = gen_times(start_time,stop_time)
    log_days = [start_time + datetime.timedelta(days=x) for x in range(\
            (stop_time - start_time).days+1)]
    print log_days
    temperature_dict = {}
    for lttr in ['A','B','C','D']:
        for ind in ['1','2','3','4']:
            #make a dictionary entry for the list that will contain all the 
            #temperatures from that pt100
            temperature_dict[lttr+ind] = []
            temperature_dict[lttr+ind+'_label'] = 'none'
            for day in log_days:
                curr_time = day
                daypath = day.strftime(pathfmt)
                with open(logpath+daypath+'/temp.'+lttr+'.'+ind+'.log') as fh:
                    lines = fh.readlines()
                    temperature_dict[lttr+ind+'_label'] = \
                        lines[0].split(',')[2].rstrip()
                    n = 0
                    total = 0
                    ipdb.set_trace()
                    for line in lines:
                        entries = line.split(',')
                        curr_timestr = curr_time.strftime(minutefmt)
                        if curr_timestr == entries[0][:16]:
                            print 'got it'
                            n+=1
                            total+=float(entries[1])
                        else:
                            temperature_dict[lttr+ind].append(total/n)
                            #if the times differ, we update to the time in the 
                            #line rather than an increment incase there were no
                            # temps recorded in that minute
                            curr_time=datetime.strptime(entries[0][:16]\
                                                            ,minutefmt)
                            n = 1
                            total = float(entries[1])

                
    

if __name__ == '__main__':
    ipdb.set_trace()
    start = '2015-12-25 00:00:00'
    end = '2015-12-31 00:05:00'
    get_main_temps(start,end)
    dt_list = gen_times(start,end)
    dt_list = np.array(dt_list)
    
