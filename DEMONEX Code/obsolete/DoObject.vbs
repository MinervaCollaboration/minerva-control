Sub DoObject(objName,ra,dec,jdstart,jdend,night,arrFilters,ExpTime,NImages)

  Const ForReading = 1
  Const Light = 1

  'SExtractor inventory constants:
  Const cdInventoryX=0
  Const cdInventoryY=1
  Const cdInventoryMagnitude=2
  Const cdInventoryClass=3
  Const cdInventoryFWHM=4
  Const cdInventoryMajorAxis=5
  Const cdInventoryMinorAxis=6
  Const cdInventoryTheta=7
  Const cdInventoryEllipticity=8

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
  If Hour(Now) > 12 and Result(1) < 12 Then  
    TransitTime = jd(Year(Now+1),Month(Now+1),Day(Now+1),0,0,0) + result(1)/24
  Else
    TransitTime = jd(Year(Now),Month(Now),Day(Now),0,0,0) + result(1)/24
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
    objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Done waiting; resuming tracking")
    Call objTel.SetTracking(1, 1, 1, 1)
  End If

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

'        'Change the filter (Slow... cannot do during readout through CCDSoft)
'        CheckCam
'        If objCam.FilterIndexZeroBased <> objFilter Then
'          objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Changing filter from " &_
'            objCam.szFilterName(objCam.FilterIndexZeroBased) & " to " & objCam.szFilterName(objFilter))
'          objCam.FilterIndexZeroBased = objFilter
'        End If

        'Set up the initial exposure time, pointing
        adNow = Utils.Precess2000ToNow(ra,dec)
	If AcquireObject Then
          If JDNow > TransitTime Then
            MeridianFlip = True
          End If
          objCam.Autoguider = 1
          objCam.Abort
          Call CenterObject(adnow)
          objCam.Autoguider = 0
        End If
   
        'Deal with Meridian Flip (Force no meridian flip when close??)
        If JDNow > TransitTime and Not MeridianFlip Then
          MeridianFlip = True
          NTaken = 0
          objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Object about to transit; flipping meridian and reacquiring object")
          objCam.Autoguider = 1
          objCam.Abort
          Call CenterObject(adnow)
          objCam.Autoguider = 0
        End If

        'TakeImage
        objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Taking image")
        CheckCam
        objCam.TakeImage
        'wait for exposure to complete
        Do While (Not CBool(objCam.IsExposureComplete))
          CheckCam
        Loop

        'filename of the image -- nYYYYMMDD.objName.####.fits
        strFileName = "n" & night & "." & objName & "." & GetIndex(objName) & ".fits"

	'Write to the Log
        Call WriteLog

        'Update the guide star coordinates to account for differential drift
        objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Determining guider drift")
        objImage.AttachToActiveImager
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

        If NTaken = 0 Then
          'Finds the brightest star within 50 pixels of the edge for reference
          For i=0 to UBound(X) - 1
            If X(i) > 50 and X(i) < 1998 and Y(i) > 50 and Y(i) < 1998 and FWHM(i) > 1 and Ellipticity(i) < 1.5 Then
              RefX = X(i)
              RefY = Y(i)
              objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Reference Star found at (x,y) = (" &_
                RefX & "," & RefY & "); Magnitude = " & Magnitude(i) & ", Class = " & objClass(i) & ", FWHM = " &_
                FWHM(i) & ", MajorAxis = " & MajorAxis(i) & ", MinorAxis = " & MinorAxis(i) & ", Theta = " &_
                Theta(i) & ", Ellipticity = " & Ellipticity(i))
              RefStar = i
              Exit For
            End If
          Next
        Else 

          'Look through the 50 brightest stars for the closest matching the brightest in the reference frame
          if UBound(x) > RefStar + 25 Then 
            MaxStars = RefStar + 25
          Else
            MaxStars = UBound(X)
          End If
          If RefStar > 25 Then 
            MinStars = Refstar - 25
          Else 
            MinStars = 0
          End If

          Mindist = sqr(2)*2048
          For i=MinStars to MaxStars - 1
             dist = sqr((RefX - X(i))^2 + (RefY - Y(i))^2)
             If dist < mindist Then
               MinDist = dist
               Star = i
             End If
          Next

          objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Closest bright star matching reference star (" &_
                RefX & "," & RefY & ") found at (" & X(Star) & "," & Y(Star) & "); distance = " & MinDist)

if MinDist < 10 Then
          objCam.Autoguider = 1  
          newGuideStarX = objCam.GuideStarX + (refX - X(star))/4.11432846 'ratio of platescales
          newGuideStarY = objCam.GuideStarY + (refY - Y(star))/4.11432846 'ratio of platescales
          objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Moving guide star from " &_
            objCam.GuideStarX & "," & objCam.GuideStarY & " to " & newGuideStarX & "," & newGuideStarY)
          objCam.GuideStarX = newGuideStarX 
          objCam.GuideStarY = newGuideStarY
          objCam.Autoguider = 0
End If

        End If
        objImage.close

        'Rename the image to something reasonable
        objEngFile.WriteLine("DoObject (" & FormatDateTime(Now,3) & "): Renaming file from " &_
          objCam.LastImageFileName & " to " & strFileName)
        objFSO.MoveFile datapath & objCam.LastImageFileName, datapath & strFileName



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

  'Slew Telescope
  objEngFile.WriteLine("CenterObject (" & FormatDateTime(Now,3) & "): Slewing to " & objName & " " & ra & " " & dec )
  CheckTel
  SyncTime
  SlewStart = Now

  Call objTel.SlewToRaDec(adNow(0),adNow(1),objName)  
  Do While Not CBool(objTel.IsSlewComplete)
    CheckTel
  Loop
  WScript.Sleep 120000

'*****************KLUDGE*******************
'OH NO HE DI'INT... AIM 10' NORTH/SOUTH OF TARGET... KLUDGE!
If MeridianFlip Then 
  Direction = "South"
Else 
  Direction = "North"
End If
Call objTel.Jog(10,Direction)
'*****************KLUDGE*******************

  Do While Not CBool(objTel.IsSlewComplete)
    CheckTel
  Loop
  WScript.Sleep 10000

'  Do While Err.Number <> 0
'    If objTel.GetLastSlewError = 229 Then
'      objEngFile.WriteLine("CenterObject (" & FormatDateTime(Now,3) & "): Attempted slew below horizon; retrying")
'      WScript.Sleep 60000
'      'Slew Telescope
'      CheckTel
'      SyncTime
'      SlewStart = Now
'      Call objTel.SlewToRaDec(adNow(0),adNow(1),objName)  
'    Else
'      objEngFile.WriteLine("CenterObject (" & FormatDateTime(Now,3) & "): Unrecognized error " & objTel.GetLastSlewError & "; aborting object")
'      Exit Do
'    End If
'  Loop

  objEngFile.WriteLine("CenterObject (" & FormatDateTime(Now,3) & "): Slew Completed in " & Round((Now - slewStart)*86400) & " seconds")
  objEngFile.WriteLine("CenterObject (" & FormatDateTime(Now,3) & "): Finding Guide Star")

  'Disconnect the telescope so TheSky6 doesn't fight with the guider
  objTel.Disconnect() 
  objTheSky.DisconnectTelescope()

  objCam.Autoguider = 1
  objCam.ReverseX = MeridianFlip
  objCam.TelescopeDeclination = adNow(1)

  FindGuideStar

  If objCam.GuideStarX <> -1 Then
    objEngFile.WriteLine("CenterObject (" & FormatDateTime(Now,3) & "): Beginning Autoguiding")
    objCam.Asynchronous = 1
    objCam.Autoguide
  End If

  AcquireObject = False
  objCam.Autoguider = 0

End Function

Public Sub MyCamera_CameraEvent(EventID, WhichCamera, MyString, Param1, Param2)

  On Error Resume Next

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

  'After the file is saved
  If (EventId = cdAfterAutoSave) Then

'    'filename of the image -- nYYYYMMDD.objName.####.fits
'    strFileName = "n" & night & "." & objName & "." & GetIndex(objName) & ".fits"
'
'    'Rename the image to something reasonable
'    objEngFile.WriteLine("Camera Event " & EventNames(EventID) & " (" & FormatDateTime(Now,3) & "): Renaming file from " &_
'        objCam.LastImageFileName & " to " & strFileName)
'    objFSO.MoveFile datapath & objCam.LastImageFileName, datapath & strFileName
'    
'    'Write the current exposure to the Log
'    If objName <> "SkyFlat" Then
'      Call WriteLog(strFileName,objName)
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
  If (EventId = cdAfterExposure) Then
    'nothing
  End If

  'During readout
  If (EventId = cdBeforeDownload) Then
    'nothing
  End If

  'Before Guider Corrections
  If (EventId = cdGuideError) Then

    objCam.Autoguider = 1
    MaxGuideErr = 5
    MaxBadGuides = 3
    If objCam.GuideErrorX < MaxGuideErr and objCam.GuideErrorY < MaxGuideErr Then
      objCam.EnabledXAxis = True
      objCam.EnabledYAxis = True
      BadGuideCounter = 0
    Else
      objEngFile.WriteLine("Camera Event " & EventNames(EventID) & " (" & FormatDateTime(Now,3) & "): Guide Correction too large; ignoring correction")
      objCam.EnabledXAxis = False
      objCam.EnabledYAxis = False 
      BadGuideCounter = BadGuideCounter + 1
    End If

    If BadGuideCounter >= MaxBadGuides Then
      objEngFile.WriteLine("Camera Event " & EventNames(EventID) & " (" & FormatDateTime(Now,3) & "): Too many bad guides, increasing exposure time")
      objCam.AutoGuiderExposureTime = objCam.AutoGuiderExposureTime*2
    End If
    objCam.Autoguider = 0
 
  End If 

End Sub