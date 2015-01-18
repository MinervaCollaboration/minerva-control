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

  'After the file is saved
  If (EventId = cdAfterAutoSave) Then
    'nothing
  End If

  'Before exposing
  If (EventId = cdBeforeExposure) Then
    'nothing
  End If

  'During the exposure
  If (EventId = cdExposing) Then
    'nothing
  End If

  'During readout
  If (EventId = cdBeforeDownload) Then
    'Make guide corrections from last frame

    If MovePending Then
      objEngFile.WriteLine("BeforeDownload (" & FormatDateTime(Now,3) & "): Move already pending; waiting for new correction")
      MovePending = 0
    Else

      SolveName = "C:\demonex\share\solve.txt"
      If objFSO.FileExists(solvename) Then
        Set File = objFSO.getFile(SolveName)
        If File.size > 0 Then 

          objEngFile.WriteLine("BeforeDownload (" & FormatDateTime(Now,3) & "): reading coordinate solution")

          Set SolveFile = objFSO.OpenTextFile(Solvename, ForReading)
          line = SolveFile.Readline
          SolveFile.Close
          arr = split(line)
      
          If arr(0) <> "FAIL" Then

            '1 image delay -> This position doesn't take into account the last move
            X = arr(3)
            Y = arr(4)
            Peak = arr(5)

            objEngFile.WriteLine("BeforeDownload (" & FormatDateTime(Now,3) & "): Peak Counts around target: " & peak)

            'What about cosmic rays?
            If Peak > 55000 Then
	      objEngFile.WriteLine("BeforeDownload (" & FormatDateTime(Now,3) & "): Target saturated; reducing exposure time from " & objCam.ExposureTime & " to " & objCam.ExposureTime/2)
              objCam.ExposureTime = objCam.ExposureTime/2
            End If 

            PlateScale = 0.754
            RAOffset  = (X - TargetX)*Platescale
            DecOffset = (Y - TargetY)*Platescale       
            GuiderScaleArcsecPerPixel = 3.09
            Aggressiveness = 0.5 ' (only correct half to eliminate runaway oscillations)
            FromX = 0
            FromY = 0
            ToX = RAOffset/GuiderScaleArcsecPerPixel*Aggressiveness
            ToY = DecOffset/GuiderScaleArcsecPerPixel*Aggressiveness
            Minoffset = 10*Platescale/GuiderScaleArcsecPerPixel' (mount jitter)
            Maxoffset = 300*Platescale/GuiderScaleArcsecPerPixel'fucked

            offset = sqr(tox^2 + toy^2)
            If offset > minoffset Then
              If Offset < MaxOffset Then
                'Reverse x correction if West of Meridian
                If MeridianFlip Then ToX = -ToX
                objEngFile.WriteLine("BeforeDownload (" & FormatDateTime(Now,3) & "): Moving from " & fromX & "," & fromY & " to " & toX & "," & toY)        
                objCam.Autoguider = 1
                objCam.EnabledXAxis = 1
                objCam.EnabledYAxis = 1
                Call objCam.Move(FromX, FromY, ToX, ToY)
                objEngFile.WriteLine("BeforeDownload (" & FormatDateTime(Now,3) & "): Done moving")        
                objCam.EnabledXAxis = 0
                objCam.EnabledYAxis = 0
                objCam.Autoguider = 0
                WScript.Sleep(5000)
                MovePending = 1
              Else
                objEngFile.WriteLine("BeforeDownload (" & FormatDateTime(Now,3) & "): Object too far away -- recentering")
                AcquireObject = True
              End If 
            End If
          Else
            objEngFile.WriteLine("BeforeDownload (" & FormatDateTime(Now,3) & "): Coordinate Solution Failed")
          End If

          objFSO.DeleteFile(SolveName)

        End If 'File not empty

      End If ' solve.txt Exists
  
    End If ' Move Pending

  End If ' Reading out

  'Before Guider Corrections
  If UseGuider Then
    If (EventId = cdGuideError) Then

      Set objImage = WScript.CreateObject("CCDSoft.Image")
      objImage.AttachToActiveAutoGuider

      If objImage.Width <> GuideBoxSize Then
        objEngFile.WriteLine("Camera Event " & EventNames(EventID) & " (" & FormatDateTime(Now,3) & "): Acquisition image (Image width=" & objImage.Width & "); exiting guiding script")
        Exit Sub
      End If

      'what fraction of difference to move
      Agressiveness = 0.5

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
      TargetMag = 1.5   
      MaxMag = 2.5
      MaxBadGuides = 3
      MaxMove = 2 'pixels

      CurrentExpTime = objCam.AutoGuiderExposureTime

      MinExpTime = 0.01 'beyond which it doesn't matter to take a shorter exposure
      MaxExpTime = 60.0 'beyond which it doesn't make sense to take a guide exposure

      If NStars = 1 Then
      
        'Scale the Exposure Time to get Mag = TargetMag
        If Not RestartGuider Then
          Scale = 10^(-0.4*(TargetMag - Magnitude(0))) 
          If Scale < 0.5 or Scale > 2 Then
            If CurrentExpTime = MinExpTime And Scale < 1 Then
              'if it's already at min exptime and it's too bright, just leave it
              RestartGuider = False
            ElseIf CurrentExpTime = MaxExpTime And Scale > 1 Then
              'if it's already at max exptime and it's too faint, just leave it
              RestartGuider = False
            Else
              'scale the exptime
              objEngFile.WriteLine("Camera Event " & EventNames(EventID) & " (" & FormatDateTime(Now,3) & "): Scaling Autoguider exposure from " & CurrentExpTime & " to " & CurrentExpTime*Scale)
              CurrentExpTime = CurrentExpTime*Scale
              If CurrentExpTime > MaxExpTime Then CurrentExpTime = MaxExpTime
              If CurrentExpTime < MinExpTime Then CurrentExpTime = MinExpTime
              objCam.AutoGuiderExposureTime = CurrentExpTime
              RestartGuider = True
            End If
          End If ' 0.5 < Scale < 2
        End If ' Not RestartGuider    

        FromX = objImage.Width/2.0 + (X(0) - objImage.Width/2.0)*Agressiveness
        FromY = objImage.Height/2.0 + (Y(0) - objImage.Height/2.0)*Agressiveness
ToX = GuideboxSize/2
ToY = GuideboxSize/2


        If Abs(FromX-ToX) > maxMove or abs(fromY-ToY) > maxMove Then
          objEngFile.WriteLine("Camera Event " & EventNames(EventID) & " (" & FormatDateTime(Now,3) & "): Desired Move too big, not moving: (" & FromX & "," & FromY & ") to (" & ToX & "," & ToY & ")")
          BadGuideCounter = BadGuideCounter + 1
        Else
          objEngFile.WriteLine("Camera Event " & EventNames(EventID) & " (" & FormatDateTime(Now,3) & "): Moving Guide Star from (" & FromX & "," & FromY & ") to (" & ToX & "," & ToY & ")")
          Call objCam.Move(FromX, FromY, ToX, ToY)
          BadGuideCounter = 0
        End If
      ElseIf Nstars > 1 Then
        If Not RestartGuider Then
          objEngFile.WriteLine("Camera Event " & EventNames(EventID) & " (" & FormatDateTime(Now,3) & "): Multiple guide stars (" & Nstars & ") in box; acquiring new guide star")
          AcquireGuideStar = True
          RestartGuider = True 
          BadGuideCounter = 0
        End If  
      Else
        If Not RestartGuider Then
          objEngFile.WriteLine("Camera Event " & EventNames(EventID) & " (" & FormatDateTime(Now,3) & "): Guide star dimmed beyond threshhold; doubling exposure time to " & CurrentExpTime*2)
          CurrentExpTime = CurrentExpTime*2
          objCam.AutoGuiderExposureTime = CurrentExpTime
          BadGuideCounter = BadGuideCounter + 1 
          RestartGuider = True
        End If
      End If 'Nstars = 1
   
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
  End If 'Use Guider
 
End Sub