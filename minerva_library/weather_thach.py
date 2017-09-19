import numpy as np
import pandas as pd
import datetime

def get_current_weather(path="/Users/Julien/Downloads/onelinefile"):
    file = np.loadtxt(path, dtype=str)

    weather = {}

    if int(file[17]) > 1:
        weather['totalRain'] = 45.0
        weather['wxt510Rain'] = 45.0
    else:
        weather['totalRain'] = 0.0
        weather['wxt510Rain'] = 0.0

    weather['windGustSpeed'] = file[7]
    weather['outsideHumidity'] = file[8]
    weather['outsideDewPt'] = file[9]
    weather['outsideTemp'] = file[6]
    weather['windSpeed'] = file[7]
    weather['date'] = datetime.datetime.utcnow()
    weather['cloudDate'] = datetime.datetime.utcnow()
    weather['MearthCloud'] = file[4]
    weather['HATCloud'] = file[4]
    weather['AuroraCloud'] = file[4]
    weather['MINERVACloud'] = file[4]

    return weather
