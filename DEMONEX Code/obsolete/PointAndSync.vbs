Sub PointAndSync

  MaxTries = 3
  
  Set Utils = CreateObject("TheSky6.Utils")

  Randomize
  Az = Rnd*360
  Alt = Rnd*50 + 30

  objEngFile.WriteLine("PointAndSync (" & FormatDateTime(Now,3) & "): Moving to Alt Az = " & Alt & " " & Az)
  On Error Resume Next
  CheckTel
  SyncTime
  Call objTel.SlewToAzAlt(Az, Alt, "Pointing")
  Wscript.Sleep 30000

  Do While Err.Number <> 0 
 
    BadPoint = BadPoint + 1
    If BadPoint > MaxTries Then
      objEngFile.WriteLine("PointAndSync (" & FormatDateTime(Now,3) & "): Unrecoverable error pointing scope; exiting. " & Err.Description)

      HomeScope
      DisconnectAll
      ScopeOff

      'Email error about failed connection    
      strTo = StudentEmail & "," & EmergencyTxt
      strSubject = "DEMONEX Error"
      strBody = "Could not point the telescope"
      strAttachment = logdir & "n" & night & ".eng"
      objEngFile.Close

      'Email log
      Call Email(strTo,strSubject,strBody,strAttachment)

      WScript.Quit(0)

    End If

    objEngFile.WriteLine("PointAndSync (" & FormatDateTime(Now,3) & "): Error Pointing, rebooting scope. " & Err.Description)
    Err.Clear   

    HomeScope
    DisconnectAll
    ScopeOff
    Wscript.Sleep 30000
    ScopeOn
    ConnectAll

    objEngFile.WriteLine("PointAndSync (" & FormatDateTime(Now,3) & "): Repointing scope")
    CheckTel
    SyncTime

    Az = Rnd*360
    Alt = Rnd*50 + 30
    Call objTel.SlewToAzAlt(Az, Alt, "Pointing")    
    Wscript.Sleep 30000
  Loop  
  On Error Goto 0

  RADec = Utils.ConvertAzAltToRADec(Az, Alt)

  MaxSunAlt = -4

  objCam.ExposureTime = 15
  objCam.Frame = 1 'Light

  NTaken = 0

  Do While (NTaken < MaxTries and SunAlt < MaxSunAlt)  
    If RoofOpen Then

      objEngFile.WriteLine("PointAndSync (" & FormatDateTime(Now,3) & "): Making sure tracking is on")
      Call objTel.SetTracking(1, 1, 1, 1)

      objEngFile.WriteLine("PointAndSync (" & FormatDateTime(Now,3) & "): Roof open; beginning attempt " &_
        Ntaken + 1 & " of " & MaxTries)

      objCam.TakeImage

      'Solve the coordinates of the image
      coorSolveStart = Now
      objEngFile.WriteLine("PointAndSync (" & Now & "): Beginning Coordinate Solution")

      On Error Resume Next
      Set Image = CreateObject("CCDSoft.Image")
      Image.AttachToActive'Imager
      Image.ScaleInArcsecondsPerPixel = 0.754
      Image.InsertWCS True

      If Err.Number = 0 Then
        RADec = Image.XYToRaDec(Image.Width/2,Image.Height/2)

        Call objTheSky.GetObjectRaDec("Image Link Information")
        CheckTel

        'TheSky6 Doesn't take into account the TPoint Model when syncing, must sync in telescope's raw coordinates
        Call TalkToLX200(":GR#", strRA, 2, 10)
        Call TalkToLX200(":GD#", strDec, 2, 10)
        RawRA  = utils.ConvertStringToRA(strRA)
        RawDec = utils.ConvertStringToDec(strDec)
        SyncRA  = RawRA + (objTheSky.dObjectRa - RADec(0))
        SyncDec = RawDec + (objTheSky.dObjectDec - RADec(1))

        Call objTel.Sync(SyncRA,SyncDec, "Image Link's Solution")

        objEngFile.WriteLine("PointAndSync (" & Now & "): Completed Coordinate Solution in " & Round((Now - coorSolveStart)*86400) & " seconds")
        objEngFile.WriteLine("PointAndSync (" & Now & "): RA/Dec Attempted: " & RADec(0) & " " & RADec(1) & " RA/Dec Actual: " & objTheSky.dObjectRa & " " &  objTheSky.dObjectDec)
        objEngFile.WriteLine("PointAndSync (" & Now & "): Pointing off by " & (RADec(0) - objTheSky.dObjectRa)*900*cos(objTheSky.dObjectDec*Atn(1)/45) & "' in RA and " & (RADec(1) - objTheSky.dObjectDec)*60 & "' in Dec") 

        strBody = "Pointing off by " & Round((RADec(0) - objTheSky.dObjectRa)*900*cos(objTheSky.dObjectDec*Atn(1)/45),2) & "' in RA and " & Round((RADec(1) - objTheSky.dObjectDec)*60,2) & "' in Dec" & vbCrLf & vbCrLf & strBody

        NotAligned = False

        Exit Sub
      Else 
        objEngFile.WriteLine("PointAndSync (" & Now & "): Error: " & Err.Number & " " & Err.Description & "; retrying sync")
        Err.Clear
        NTaken = NTaken + 1
      End If
      On Error Goto 0

    Else
      objEngFile.WriteLine("PointAndSync (" & FormatDateTime(Now,3) & "): Roof Closed; retry in 5 minutes")
      'Turn Tracking off (just in case)
      objEngFile.WriteLine("PointAndSync (" & FormatDateTime(Now,3) & "): Making sure tracking is off")
      Call objTel.SetTracking(0, 0, 0, 0)
      WScript.Sleep 300000  
    End If
  Loop


  If NTaken >= MaxTries Then 
    objEngFile.WriteLine("PointAndSync (" & FormatDateTime(Now,3) & "): WARNING: Sync Failed; re-aligning on home")  
    BadPoint = BadPoint+1
    HomeScope
    PointAndSync
  End If


End Sub