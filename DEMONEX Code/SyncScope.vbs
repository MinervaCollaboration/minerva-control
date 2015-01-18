Sub SyncScope

  MaxTries = 3
  Platescale = 0.754
  pi = 4*atn(1)

  'calculate the current JD
  jdNow = jd(Year(Now),Month(Now),Day(Now),Hour(Now),Minute(Now),Second(Now))

  objCam.ExposureTime = 15
  objCam.Frame = 1 'Light

  objEngFile.WriteLine("SyncScope (" & FormatDateTime(Now,3) & "): Making sure tracking is on")
  Call objTel.SetTracking(1, 1, 1, 1)

  objCam.AutoGuider=0
  objCam.TakeImage

  'Solve the coordinates of the image
  coorSolveStart = Now
  objEngFile.WriteLine("SyncScope (" & FormatDateTime(Now,3) & "): Beginning Coordinate Solution")


  Err.Clear
  On Error Resume Next

  Set Image = CreateObject("CCDSoft.Image")
  Image.AttachToActiveImager
  Image.Save
  Image.ScaleInArcsecondsPerPixel = Platescale 
  Image.InsertWCS True

  If Err.Number <> 0 Then
    'ImageLink failed, use astrometry.net
    objEngFile.WriteLine("SyncScope (" & FormatDateTime(Now,3) & "): ImageLink failed in " &_
      Round((Now - coorSolveStart)*86400,2) & " seconds, using astrometry.net")
    Call SolveField(Image.Path, RACenter, DecCenter, Orientation, ra, dec, CurrentX, CurrentY)
    Orientation = cDbl(Orientation)
    If Orientation > 180 Then Orientation = Orientation - 360
  Else
    'ImageLink succeeded, Find RA/dec at desired position of target
    RADec2000 = Image.XYToRaDec(TargetX,TargetY)
    RACenter = RADec2000(0)
    DecCenter = RADec2000(1)
    'ImageLink Fails and returns 0,0 sometimes
    If RACenter < 0.15 and DecCenter < 0.15 Then
      RACenter = "FAIL"
    End If

    XY = Image.RADecToXY(ra,dec)
    CurrentX = XY(0)
    CurrentY = XY(1)

    cd1_1 = Image.FITSKeyword("CD1_1")
    cd1_2 = Image.FITSKeyword("CD1_2")
    cd2_1 = Image.FITSKeyword("CD2_1")
    cd2_2 = Image.FITSKeyword("CD2_2")

    xscale = sqr(cd1_1^2 + cd1_2^2)
    yscale = sqr(cd2_1^2 + cd2_2^2)
    sintheta = cd2_1/yscale
    costheta = cd1_1/xscale

    orientation = -atn(sintheta/costheta)*180/pi
    If costheta < 0 then orientation = orientation + 180
    If orientation > 180 then orientation = orientation - 360

    'ImageLink's solution cannot be trusted if offset more than FOV, and is wrong if orientation isn't within 5 degrees of square.
    If (abs(orientation) > 5 and abs(abs(orientation) - 180) > 5) or (abs(racenter - ra)*cos(deccenter*pi/180)*15) > 1 or abs(deccenter - dec) > 1 Then
      'ImageLink failed, use astrometry.net
      objEngFile.WriteLine("SyncScope (" & FormatDateTime(Now,3) & "): Cannot trust ImageLink's solution, using astrometry.net")
      Call SolveField(Image.Path, RACenter, DecCenter, Orientation, ra, dec, CurrentX, CurrentY)
      Orientation = cDbl(Orientation)
      If Orientation > 180 Then Orientation = Orientation - 360
    End If

  End If
  On Error Goto 0

  If RACenter = "FAIL" then 
    objEngFile.WriteLine("SyncScope (" & FormatDateTime(Now,3) & "): Astrometry.net Failed; Clouds?") 
    RAoffset = 648000 '180 degrees, can't be real value
    DecOffset = 648000 '180 degrees, can't be real value
    Exit Sub
  Else 
    objEngFile.WriteLine("SyncScope (" & FormatDateTime(Now,3) & "): Coordinate solution completed in " &_
      Round((Now - coorSolveStart)*86400,2) & " seconds")
  
    If Orientation < 90 and Orientation > -90 Then
      MeridianAct = CBool(False)
    Else
      MeridianAct = CBool(True)
    End If

    If MeridianAct <> MeridianFlip Then
      objEngFile.WriteLine("SyncScope (" & FormatDateTime(Now,3) & "): WARNING: wrong side of meridian; orientation = " & Orientation & " Meridian Actual=" & MeridianAct & " Meridian Thought=" & MeridianFlip)
      MeridianFlip = MeridianAct
    End If 

    objEngFile.WriteLine("SyncScope (" & FormatDateTime(Now,3) & "): Precessing coordinates")
    RADecActNow = Utils.Precess2000ToNow(RACenter,DecCenter)
    If Err.Number <> 0 Then
      objEngFile.WriteLine("SyncScope (" & FormatDateTime(Now,3) & "): Error Precessing coordinates: " & Err.Description)
    End If

    objEngFile.WriteLine("SyncScope (" & FormatDateTime(Now,3) & "): Syncing the telescope")
    CheckTel

    'bad solution causes syncing error sometimes
    On Error Resume Next
    Call objTel.Sync(RADecActNow(0),RADecActNow(1), "Image Link's Solution")
    If Err.Number <> 0 Then
      objEngFile.WriteLine("SyncScope (" & FormatDateTime(Now,3) & "): Error Syncing the telescope, power cycling mount: " & Err.Description)
      DisconnectAll
      ScopeOff
      WScript.Sleep 30000
      ScopeOn
      ConnectAll    
    End If
    On Error Goto 0

    objEngFile.WriteLine("SyncScope (" & FormatDateTime(Now,3) & "): Object (ra=" & ra & ", dec=" & dec & ") at " & CurrentX & "," & CurrentY) 


    RAOffset  = (CurrentX - TargetX)*Platescale
    DecOffset = (CurrentY - TargetY)*Platescale


    objEngFile.WriteLine("SyncScope (" & FormatDateTime(Now,3) & "): Pointing off by " & RAOffset & """ in RA and " & DecOffset & """ in Dec; Orientation = " & Orientation & " Meridian = " & MeridianAct) 

    NotAligned = False
    BadPoint = 0

    Exit Sub
  End If 

End Sub