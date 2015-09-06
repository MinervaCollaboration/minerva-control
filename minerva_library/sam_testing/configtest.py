from configobj import ConfigObj
#f = open('C:/minerva-control/minerva_library/sam_testing/congiftest.ini','r')
#f.readlines()
#f.close()
         
try:
    calib_dict = ConfigObj('./configtest.ini')['TEST']
except:
    print 'damn!'
    

print type(calib_dict['dark_nums'])
