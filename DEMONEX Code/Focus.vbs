'Auto Focuses the telescope based on pre-defined temperature settings.

Function Focus

  Exit Function

  'Crashes if two focus commands issued at the same time, wait 5 minutes between commands
  If (Now - TLastFocus) < 0.003472222 Then
    objEngFile.WriteLine("Focus (" & FormatDateTime(Now,3) & "): Time since last focus command too short, not changing focus")
    Exit Function
  End If

  'If the focuser not connected, don't do anything
  If (objCam.focIsConnected=0) Then 
    Exit Function
  End If

   'Get the temperature from the Winer site
  Set objFile = objFSO.OpenTextFile("GetWeather.vbs", ForReading)
  Execute objFile.ReadAll()
  Call GetWeather(strWindSpeed,strWindDir,strHumidity,strRain,strPressure,strTemp) 
  If strTemp = "??" Then
    objEngFile.WriteLine("Focus (" & FormatDateTime(Now,3) & "): Temperature unknown, not changing focus")
    Exit Function
  End If

  Temp = Cdbl(strTemp)

  'Device Specific Parameters
  stepsPerDegreeC = 10
  MaxFocus = 7000
  MinFocus = 0
  MidTemp = 15
  PosAtMidTemp = (MaxFocus + MinFocus)/2 

  currPos = objCam.focPosition

  'Calculate the focus offset
  focusOffset = (Temp - MidTemp)*stepsPerDegreeC + PosAtMidTemp - CurrPos

  'Move to the desired Focus Position. 
  'If it's out of bounds, move to the limit
  If FocusOffset < 0 Then
    If (FocusOffset + CurrPos) > 0 Then
      objEngFile.WriteLine("Focus (" & FormatDateTime(Now,3) & "): Moving from " & CurrPos & " to " & Currpos + focusOffset)
      objCam.focMoveIn(-focusOffset)
    Else 
      objEngFile.WriteLine("Focus (" & FormatDateTime(Now,3) & "): Focus move exceeds limit, moving focus to " & MinFocus)
      objCam.focMoveIn(currPos)
    End If
  ElseIf FocusOffset > 0 Then
    If (FocusOffset + CurrPos) < MaxFocus Then 
      objEngFile.WriteLine("Focus (" & FormatDateTime(Now,3) & "): Moving from " & CurrPos & " to " & Currpos + focusOffset)
      objCam.focMoveOut(focusOffset)
    Else 
      objEngFile.WriteLine("Focus (" & FormatDateTime(Now,3) & "): Focus move exceeds limit, moving focus to " & MaxFocus)
      objCam.focMoveOut(MaxFocus - currPos)
    End If
  End If

  TLastFocus = Now

End Function