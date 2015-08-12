import time
import datetime
import ipdb


class tester:
    def __init__(self,base=''):
            #ipdb.set_trace()
            self.base_directory = base
    def turnThArON(self):
            ThArfile = 'ThArLamp01.txt'
            self.timeTrackON(ThArfile)
#            self.dynapower1.on('2')
    def turnThArOFF(self):
            ThArfile = 'ThArLamp01.txt'
            self.timeTrackOFF(ThArfile)
#            self.dynapower1.off('2')



    #S Functions for tracking the time something has been on.
    #S Tested on my computer, so it should be fine. Definitely keep an eye
    #S on it though. 
    def timeTrackON(self,filename):
            #S Some extra path to put files in directory in log directory
            extra_path = ''#self.base_directory+'/log/lamps/'
            #S Format for datetime objects being used.
            fmt = '%Y-%m-%dT%H:%M:%S'
            #S Get datetime string of current time.
            now = datetime.datetime.utcnow().strftime(fmt)
            #S Open file, append the current time, and close.
            #S Note: no EOL char, as it makes f.readlines shit.
            f = open(extra_path+filename,'a')
            f.write(now)
            f.close()
            
    def timeTrackOFF(self,filename):
            #S Paath
            #ipdb.set_trace()
            extra_path = ''#self.base_directory + '/log/lamps/'
            #S Format for datetime strings 
            fmt = '%Y-%m-%dT%H:%M:%S'
            #S Current time, datetime obj and string
            now = datetime.datetime.utcnow()
            nowstr = now.strftime(fmt)
            #S Open and read log. For some reason can't append and
            #S read at sametime.
            #TODO Find way to read file from bottom up, only need
            #TODO last two lines.
            f = open(extra_path+filename,'r')
            lst = f.readlines()
            f.close()
            #S Check to see if there is a full line of entries, and if so,
            #S skip the saving and update. this is because if there is a full
            #S list of entries, this timeTrackOFF was envoked by the CtrlHandler.
            #S The lamp was probably off already, but just in case we tell it again.
            if len(lst[-1].split(',')) == 3:
                    return
            #S Get previous total time on. See the except for details on
            #S what should be happening. 
            try:
                    #S Get time and pull from HH:MM:SS format, convert to seconds.
                    prevtot = float(lst[-2].split(',')[-1])*3600.
                    #temptot = prevtot.split(':')
                    #totseconds = float(temptot[0])*3600. + float(temptot[1])*60. + float(temptot[2])
                    
            #S This is meant to catch the start of a new file, where
            #S there are no previoes times to add. It shouldn't catch
            #S if there are previuos times, but the end time and previous
            #S total were not recorded.
            #S I actually think it will now, as if it doesn't find a temptot,
            #S it will still throw with IndexError as it's supposed to for
            #S no prevtot instead. Do more investigating.
            except (IndexError):
                    prevtot = 0.
                    #print 'If you started a new lamp, ignore! Otherwise, something went wrong.'
            #S The last start time as datetime
            try:
                start = datetime.datetime.strptime(lst[-1],fmt)
            except:
                print 'shit!'
            #S Update total time on
            newtot_seconds = prevtot + (now-start).total_seconds()
            #S Write in HH:MM:SS format
            #totmins,totsecs = divmod(newtot , 60)
            #tothours,totmins = divmod(totmins, 60)
            totalstr = '%0.5f'%(newtot_seconds/3600.)#'%02d:%02d:%02d'%(tothours,totmins,totsecs)
            #S Actual file appending
            f = open(extra_path+filename,'a')
            f.write(','+nowstr+','+totalstr+'\n')
            f.close()

if __name__ == '__main__':
	
	base_directory = 'C:/minerva-control'
        test = tester(base_directory)
	test.turnThArON()
	time.sleep(5)
	test.turnThArOFF()
