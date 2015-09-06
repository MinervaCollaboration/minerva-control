import atexit
import time
import os

def closetest():
    f = open('closetest.txt','a')
    f.write('Closed'+str(time.time())+'\n')
    f.close()


time.sleep(10)
atexit.register(closetest)#lambda: os.system("pause"))
