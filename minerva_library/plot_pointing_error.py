import numpy as np
import matplotlib.pyplot as plt 
from datetime import datetime, date, time
import socket 
import sys

'''
this function gets the line beginning night acquisition with it coresponding target is at
and returns the x,y of the star that has acquired and also gives you the time 
'''    

def bfa(telnum,conten):
    # function to get fine aquisition lines for a specific telescope
    xy=[]
    Times=[]
    for i, line in enumerate(conten): 
        if "%s: beginning fine acquisition"%(telnum) in line:
        #print i
            for g, goodline in enumerate(conten[i:]):
                if "%s: Target is at"%(telnum) in goodline:
                    xy.append(conten[i:][g][82:103].split(','))
                #print g
                #print conten[i:][g][82:103]
                    if "%s: Target is at"%(telnum) in goodline:
                        dt = datetime.strptime(goodline.split(' ')[0], '%Y-%m-%dT%H:%M:%S.%f')   
                    Times.append(dt)
                    break
        #good_Lines.append(line)
#print xy
#print(len(xy))
    return xy, Times


def distance(x,y):
    # Pythagorean distance
        a = np.sqrt((x)**2 + (y)**2)*0.334
        return a

def do_it_all(x,y,telnum):
# bundle into a single function
    xcenter,ycenter=get_telescope_pointing_distance(x,y,telnum) #f(x,y) is defined later for each telescope (unique offsets)
    return distance(xcenter,ycenter)



#Telescope = ['T1','T2','T3',"T4"]

#print new_Tbfa
#print Times
#for i in range(len(Times)):
    #print new_Tbfa[i],Times[i]
#   for h1 in new_Tbfa: 
#       print h1
#       print Times
'''
########## START DOING CALCULATIONS FOR THE TELESCOPES
'''
'''
Calculate x and y offset from optical axis
'''
def get_telescope_pointing_distance(x,y,telnum):
    if telnum == 'T1':   #gives me the distance from the optical
        xcenter = 278.5
        ycenter = 217.5
    elif telnum == 'T2':
        xcenter = 173
        ycenter = 118
    elif telnum == 'T3':
        xcenter = 313
        ycenter = 235
    elif telnum == 'T4':
        xcenter = 282
        ycenter = 353
    return x-xcenter, y-ycenter

#xd, yd = f(361.268489,159.531618)
#xd, yd = f(580.250596,101.609465) 
#xd, yd = f(300.757794,69.599520) 
#xd, yd = f(363.390037,342.520933) 


def get_date_range(start_date,end_date,reduced_telescope_logs,tel_number_string):
    times,distances = reduced_telescope_logs[tel_number_string]
    after_start = [start_date <= t for t in times]
    before_end = [end_date >= t for t in times]
    good_distances, good_times = [],[]
    for i in xrange(len(distances)):
        if after_start[i] and before_end[i]:
            good_distances.append(distances[i])
            good_times.append(times[i])
    return good_times, good_distances


#start_time = datetime.strptime('2016-04-15T04:00:00.0', '%Y-%m-%dT%H:%M:%S.%f')
#end_time = datetime.strptime('2016-04-15T09:00:00.0', '%Y-%m-%dT%H:%M:%S.%f')

#Times1, T1DR = get_date_range(start_time,end_time,telescope_data,'T1')
#Times2, T2DR = get_date_range(start_time,end_time,telescope_data,'T2')
#Times3, T3DR = get_date_range(start_time,end_time,telescope_data,'T3')
#Times4, T4DR = get_date_range(start_time,end_time,telescope_data,'T4')
################# END DOING CALCULATIONS  --- NOW PLOTTING 


def plot_pointing_error(night = 'n20160614'): 
    if socket.gethostname() == 'Kevins-MacBook.local': 
        Log = '/Users/Kevin/Documents/control.log'
    else: 
        Log = '/home/minerva/minerva-control/log/'+night+'/control.log'
    with open(Log) as f:
        content = f.readlines()
    
    
    #xy,times = bfa(telnum,conten)
    #a = distance(x,y)
    #distance = do_it_all(x,y)
    #x,y = get_telescope_pointing_distance(x,y,Telescope)
    ########## START DOING CALCULATIONS FOR THE TELESCOPES
    # Get all offsets for T1
    for T in ['T1']:
        T1bfa, Times1 = bfa(T,content)    
    x1_pos = [np.float(T1bfa[i][0]) for i in range(len(T1bfa))]
    y1_pos = [np.float(T1bfa[i][1]) for i in range(len(T1bfa))]
    T1DR = [do_it_all(x1_pos[i],y1_pos[i],T) for i in range(len(x1_pos))]
    # Get all offsets for T2

    for T in ['T2']:
        T2bfa, Times2 = bfa(T,content)
    x2_pos = [np.float(T2bfa[i][0]) for i in range(len(T2bfa))]
    y2_pos = [np.float(T2bfa[i][1]) for i in range(len(T2bfa))]
    T2DR = [do_it_all(x2_pos[i],y2_pos[i],T) for i in range(len(x2_pos))]
    # Get all offsets for T3
    for T in ['T3']:
        T3bfa, Times3 = bfa(T,content)
    x3_pos = [np.float(T3bfa[i][0].replace(')','')) for i in range(len(T3bfa))]
    y3_pos = [np.float(T3bfa[i][1].replace(')','')) for i in range(len(T3bfa))]
    T3DR = [do_it_all(x3_pos[i],y3_pos[i],T) for i in range(len(x3_pos))]
    # Get all offsets for T4
    for T in ['T4']:
        T4bfa, Times4 = bfa(T,content)
    x4_pos = [np.float(T4bfa[i][0]) for i in range(len(T4bfa))]
    y4_pos = [np.float(T4bfa[i][1]) for i in range(len(T4bfa))]
    T4DR = [do_it_all(x4_pos[i],y4_pos[i],T) for i in range(len(x4_pos))]
    #makes a dictionary
    telescope_data = {'T1':(Times1,T1DR), 'T2':(Times2,T2DR), 'T3':(Times3,T3DR), 'T4':(Times4,T4DR)}
    #good_times,good_distances = get_date_range()
    ################# END DOING CALCULATIONS  --- NOW PLOTTING 
    plt.plot(Times1, T1DR, 'r', label='T1')
    plt.plot(Times2, T2DR, 'b', label='T2')
    plt.plot(Times3, T3DR,'g', label='T3')
    plt.plot(Times4, T4DR, 'y', label='T4')
    plt.plot(Times1, T1DR, 'rs')
    plt.plot(Times2, T2DR, 'bs')
    plt.plot(Times3, T3DR,'gs')
    plt.plot(Times4, T4DR, 'ys')
    ax = plt.subplot(111)

    file_Plot_name='Pointing_error_%s.png'%night
    plt.xlabel('Hours since UT'+night)
    plt.ylabel('Error(arcseconds)')
    plt.title('Pointing Error of T1,T2,T3,T4')
    # plt.axis([Times1, Times4, error1, error4])
    plt.xticks(rotation=75)
    plt.grid(True)
    plt.legend()
    ax.legend(loc='upper right') #bbox_to_anchor=(1, 0.5))
    plt.tight_layout()
    plt.savefig('Pointing_error_%s.png'%night, dpi = 300)
    plt.close()
    #plt.show()
    print 'Done'
    return file_Plot_name

if __name__== '__main__':
    ax = plot_pointing_error()
    
    



    
    







