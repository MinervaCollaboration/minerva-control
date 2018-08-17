import win32api
import win32con
import time
import ipdb

def safeclose():
    f=open(path+'test.txt','a')
    f.write('shit')
    f.close()
    return
    
def handler(signal):
    print 100*'were in!\n'
    time.sleep(5)
    safeclose()

ipdb.set_trace()
path = 'C:\minerva-control\minerva_library\sam_testing\\'
print 'gotit'
win32api.SetConsoleCtrlHandler(handler,True)
#z=open(path+'new.txt','w')
#z.write('shit\n')
#z.close()
#safeclose()
while True:
    pass
