import win32api

class worker:
    def __init__(self):
        print 'Set worker close'
        win32api.SetConsoleCtrlHandler(self.closetest2,True)
    
    def closetest2(self,sig):
        print 'second, but entered first!'
        f = open('C:/minerva-control/minerva_library/sam_testing/closetest2.txt','a')
        f.write('Closed'+str(time.time())+'\n')
        f.close()
