Sub DoObject(objName,ra,dec,jdstart,jdend,night,arrFilters,ExpTime,NImages)

  GuideBoxSize = 32
  StopGuiding = False
  RestartGuider = False
  AcquireGuideStar = True

  Const Light = 1
  Const cdStateIdle = 0

  Set Utils = CreateObject("TheSky6.Utils")
  Set objImage = WScript.CreateObject("CCDSoft.Image")

  'For auto-adjusting the exposure time
  biasLevel = 2367
  targetCounts = 40000 'includes bias level
  maxExpTime = 1
  boxHalfSize = 25
  MaxSunAlt = -9

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
  
  MeridianFlip = False

  'Wait until start time
  if jdNow < jdStart then
    sleepTime = (jdStart - jdNow)*86400000
    objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Script Started before jdStart; Turning tracking off and waiting for " &_
      sleeptime/1000 & " seconds")
    Call objTel.SetTracking(0, 0, 0, 0)
    WScript.Sleep sleepTime
  End If

  objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Begin tracking")
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
  Do While (jdNow < jdEnd and NTaken < NImages and SunAlt < MaxSunAlt)

    objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Entering Loop; JDNow=" & jdNow & " JDEnd=" & jdEnd )

    For Each objFilter in arrFilters
      If RoofOpen Then

        'Focus
        Focus

        objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Roof Open; beginning image " &_
          Ntaken + 1 & " of " & NImages)

        'Change the filter (Slow... cannot do during readout through CCDSoft)
        CheckCam
        If objCam.FilterIndexZeroBased <> objFilter Then
          objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Changing filter from " &_
            objCam.szFilterName(objCam.FilterIndexZeroBased) & " to " & objCam.szFilterName(objFilter))
          objCam.FilterIndexZeroBased = objFilter
        End If

        'Set up the initial exposure time, pointing
        adNow = Utils.Precess2000ToNow(ra,dec)
	If AcquireObject Then
          If JDNow > TransitTime Then
            MeridianFlip = True
          End If

          AcquireGuideStar = True
          'Call CenterObject(adnow)
        End If
   
        'Deal with Meridian Flip (Force no meridian flip when close??)
        If JDNow > TransitTime and Not MeridianFlip Then
          MeridianFlip = True
'          NTaken = 0 'WHY DID I DO THIS?
          objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Object about to transit; aborting guider and flipping meridian")

          objCam.Autoguider = 1
          objCam.Asynchronous = 0
          objCam.Abort

          AcquireGuideStar = True
          'Call CenterObject(adnow)
        End If

        If AcquireGuideStar Then

          objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Acquiring the guide star")
          AcquireGuideStar = False
          RestartGuider = False
          objCam.Autoguider = 1
          objCam.Asynchronous = 0
          objCam.Abort

          'Wait for guider to quit
          objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Waiting for guider to quit " & objCam.State)
          Do While objCam.State <> cdStateIdle
            objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Guider State = " &_
              objCam.State & " Camera = " & objCam.Autoguider & " Restart Guider = " & RestartGuider)
            WScript.Sleep 100

            RestartGuider = False
            objCam.Autoguider = 1
            objCam.Abort
          Loop

          objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Guider State = " & objCam.State)
          FindGuideStar
          objCam.Asynchronous = 1
          objCam.Autoguider = 0
          RestartGuider = True

        End If

        If RestartGuider Then

          RestartGuider = False
          On Error Resume Next
          Do While Err.Number <> 0

            objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Restarting the autoguider")
            objCam.Autoguider = 1
            objCam.Asynchronous = 0
            objCam.Abort

            'Wait for guider to quit
            objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Waiting for guider to quit; state = " & objCam.State)
            Do While objCam.State <> cdStateIdle
              objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Guider State = " & objCam.State)
              WScript.Sleep 1000
            Loop

            objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Restarting the autoguider")
            objCam.Autoguider = 1
            objCam.Asynchronous = 1

            objCam.Autoguide
            objCam.Autoguider = 0

            If Err.Number <> 0 Then
              objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Error restarting the autoguider: " & Err.Description)
            End If
         Loop
         On Error Goto 0

        End If

        AzAltfail = Utils.ConvertRADecToAzAlt(adnow(0),adnow(1))
        HAFail = Utils.ComputeHourAngle(adnow(0))
        objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Current Az=" & AzAltFail(0) & " Alt=" & AzAltFail(1) & " HA=" & HAFail)

        'TakeImage
        objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Taking image")
        CheckCam
        objCam.TakeImage

        'filename of the image -- nYYYYMMDD.objName.####.fits
        strFileName = "n" & night & "." & objName & "." & GetIndex(objName) & ".fits"

	'Write to the Log
        Call WriteLog

        'wait for exposure to complete
        Do While (Not CBool(objCam.IsExposureComplete))
          CheckCam
        Loop

        'Rename the image to something reasonable
        objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Renaming file from " &_
          objCam.LastImageFileName & " to " & strFileName)
        objFSO.MoveFile datadir & objCam.LastImageFileName, datadir & strFileName

      Else
        objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Roof Closed; retry in 5 minutes")
        WScript.Sleep 300000  
      End if

      'Recalculate the current time
      JDNow = jd(Year(Now),Month(Now),Day(Now),Hour(Now),Minute(Now),Second(Now))
      If JDNow > JDEnd Then 
        Exit For
      End If
    Next 'For each filter

    NTaken = NTaken + 1

  Loop

  objCam.Autoguider = 1
  objCam.Abort
  objCam.Autoguider = 0
  objTel.Connect

  objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Done with " & objName & " at " & jdNow & "; took " & NTaken & " images")

End Sub

Function CenterObject(adNow)

  On Error Resume Next

  objTel.Connect

  'If a powercycle ruined the pointing
  If NotAligned Then 
    PointAndSync
  End If

  'Slew Telescope
  objEngFile.WriteLine("CenterObject (" & FormatDateTime(Now,3) & "): Slewing to " & objName & " " & ra & " " & dec )
  CheckTel
  SlewStart = Now

  Call objTel.SlewToRaDec(adNow(0),adNow(1),objName)  
'  Do While Not CBool(objTel.IsSlewComplete)
'    CheckTel
'  Loop
'  WScript.Sleep 120000

  'Wait for Telescope to finish slewing
  RACurrent = -1
  RAPrevious = -2
  DecCurrent = -1
  DecPrevious = -2
  Do While Round(RAPrevious*100000) <> Round(RACurrent*100000) and Round(DecPrevious*10000) <> Round(DecCurrent*10000)
    RAPrevious = RACurrent
    DecPrevious = DecCurrent
    Call objTel.GetRaDec()
    RACurrent  = objTel.dRa
    DecCurrent = objTel.dDec
    objEngFile.WriteLine("CenterObject (" & FormatDateTime(Now,3) & "): Slewing: Current RA/dec = " & RACurrent & ", " & DecCurrent & ", Previous RA/Dec = " & RAPrevious & ", " & DecPrevious & ", RA/Dec desired = " & adNow(0) & ", " & adNow(1) & "; reattempting acquisition.")
    WScript.Sleep 5000
  Loop
  WScript.Sleep 10000

'  'Recursive call to make sure telescope points correctly
'  If Round(RACurrent*100) <> Round(adNow(0)*100) or Round(DecCurrent*10) <> Round(adNow(1)*10) Then
'    objEngFile.WriteLine("CenterObject (" & FormatDateTime(Now,3) & "): Warning: Slew failed. RA/dec = " & RACurrent & ", " & DecCurrent & ". RA/Dec desired = " & adNow(0) & ", " & adNow(1) & "; reattempting acquisition.")
'    CenterObject(adNow)
''    Exit Function
 ' End If

  objEngFile.WriteLine("CenterObject (" & FormatDateTime(Now,3) & "): Slew Completed in " & Round((Now - slewStart)*86400) & " seconds")

  'Disconnect the telescope so TheSky6 doesn't fight with the guider
  objTel.Disconnect() 
  objTheSky.DisconnectTelescope()

  AcquireObject = False
'  AcquireGuideStar = True

End Function

Public Sub MyCamera_CameraEvent(EventID, WhichCamera, MyString, Param1, Param2)

'  On Error Resume Next

  Const cdConnected=0
  Const cdDisconnected=1
  Const cdBeforeTakeImage=2
  Const cdAfterTakeImage=3
  Const cdBeforeSelectFilter=4
  Const cdAfterSelectFilter=5
  Const cdBeforeFlipMirror=6
  Const cdAfterFlipMirror=7
  Const cdBeforeDelay=8
  Const cdAfterDelay=9
  Const cdBeforeExposure=10
  Const cdAfterExposure=11
  Const cdBeforeDigitize=12
  Const cdAfterDigitize=13
  Const cdBeforeDownload=14
  Const cdAfterDownload=15
  Const cdBeforeImageCalibration=16
  Const cdAfterImageCalibration=17
  Const cdBeforeAutoSave=18
  Const cdAfterAutoSave=19
  Const cdBeforeDisplayImage=20
  Const cdAfterDisplayImage=21
  Const cdGuideError=22
  Const cdMaximumFound=23
  Const cdExposing=24

  EventNames = Array("cdConnected","cdDisconnected","cdBeforeTakeImage","cdAfterTakeImage","cdBeforeSelectFilter","cdAfterSelectFilter","cdBeforeFlipMirror","cdAfterFlipMirror","cdBeforeDelay","cdAfterDelay","cdBeforeExposure","cdAfterExposure","cdBeforeDigitize","cdAfterDigitize","cdBeforeDownload","cdAfterDownload","cdBeforeImageCalibration","cdAfterImageCalibration","cdBeforeAutoSave","cdAfterAutoSave","cdBeforeDisplayImage","cdAfterDisplayImage","cdGuideError","cdMaximumFound","cdExposing")

'  objEngFile.WriteLine("Camera Event " & EventNames(EventID) & " (" & FormatDateTime(Now,3) & "): Camera = " & WhichCamera & " State = " & objCam.State )

  'After the file is saved
  If (EventId = cdAfterAutoSave) Then
'    If WhichCamera = 0 Then
'
'      'filename of the image -- nYYYYMMDD.objName.####.fits
'      strFileName = "n" & night & "." & objName & "." & GetIndex(objName) & ".fits"
'
'      'Rename the image to something reasonable
'      objEngFile.WriteLine("Camera Event " & EventNames(EventID) & " (" & FormatDateTime(Now,3) & "): Renaming file from " &_
'          objCam.LastImageFileName & " to " & strFileName)
'      objFSO.MoveFile datadir & objCam.LastImageFileName, datadir & strFileName
'    
'      'Write the current exposure to the Log
'      If objName <> "SkyFlat" Then
'        Call WriteLog(strFileName,objName)
'      End If
'    Else 
'      'objFSO. objCam.LastImageFileName
'
'    End If 
  End If

  'If it's a calibration frame, don't do anything fancy
  If Calibrate Then
    'nothing
  End If

  'Before exposing
  If (EventId = cdBeforeExposure) Then
    'nothing 
  End If

  'During the exposure
  If (EventId = cdExposing) Then
    If WhichCamera = 0 Then
      'nothing
    End If
  End If

  'During readout
  If (EventId = cdBeforeDownload) Then
    'nothing
  End If

  'Before Guider Corrections
  If (EventId = cdGuideError) Then

    Set objImage = WScript.CreateObject("CCDSoft.Image")
    objImage.AttachToActiveAutoGuider

    If objImage.Width <> GuideBoxSize Then
      objEngFile.WriteLine("Camera Event " & EventNames(EventID) & " (" & FormatDateTime(Now,3) & "): Acquisition image; exiting guiding script")
      Exit Sub
    End If

    Agressiveness = 0.75

    objCam.Autoguider = 1
    objCam.EnabledXAxis = True
    objCam.EnabledYAxis = True

    objImage.ShowInventory
    X = objImage.InventoryArray(cdInventoryX)
    Y = objImage.InventoryArray(cdInventoryY)
    Magnitude    = objImage.InventoryArray(cdInventoryMagnitude)
    objClass     = objImage.InventoryArray(cdInventoryClass)
    FWHM         = objImage.InventoryArray(cdInventoryFWHM)
    MajorAxis    = objImage.InventoryArray(cdInventoryMajorAxis)
    MinorAxis    = objImage.InventoryArray(cdInventoryMinorAxis)
    Theta        = objImage.InventoryArray(cdInventoryTheta)
    Ellipticity  = objImage.InventoryArray(cdInventoryEllipticity)

    Nstars = UBound(X)
    TargetMag = 2.0   
    MaxMag = 2.5
    MaxBadGuides = 3

    CurrentExpTime = objCam.AutoGuiderExposureTime
    objEngFile.WriteLine("Camera Event " & EventNames(EventID) & " (" & FormatDateTime(Now,3) & "): Found " & NStars & " stars with exptime = " & CurrentExpTime)

    MinExpTime = 0.01 'beyond which it doesn't matter to take a shorter exposure
    MaxExpTime = 60.0 'beyond which it doesn't make sense to take a guide exposure

    If NStars > 0 Then
      If Magnitude(0) < MaxMag Then

	'Scale the Exposure Time to get Mag = TargetMag
	Scale = 10^(-0.4*(TargetMag - Magnitude(0)))
       
	If Scale < 0.5 or Scale > 2 and Not RestartGuider Then
          If CurrentExpTime > MinExpTime or Scale > 1 Then
            objEngFile.WriteLine("Camera Event " & EventNames(EventID) & " (" & FormatDateTime(Now,3) & "): Scaling Autoguider exposure from " & CurrentExpTime & " to " & CurrentExpTime*Scale)
            objCam.AutoGuiderExposureTime = CurrentExpTime*Scale
            RestartGuider = True
          Else
            RestartGuider = False
          End If
        Else
            RestartGuider = False
        End If        

        FromX = objImage.Width/2.0 + (X(0) - objImage.Width/2.0)*Agressiveness
        FromY = objImage.Height/2.0 + (Y(0) - objImage.Height/2.0)*Agressiveness

        ToX = objImage.Width/2.0
        ToY = objImage.Height/2.0
        objEngFile.WriteLine("Camera Event " & EventNames(EventID) & " (" & FormatDateTime(Now,3) & "): Moving Guide Star from (" & FromX & "," & FromY & ") to (" & ToX & "," & ToY & ")")
        Call objCam.Move(FromX, FromY, ToX, ToY)

        BadGuideCounter = 0
   
      Else
        If Not RestartGuider Then
          objEngFile.WriteLine("Camera Event " & EventNames(EventID) & " (" & FormatDateTime(Now,3) & "): Guide star dimmed beyond threshhold; doubling exposure time and ignoring correction")
          objCam.AutoGuiderExposureTime = CurrentExpTime*2
          BadGuideCounter = BadGuideCounter + 1 
          RestartGuider = True
        End If
      End If
    Else 
      If Not RestartGuider Then
        objEngFile.WriteLine("Camera Event " & EventNames(EventID) & " (" & FormatDateTime(Now,3) & "): No stars in subframe; doubling exposure time and increasing subframe size")
        objCam.AutoGuiderExposureTime = CurrentExpTime*2
        BadGuideCounter = BadGuideCounter + 1
        RestartGuider = True
      End If
    End If

    objCam.EnabledXAxis = False
    objCam.EnabledYAxis = False 

    If BadGuideCounter >= MaxBadGuides or objCam.AutoGuiderExposureTime > MaxExpTime Then
      objEngFile.WriteLine("Camera Event " & EventNames(EventID) & " (" & FormatDateTime(Now,3) & "): Too many bad guides, Reacquiring Guide Star")
      AcquireGuideStar = True    
      RestartGuider = True 
      BadGuideCounter = 0
    End If

    objImage.Close
    objCam.Autoguider = 0
 
  End If 'Camera Event cdGuideError

End Sub