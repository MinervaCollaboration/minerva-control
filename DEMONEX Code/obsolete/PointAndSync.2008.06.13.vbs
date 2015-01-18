Sub PointAndSync

  MaxTries = 3
  Set Utils = CreateObject("TheSky6.Utils")

  Az = 270
  Alt = 75

  objEngFile.WriteLine("PointAndSync (" & FormatDateTime(Now,3) & "): Moving to Alt Az")
  On Error Resume Next
  CheckTel
  Call objTel.SlewToAzAlt(Az, Alt, "Pointing")
  Wscript.Sleep 120000
  If Err.Number <> 0 Then 
    objEngFile.WriteLine("PointAndSync (" & FormatDateTime(Now,3) & "): Error Pointing... what happens if we ignore it?" & Err.Description)
  End If
  On Error Goto 0

  RADec = Utils.ConvertAzAltToRADec(Az, Alt)

  'Pre-Sync the scope to previous best fit values (accounts for drift in home position)
  objEngFile.WriteLine("PointAndSync (" & FormatDateTime(Now,3) & "): Pre-syncing")

  Set objFSO = CreateObject("Scripting.FileSystemObject") 
  Set adOffsetFile = objFSO.OpenTextFile("adOffset.txt", ForReading)
  RAOffset = adOffsetFile.Readline
  DecOffset = adOffsetFile.Readline
  adOffsetFile.Close
  objEngFile.WriteLine("PointAndSync (" & FormatDateTime(Now,3) & "): Read in previous offsets: " & raoffset & ", " & decoffset)


  Call TalkToLX200(":GR#", strRA, 2, 10)
  Call TalkToLX200(":GD#", strDec, 2, 10)
  SyncRA  = utils.ConvertStringToRA(strRA)   - RAOffset
  SyncDec = utils.ConvertStringToDec(strDec) - DecOffset
  Call objTel.Sync(SyncRA,SyncDec, "Last Sync")
  objEngFile.WriteLine("PointAndSync (" & FormatDateTime(Now,3) & "): Finished Pre-syncing")

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
      Call objTheSky.ImageLink(0.75, RADec(0), RADec(1))
      If Err.Number = 0 Then
        Call objTheSky.GetObjectRaDec("Image Link Information")
        CheckTel

        'TheSky6 Doesn't take into account the TPoint Model when syncing, must sync in telescope's raw coordinates
        Call TalkToLX200(":GR#", strRA, 2, 10)
        Call TalkToLX200(":GD#", strDec, 2, 10)
        SyncRA  = utils.ConvertStringToRA(strRA)   - (RADec(0) - objTheSky.dObjectRa) 
        SyncDec = utils.ConvertStringToDec(strDec) - (RADec(1) - objTheSky.dObjectDec)
        Call objTel.Sync(SyncRA,SyncDec, "Image Link's Sync")

        objEngFile.WriteLine("PointAndSync (" & Now & "): Completed Coordinate Solution in " & Round((Now - coorSolveStart)*86400) & " seconds")
        objEngFile.WriteLine("PointAndSync (" & Now & "): RA/Dec Attempted: " & RADec(0) & " " & RADec(1) & " RA/Dec Actual: " & objTheSky.dObjectRa & " " &  objTheSky.dObjectDec)
        objEngFile.WriteLine("PointAndSync (" & Now & "): Pointing off by " & (RADec(0) - objTheSky.dObjectRa)*900*cos(objTheSky.dObjectDec*Atn(1)/45) & "' in RA and " & (RADec(1) - objTheSky.dObjectDec)*60 & "' in Dec")

        objEngFile.WriteLine("PointAndSync (" & FormatDateTime(Now,3) & "): Writing offsets to adOffset.txt for next sync")
        Set adOffsetFile = objFSO.CreateTextFile("adOffset.txt") 
        adOffsetFile.WriteLine RAOffset + (RADec(0) - objTheSky.dObjectRa) 
        adOffsetFile.WriteLine DecOffset + (RADec(1) - objTheSky.dObjectDec)
        adOffsetFile.Close  

        Exit Sub
      Elseif Err.Number = 651 or Err.Number = 652 Then
        objEngFile.WriteLine("PointAndSync (" & Now & "): WARNING: not enough stars in the image; clouds?")
        Err.Clear
      Elseif Err.Number = 653 Then
        objEngFile.WriteLine("PointAndSync (" & Now & "): WARNING: could not find match; realigning on home")
        Err.Clear
        Align
        Call objTel.SlewToAzAlt(Az, Alt, "Pointing")
        Wscript.Sleep 120000
        RADec = Utils.ConvertAzAltToRADec(Az, Alt)
        NTaken = NTaken + 1    
      Else 
        objEngFile.WriteLine("PointAndSync (" & Now & "): WARNING: unanticipated error: " & Err.Number & " " & Err.Description & "; retrying sync")
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
    Align
    PointAndSync
  End If


End Sub