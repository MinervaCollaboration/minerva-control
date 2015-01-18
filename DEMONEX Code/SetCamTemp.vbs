Sub SetCamTemp

CamCooling = 58
GuiderCooling = 30
MaxDifference = 0.5

'0 F = -17.9 C, unhandled error in GetWeather?
start = now
Do
  Call GetWeather(strWindSpeed,strWindDir,strHumidity,strRain,strPressure,strTemp)
  If (now - start)*86400 > 10 then
    Timeout = True
  End If
  WScript.Sleep 1000
Loop Until strTemp  <> "-17.7777777777778" or Timeout

If strTemp = "??" or strTemp = "-17.7777777777778" Then
  objEngFile.WriteLine("SetCamTemp (" & FormatDateTime(Now,3) & "): No temperature found, using 0 F")
  strTemp = "-17.7777777777778"
End If

'Round to the nearest degree, 7 degrees below threshhold
CamSetPoint = round(strTemp - CamCooling) + 7
GuiderSetPoint = round(strTemp - GuiderCooling) + 7

If UseGuider Then
  objCam.Autoguider = 1
  objCam.TemperatureSetPoint = GuiderSetPoint
  objCam.RegulateTemperature = 1
End If

objCam.Autoguider = 0
objCam.TemperatureSetPoint = CamSetPoint
objCam.RegulateTemperature = 1

TStart = Now
Do While abs(CamSetPoint - objCam.Temperature) > MaxDifference
  If (Now - Tstart)*1440 > 10 Then
    objEngFile.WriteLine("SetCamTemp (" & FormatDateTime(Now,3) & "): Setting camera temp took too long, lowering set point to 7 degrees above current; T_Cam = " &_
      objCam.Temperature & ", T_SetOld = " & CamSetPoint & ", T_outside = " & strTemp & ", T_SetNew = " & Round(objCam.Temperature) + 7)
    CamSetPoint = Round(objCam.Temperature) + 7
    objCam.TemperatureSetPoint = CamSetPoint
    objCam.RegulateTemperature = 1
    TStart = Now

    'outside temp probably wrong; reset guider temp too
    If UseGuider Then
      GuiderSetPoint = round(objCam.TemperatureSetPoint) + (CamCooling - GuiderCooling) + 7
      objCam.Autoguider = 1
      objCam.TemperatureSetPoint = GuiderSetPoint
      objCam.RegulateTemperature = 1
      objCam.Autoguider = 0
    End If

  Else 
    objEngFile.WriteLine("SetCamTemp (" & FormatDateTime(Now,3) & "): Waiting for Camera to reach set point; T_Cam = " &_
      objCam.Temperature & ", T_Set = " & CamSetPoint & ", T_outside = " & strTemp)
    WScript.Sleep 30000
  End If
Loop
objEngFile.WriteLine("SetCamTemp (" & FormatDateTime(Now,3) & "): Camera at set point; T_Cam = " &_
      objCam.Temperature & ", T_Set = " & CamSetPoint & ", T_outside = " & strTemp)

If UseGuider Then
  objCam.AutoGuider = 1
  Do While abs(GuiderSetPoint - objCam.Temperature) > MaxDifference
    If (Now - Tstart)*1440 > 15 Then
      objEngFile.WriteLine("SetCamTemp (" & FormatDateTime(Now,3) & "): Setting guider temp took too long, lowering set point; T_Cam = " &_
        objCam.Temperature & ", T_SetOld = " & GuiderSetPoint & ", T_outside = " & strTemp & ", T_SetNew = " & GuiderSetPoint + 5)
      GuiderSetPoint = GuiderSetPoint + 5
      objCam.TemperatureSetPoint = GuiderSetPoint
      objCam.RegulateTemperature = 1
      TStart = Now       
    Else 
      objEngFile.WriteLine("SetCamTemp (" & FormatDateTime(Now,3) & "): Waiting for Guider to reach set point; T_Cam = " &_
        objCam.Temperature & ", T_Set = " & GuiderSetPoint & ", T_outside = " & strTemp)
      WScript.Sleep 30000
    End If
  Loop
  objEngFile.WriteLine("SetCamTemp (" & FormatDateTime(Now,3) & "): Guider at set point; T_Cam = " &_
      objCam.Temperature & ", T_Set = " & GuiderSetPoint & ", T_outside = " & strTemp)
  objCam.AutoGuider = 0
End If

'Write the camera tempertures to a file for recovery
objEngFile.WriteLine("SetCamTemp (" & FormatDateTime(Now,3) & "): writing camtemp.txt file")
set CamTempFile = objFSO.OpenTextFile("camtemp.txt", ForWriting)
CamTempFile.WriteLine(CamSetPoint)
CamTempFile.WriteLine(GuiderSetPoint)
CamTempFile.Close

End Sub