Sub WriteLog

  Const Light = 1
  Const Bias = 2
  Const Dark = 3
  Const Flat = 4

  objEngFile.WriteLine("WriteLog (" & FormatDateTime(Now,3) & "): Getting weather info")
  'Gets weather info from http://www.winer.org/metricWeather.html
  Call GetWeather(strWindSpeed,strWindDir,strHumidity,strRain,strPressure,strTemp)

  strFilter = objCam.szFilterName(objCam.FilterIndexZeroBased)

  strTCam = objCam.Temperature
  strTFocus = "??" 'objCam.focTemperature '??
  strTTel = "??" 'not currently supported, but soon?

  strExpTime = objCam.ExposureTime
  strMerFlip = MeridianFlip
  
  If objCam.Frame = Light Then
    objEngFile.WriteLine("WriteLog (" & FormatDateTime(Now,3) & "): Light Frame")
    'Calculate the Airmass from the telescope's altitude
    AzAlt = Utils.ConvertRADecToAzAlt(adnow(0),adnow(1))
    strAirmass = Utils.ComputeAirMass(AzAlt(1))   
  ElseIf objCam.Frame = Bias Then
    objEngFile.WriteLine("WriteLog (" & FormatDateTime(Now,3) & "): Bias Frame")
    strExptime = "0"
    strAirmass = "--"
    strFilter = "--"
    strMerFlip = "--"
  ElseIf objCam.Frame = Dark Then
    objEngFile.WriteLine("WriteLog (" & FormatDateTime(Now,3) & "): Dark Frame")
    strAirmass = "--"
    strFilter = "--"
    strMerFlip = "--"
  ElseIf objCam.Frame = Flat Then
    objEngFile.WriteLine("WriteLog (" & FormatDateTime(Now,3) & "): Flat Field")
    strMerFlip = "--"
    strAirmass = "--"
  End If

  'Write to the log file
  objLogFile.WriteLine(strFilename & VBTab & objName & VBTab & FormatDateTime(Now,3) & VBTab &_
	strExpTime & VBTab & strAirmass & VBTab & strFilter & VBTab &_
        strMerFlip & VBTab & strTemp & VBTab &_
	strTCam & VBTab & strTFocus & VBTab & strTTel & VBTab &_
	strWindSpeed & VBTab & strWindDir & VBTab &_
	strHumidity & VBTab & strRain & VBTab & strPressure)

End Sub