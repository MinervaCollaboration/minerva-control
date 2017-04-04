def get_dome_temp_rh():
#This code will read the temperature, RH, and dew point
#Returns dictionary with tags 'rh', 'temp', and 'dewp'
#Returns rh=-1 if communication with arduino on COM3 fails
#Takes longer than it should to return, like 5-6 seconds

        import serial
                    
        try: 
            a = serial.Serial('COM3', 9600, timeout=None)
        except:
            return {'rh':-1., 'temp':-100., 'dewp':-100.}
                   
        #It appears that this is required to get rid of the first line of output from the arduinos
        data0 = a.readline()       
        t = a.readline()

        #this is important, you have to close the serial connections                                
        a.close()   
       
        #This is set up to work with the specific output format of the arduino code RH_TEMP.sketch
        rh =  float(t[t.find('ity')+4:t.find('%\t')])
    
        tc =  float(t[t.find('ure')+4:t.find('*C')])
        dewp = float(t[t.find('oint')+5:t.find('Dew D')])
                                                                                           
        return{'rh':rh,'temp':tc, 'dewp':dewp}
    
        