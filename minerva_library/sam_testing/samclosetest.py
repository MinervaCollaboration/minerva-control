import signal
import time
import worker
import win32api

class tester:
    def __init__(self):
        self.worker = worker.worker()
    def closetest(self):
        f = open('C:/minerva-control/minerva_library/sam_testing/closetest.txt','a')
        f.write('Closed'+str(time.time())+'\n')
        f.close()


    def handler(self,sig):
        print 'Closing...'
        print 'Writing...'
        self.closetest()
        print 'new waiting!'
        time.sleep(2)
        pass

##print 'samclosetest.py'
##
##time.sleep(2)
##signal.signal( signal.SIGINT, handler )

testit = tester()

                     
print 'set tester cloose'

win32api.SetConsoleCtrlHandler(testit.handler,True)

time.sleep(10)
