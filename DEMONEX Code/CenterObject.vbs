Function CenterObject(adNow)

  MaxSunAlt = -6
  Nattempts = 0
  Unsolved = 0
  CenterStart = Now

  On Error Resume Next
  objTel.Connect

  RAOffset = 648000
  DecOffset = 648000
  Offset = sqr(raoffset^2 + decoffset^2)
'  MaxErr = 7 'in arcsec
MaxErr = 60 'in arcsec

  jdNow = jd(Year(Now),Month(Now),Day(Now),Hour(Now),Minute(Now),Second(Now))

  Do While offset > maxerr and SunAlt < MaxSunAlt and jdNow < jdEnd
    If RoofOpen Then

      If RAOffset = 648000 Then
        objEngFile.WriteLine("CenterObject (" & FormatDateTime(Now,3) & "): There have been " & unsolved & " successive unsolved images")
        Unsolved = unsolved + 1
        CheckTel
        Call SlewScope(adNow(0),adNow(1),objName)
      Else
        Unsolved = 0
        objEngFile.WriteLine("CenterObject (" & FormatDateTime(Now,3) & "): RAOffset=" & RAOffset & " DecOffset=" & DecOffset )
        objEngFile.WriteLine("CenterObject (" & FormatDateTime(Now,3) & "): Centering " & objName & " " & ra & " " & dec )
        CheckTel

        'small offset, use guider to correct
        If Offset < 300 Then
          objEngFile.WriteLine("CenterObject (" & FormatDateTime(Now,3) & "): Centering with guider")

          'Disconnect the telescope so TheSky6 doesn't fight with the guider
          objTel.Disconnect() 
          objTheSky.DisconnectTelescope()
       
          objCam.Autoguider = 1
          objCam.EnabledXAxis = True
          objCam.EnabledYAxis = True
          GuiderScaleArcsecPerPixel = 3.09
          Aggressiveness = 0.75
          FromX = 0
          FromY = 0
          ToX = RAOffset/GuiderScaleArcsecPerPixel*Aggressiveness
          ToY = DecOffset/GuiderScaleArcsecPerPixel*Aggressiveness

          'Reverse x correction if West of Meridian
          If MeridianFlip Then ToX = -ToX

          objEngFile.WriteLine("CenterObject (" & FormatDateTime(Now,3) & "): Moving from " & fromX & "," & fromY & " to " & toX & "," & toY)        

          Call objCam.Move(FromX, FromY, ToX, ToY)

          WScript.Sleep 10000 'wait to settle
          objCam.EnabledXAxis = False
          objCam.EnabledYAxis = False 
          objCam.Autoguider = 0
          
          objTel.Connect

        Else
          'big offset, use slew to correct
          objEngFile.WriteLine("CenterObject (" & FormatDateTime(Now,3) & "): Centering with slew")
          Call SlewScope(adNow(0),adNow(1),objName)
        End If
        Nattempts = Nattempts + 1
      End If
      
      OffsetPrev = offset
     
      'Confirm Pointing
      CheckTel
      SyncScope

      'RAOffset and DecOffset were changed by SyncScope
      Offset = sqr(raoffset^2 + decoffset^2)

      'Pointing degraded from last iteration; reboot telescope (guider dead?)
'      If Offset > OffsetPrev and Offset > 100 And RAOffset <> 648000 Then
      If Offset > OffsetPrev And RAOffset <> 648000 Then
        objEngFile.WriteLine("CenterObject (" & FormatDateTime(Now,3) & "): Offset=" & Offset & " Offsetprev=" & Offsetprev & " RAoffset=" & RAOffset)
        objEngFile.WriteLine("CenterObject (" & FormatDateTime(Now,3) & "): Error Centering the object; homing, powercycling, and retrying")
        HomeScope
        DisconnectAll
        ScopeOff
        WScript.Sleep 30000
        ScopeOn        
        ConnectAll

        'Re-point
        CheckTel
        Call SlewScope(adNow(0),adNow(1),objName)
        SyncScope
      End If

    Else
      objEngFile.WriteLine("CenterObject (" & FormatDateTime(Now,3) & "): Roof Closed; retry in 5 minutes")
      'Turn Tracking off (just in case)
      objEngFile.WriteLine("CenterObject (" & FormatDateTime(Now,3) & "): Making sure tracking is off")
      CheckTel
      Call objTel.SetTracking(0, 0, 0, 0)
      WScript.Sleep 300000  
    End If

    'calculate the current JD
    jdNow = jd(Year(Now),Month(Now),Day(Now),Hour(Now),Minute(Now),Second(Now))

  Loop

  If offset <= maxerr Then
    Centered = True
    strBody = strBody & "Pointing off by " & Round(RAOffset,2) & """ in RA and " & Round(DecOffset,2) & """ in Dec in " & nattempts & " iterations" & vbCrLf
    objEngFile.WriteLine("CenterObject (" & FormatDateTime(Now,3) & "): Centering Completed in " & Round((Now - CenterStart)*86400) & " seconds")
  Else
    Centered = False
    objEngFile.WriteLine("CenterObject (" & FormatDateTime(Now,3) & "): Centering failed in " & Round((Now - CenterStart)*86400) & " seconds")
    strBody = strBody & "ERROR: Pointing off by " & Round(RAOffset,2) & """ in RA and " & Round(DecOffset,2) & """ in Dec in " & nattempts & " iterations" & vbCrLf
  End If
 

  'Disconnect the telescope so TheSky6 doesn't fight with the guider
  objTel.Disconnect() 
  objTheSky.DisconnectTelescope()

  AcquireObject = False
  MovePending = 0

  CheckCam
  objCam.ExposureTime = ExpTime

End Function