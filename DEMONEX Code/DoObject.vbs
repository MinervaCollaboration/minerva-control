Sub DoObject(objName,ra,dec,jdstart,jdend,night,arrFilters,ExpTime,NImages)

  StopGuiding = False
  RestartGuider = False
  AcquireGuideStar = True

  Const Light = 1
  Const cdStateIdle = 0

  Set objImage = WScript.CreateObject("CCDSoft.Image")

  'For auto-adjusting the exposure time
  biasLevel = 2367
  targetCounts = 40000 'includes bias level
  maxExpTime = 1
  boxHalfSize = 25
  MaxSunAlt = -6

  NLoops = 0

  'calculate the current JD
  jdNow = jd(Year(Now),Month(Now),Day(Now),Hour(Now),Minute(Now),Second(Now))

  'calculate when the object will cross the meridian
  result = Utils.ComputeRiseTransitSetTimes(ra,dec)
  TransitTime = jd(Year(Now),Month(Now),Day(Now),0,0,0) + result(1)/24
  If TransitTime - jdNow < -0.5 Then 
    TransitTime = TransitTime + 1
  ElseIf TransitTime - jdNow > 0.5 Then
    TransitTime = TransitTime - 1
  End If

  objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Object transits at " & TransitTime & "; current time is " & JDNow)
  
  MeridianFlip = CBool(False)

  'Wait until start time
  if jdNow < jdStart then
    sleepTime = (jdStart - jdNow)*86400000
    objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Script Started before jdStart; Turning tracking off and waiting for " &_
      sleeptime/1000 & " seconds. Sun altitude = " & SunAlt)
    CheckTel
    Call objTel.SetTracking(0, 0, 0, 0)
    WScript.Sleep sleepTime
  End If

  objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Begin tracking")
  CheckTel
  Call objTel.SetTracking(1, 1, 1, 1)  

  'If the exposure time is less than 0, calculate it based on the previous image, start with 10 seconds
  objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Setting exposure time")
  If Exptime <= 0 Then 
    CalcExpTime = True
    ExpTime = 10 'Initial guess
  Else 
    CalcExpTime = False
  End If

  CheckCam
  objCam.ExposureTime = ExpTime

  objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Setting Filename")
  CheckCam
  objCam.AutoSavePrefix = "TmpPrefix"

  'Run other commands while exposing and slewing
  objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Doing Commands Serially")
  CheckCam
  objCam.Asynchronous = 0
  CheckTel
  objTel.Asynchronous = 0

  'Initial Focus based on temperature
  Focus

  'Set IMGTYPE = Light
  CheckCam
  objCam.Frame = Light

  NTaken = 0
  AcquireObject = True

  'Wait for Sun to set
  Do While SunAlt > MaxSunAlt and Hour(Now) > 12
    objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Sun too high to begin observations: " & SunAlt )
    WScript.Sleep 60000
  Loop

  'Set up the initial exposure time, pointing
  adNow = Utils.Precess2000ToNow(ra,dec)

  'Number of times the center has been too far to move
  BadCenter = 0

  Do While (jdNow < jdEnd and NTaken < NImages and SunAlt < MaxSunAlt)

    objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Entering Loop; JDNow=" & jdNow & " JDEnd=" & jdEnd )

    For Each objFilter in arrFilters
      If RoofOpen Then

        'Focus the Telescope
        Focus

        objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Roof Open; beginning image " &_
          Ntaken + 1 & " of " & NImages)

        If AcquireObject Then
          If JDNow > TransitTime Then
            MeridianFlip = CBool(True)
          End If

          AcquireGuideStar = True
          Call CenterObject(adnow)
          If Not Centered Then
            Exit Sub
          End If
        End If
   
        'Deal with Meridian Flip (Force no meridian flip when close??)
        If JDNow > TransitTime and Not MeridianFlip Then
          MeridianFlip = True

          If UseGuider Then
            objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Object about to transit; aborting guider and flipping meridian")
            objCam.Autoguider = 1
            objCam.Asynchronous = 0
            objCam.Abort
            AcquireGuideStar = True
          Else 
            objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Object about to transit; flipping meridian")
          End If       

          Call CenterObject(adnow)
          If Not Centered Then
            Exit Sub
          End If
        End If

        If UseGuider Then
          If AcquireGuideStar Then

            objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Acquiring the guide star")
            AcquireGuideStar = False
            RestartGuider = False
            objCam.Autoguider = 1
            objCam.Asynchronous = 0
            objCam.Abort

            'Wait for guider to quit
            On Error Resume Next
            Err.Clear
            Err.Number = 1
            Do While Err.Number <> 0
              Err.Clear
              objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Waiting for guider to quit " & objCam.State)
              Do While objCam.State <> cdStateIdle
                objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Guider State = " &_
                  objCam.State & " Camera = " & objCam.Autoguider & " Restart Guider = " & RestartGuider)
                WScript.Sleep 3000

                RestartGuider = False
                objCam.Autoguider = 1
                objCam.Abort
              Loop

              objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Guider State = " & objCam.State)
              Err.Clear
              FindGuideStar

              If Err.Number <> 0 Then
                objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Error restarting the autoguider: " & Err.Description)
              End If
            Loop
            On Error Goto 0           

            objCam.Asynchronous = 1
            objCam.Autoguider = 0
            RestartGuider = True

          End If

          ErrCount = 0
          If RestartGuider Then

            RestartGuider = False
            On Error Resume Next
            Err.Number = 1
            Do While Err.Number <> 0
              Err.Clear

              objCam.Autoguider = 1
              objCam.Asynchronous = 0
              objCam.Abort
 
              'Wait for guider to quit
              objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Waiting for guider to quit; state = " & objCam.State)
              Do While objCam.State <> cdStateIdle
                objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Guider State = " & objCam.State)
                WScript.Sleep 3000
              Loop

              objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Restarting the autoguider")
              objCam.Autoguider = 1
              objCam.Asynchronous = 1
              objCam.Autoguide
              objCam.Autoguider = 0

              'Fixes Memory Error code 205 (?)
              If Err.Number <> 0 Then
                objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Error restarting the autoguider: " & Err.Description)
                ErrCount = ErrCount + 1
                If ErrCount > 5 Then
                  objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Error restarting guider 5 times, reconnecting")
                  objCam.Disconnect
                  WScript.Sleep 3000
                  objCam.Connect
                End If 
                WScript.Sleep 3000               
              End If

            Loop
            On Error Goto 0

          End If 'RestartGuider
        End If 'UseGuider
        
        AzAltfail = Utils.ConvertRADecToAzAlt(adnow(0),adnow(1))
        HAFail = Utils.ComputeHourAngle(adnow(0))
        objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Current Az=" & AzAltFail(0) & " Alt=" & AzAltFail(1) & " HA=" & HAFail)

        'Change the filter (Slow... cannot do during readout through CCDSoft)
        CheckCam
        If objCam.FilterIndexZeroBased <> objFilter Then
          objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Changing filter from " &_
            objCam.szFilterName(objCam.FilterIndexZeroBased) & " to " & objCam.szFilterName(objFilter))
          objCam.FilterIndexZeroBased = objFilter
        End If

        'TakeImage
        objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Taking image")
        CheckCam
        objCam.AutoGuider=0
        objCam.TakeImage    

        'filename of the image -- nYYYYMMDD.objName.####.fits
        index = GetIndex(objName)
        strFileName = "n" & night & "." & objName & "." & index & ".fits"

        'Write to the Log
        Call WriteLog

        'wait for exposure to complete
        Do While (Not CBool(objCam.IsExposureComplete))
          CheckCam
        Loop

        On Error Resume Next
          'Write the object RA and Dec to the header since we have to disconnect from telescope
          Set Image = CreateObject("CCDSoft.Image")
          Image.AttachToActiveImager
          Image.FITSKeyword("OBJCTRA") = ra
          Image.FITSKeyword("OBJCTDEC") = dec
          Image.Save
        Image.Close
        On Error Goto 0    

        'Rename the image to something reasonable
        objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Renaming file from " &_
          objCam.LastImageFileName & " to " & strFileName)
        objFSO.MoveFile datadir & objCam.LastImageFileName, datadir & strFileName        

        ' Solve the frame in the background
        cmd = "asyncastrom.bat " & datadir & strFileName & " " & ra*15 & " " & dec 
        objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Beginning Coordinate Solution (in background); cmd=" & cmd)  
        Set ObjWS = WScript.CreateObject("WScript.Shell")
	dummy = ObjWS.Run(cmd,1,0)
        
If 0 Then
'If UseGuider Then
        'Guide with science image
        objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Finding Centroid")
        subframesize = 40
        XY = Centroid(dataDir & strFileName, targetX,targetY,subFrameSize)
        XY(0) = TargetX - subFrameSize/2 + XY(0) 
        XY(1) = TargetY - subFrameSize/2 + XY(1) 

        objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): star centered at " & XY(0) & "," & XY(1) & " min=" & XY(2) & " max=" & XY(3) & " mean=" & XY(4))
        If XY(4) < 10 Then 
          objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Star out of subframe; recentering")        
          AcquireObject = True
        Else 

	  If XY(3) > 55000 Then
	    objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Target saturated; reducing exposure time from " & objCam.ExposureTime & " to " & objCam.ExposureTime/2)
            objCam.ExposureTime = objCam.ExposureTime/2
          End If        

          PlateScale = 0.754
          RAOffset  = (XY(0) - TargetX)*Platescale
          DecOffset = (XY(1) - TargetY)*Platescale
          objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Centering with guider")        
          objCam.Autoguider = 1
          objCam.EnabledXAxis = True
          objCam.EnabledYAxis = True
          GuiderScaleArcsecPerPixel = 3.09
          Aggressiveness = 0.75
          FromX = 0
          FromY = 0
          ToX = RAOffset/GuiderScaleArcsecPerPixel*Aggressiveness
          ToY = DecOffset/GuiderScaleArcsecPerPixel*Aggressiveness
          Maxoffset = 10*Platescale/GuiderScaleArcsecPerPixel


	  offset = sqr(tox^2 + toy^2)
	  If Offset < MaxOffset then
            'Reverse x correction if West of Meridian
            If MeridianFlip Then ToX = -ToX
            objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Moving from " & fromX & "," & fromY & " to " & toX & "," & toY)        
            Call objCam.Move(FromX, FromY, ToX, ToY)
            objCam.EnabledXAxis = False
            objCam.EnabledYAxis = False 
            objCam.Autoguider = 0
            BadCenter = 0
          Else
            objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Star too far away; offset = " & offset)
            BadCenter = BadCenter + 1

            If BadCenter = 3 Then
              objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Too many bad centers -- recentering")
              AcquireObject = True
              BadCenter = 0
            End If
          End If 

        End If

'End If   
End If

      Else
        Call GetWeather(strWindSpeed,strWindDir,strHumidity,strRain,strPressure,strTemp)
        objEngFile.WriteLine("Temp = " & strTemp & " C" & vbCrLf &_
                             "Wind Speed = " & strWindSpeed & " m/s" & vbCrLf &_
		                         "Humidity = " & strHumidity & "%" & vbCrLf &_
                             "Rain = " & strRain & " mm" & vbCrLf &_
                             "Sun Altitude = " & SunAlt & " degrees" & vbCrLf)
        If NLoops = 0 Then 
          strBody = strBody & "Roof Closed at " & now & vbCrLf
      	  strBody = strBody & "Temp = " & strTemp & " C" & vbCrLf &_
		                          "Wind Speed = " & strWindSpeed & " m/s" & vbCrLf &_
		                          "Humidity = " & strHumidity & "%" & vbCrLf &_
                              "Rain = " & strRain & " mm" & vbCrLf &_
                              "Sun Altitude = " & SunAlt & " degrees" & vbCrLf & vbCrLf
        End If
        WScript.Sleep 300000  
      End if

      'Recalculate the current time
      JDNow = jd(Year(Now),Month(Now),Day(Now),Hour(Now),Minute(Now),Second(Now))
      If JDNow > JDEnd Then 
        Exit For
      End If
    Next 'For each filter

    If RoofOpen Then
      If NLoops > 0 and NTaken = 0 Then 
        strBody = strBody & "Roof Open at " & now & vbCrLf
      End If

      NTaken = NTaken + 1
    End If

    NLoops = NLoops + 1

  Loop

  If UseGuider Then
    objCam.Autoguider = 1
    objCam.Abort
    objCam.Autoguider = 0
  End If
  objTel.Connect

  If objFSO.FileExists("C:\demonex\share\solve.txt") Then
    objFSO.DeleteFile("C:\demonex\share\solve.txt")
  End If

  objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Done with " & objName & " at " & jdNow & "; took " & NTaken & " images")
  objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Stop tracking")
  CheckTel
  Call objTel.SetTracking(0, 0, 0, 0)  

End Sub