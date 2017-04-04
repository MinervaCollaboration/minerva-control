def should_be_open():
    
        import get_mountain_weather
        import get_dome_temp_rh
        import numpy as np
        
        
        linmax_weather = get_mountain_weather.get_mountain_weather()
        
        if linmax_weather==-1.:
            return False
        
        dome_weather = get_dome_temp_rh.get_dome_temp_rh()
        
        conditions = np.zeros(8)
        badness=''
        
        if (linmax_weather['windspeed'] < 30):
                conditions[0]=1.
                
        
        if (linmax_weather['gust'] < 40):
                conditions[1]=1.
               

        if (linmax_weather['humidity'] < 80):
                conditions[2]=1.
                
                
        if (linmax_weather['dpd'] > 5. ):
                conditions[3]=1.
                
                
        if (linmax_weather['wxtrain'] == 0.):
                conditions[4]=1.
                
        if (dome_weather['rh'] < 80.):
                conditions[5]=1.
                
        if (dome_weather['temp']-dome_weather['dewp'] > 5.):
                conditions[6]=1.
        
        if (linmax_weather['skytemp'] < -30.):
                conditions[7]=1.
        print linmax_weather
        print np.sum(conditions)
        
        
        if np.sum(conditions) == 8:
                return True
                
        if np.sum(conditions) != 8:
                return False