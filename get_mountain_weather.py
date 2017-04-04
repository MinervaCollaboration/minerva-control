def get_mountain_weather():
    import urllib2, string

    url = "http://linmax.sao.arizona.edu/weather/weather.cur_cond"
    
    try:
        response = urllib2.urlopen(url)
    except urllib2.HTTPError:
        return -1
            
    output = response.read()
    weather = string.split(output, '\n')
    #print output
    currmttime = weather[0][:4]+'-'+weather[0][6:8]+'-'+weather[0][10:12]+' '+weather[0][22:24]+':'+weather[0][18:20]+':'+weather[0][14:16]+'.'+weather[0][26:]
    mttemp = weather[1][12:]
    windspeed = weather[2][10:]
    gustspeed = weather[3][14:]
    windDir = weather[4][21:]
    barometer = weather[5][10:]
    outHum = weather[6][16:]
    wxt510Rain = weather[7][11:]
    totalRain = weather[8][10:]
    outDewPt = weather[9][13:]
    outDPD = str(float(mttemp)-float(outDewPt))
    
    url = "http://mearth.sao.arizona.edu/weather/now"
    try:
        response = urllib2.urlopen(url)
    except urllib2.HTTPError:
        return -1
           
    output = response.read()
    mearth_weather = string.split(output)
    skytemp= float(mearth_weather[13])
    
    return {'windspeed':float(windspeed), 'humidity':float(outHum), 'wxtrain':float(wxt510Rain), 'dpd':float(outDPD), 'gust':float(gustspeed), "skytemp":skytemp}