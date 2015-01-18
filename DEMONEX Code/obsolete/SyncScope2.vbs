Sub SyncScope

  MaxTries = 3
  MaxSunAlt = -4
  'calculate the current JD
  jdNow = jd(Year(Now),Month(Now),Day(Now),Hour(Now),Minute(Now),Second(Now))

  Set Utils = CreateObject("TheSky6.Utils")

  'change to R filter (better for mapping solution)
  objEngFile.WriteLine("SyncScope (" & FormatDateTime(Now,3) & "): Changing filter from " &_
    objCam.szFilterName(objCam.FilterIndexZeroBased) & " to " & objCam.szFilterName(2))
  objCam.FilterIndexZeroBased = 2

  objCam.ExposureTime = 15
  objCam.Frame = 1 'Light

  NTaken = 0

  Do While (NTaken < MaxTries and SunAlt < MaxSunAlt and jdNow < jdEnd)  
    If RoofOpen Then

      objEngFile.WriteLine("SyncScope (" & FormatDateTime(Now,3) & "): Roof open; beginning attempt " &_
        Ntaken + 1 & " of " & MaxTries) 

      objEngFile.WriteLine("SyncScope (" & FormatDateTime(Now,3) & "): Making sure tracking is on")
      Call objTel.SetTracking(1, 1, 1, 1)

      objCam.TakeImage

      'Solve the coordinates of the image
      coorSolveStart = Now
      objEngFile.WriteLine("SyncScope (" & Now & "): Beginning Coordinate Solution")

      Err.Clear
      On Error Resume Next
      Set Image = CreateObject("CCDSoft.Image")

      Image.AttachToActive'Imager
      Call SolveField(Image.Path, RACenter, DecCenter)
      
      If RACenter <> "FAIL" Then      

        RADecActNow = Utils.Precess2000ToNow(RACenter,DecCenter)

        StrADAct = Utils.ConvertEquatorialToString(RADecActNow(0),RADecActNow(1),4)
        a = split(StrADAct)
        strRAAct = a(1) & a(2) & a(3)
        strDecAct = a(6)

        CheckTel
        'TheSky6 Doesn't take into account the TPoint Model when syncing, must sync in telescope's raw (current epoch) coordinates
        Call TalkToLX200(":GR#", strRA, 2, 10)
        Call TalkToLX200(":GD#", strDec, 2, 10)
        RawRA  = utils.ConvertStringToRA(strRA)
        RawDec = utils.ConvertStringToDec(strDec)
        SyncRA  = RawRA + (adNow(0) - RADecActNow(0))
        SyncDec = RawDec + (adNow(1) - RADecActNow(1))

        Call TalkToLX200(":GA#", strAltOld, 2, 10)
        Call TalkToLX200(":GZ#", strAzOld, 2, 10)

        Call objTel.GetRaDec()
        StrSkyADOld = Utils.ConvertEquatorialToString(objTel.dra,objTel.dDec,4)
        a = split(strSkyADOld)
        strSkyRAOld = a(1) & a(2) & a(3)
        strSkyDecOld = a(6)

        Call objTel.GetAzAlt()
        StrSkyAzAltOld = Utils.ConvertHorizonToString(objTel.dAz,objTel.dAlt,4)
        a = Split(strSkyAzAltOld)
        strSkyAzOld = a(1)
        strSkyAltOld = a(4)

        'Sync TheSky6
        Call objTel.Sync(SyncRA,SyncDec, "Image Link's Solution")

        RAOffset  = (RA - RACenter)*900*cos(Dec*Atn(1)/45) 
        DecOffset = (Dec - DecCenter)*60

WScript.Sleep 3000
'check syncing
        Call TalkToLX200(":GR#", strRANew, 2, 10)
        Call TalkToLX200(":GD#", strDecNew, 2, 10)

        Call TalkToLX200(":GA#", strAltNew, 2, 10)
        Call TalkToLX200(":GZ#", strAzNew, 2, 10)

        Call objTel.GetRaDec()
        StrSkyADNew = Utils.ConvertEquatorialToString(objTel.dra,objTel.dDec,4)
        a = split(strSkyADNew)
        strSkyRANew = a(1) & a(2) & a(3)
        strSkyDecNew = a(6)

        Call objTel.GetAzAlt()
        StrSkyAzAltNew = Utils.ConvertHorizonToString(objTel.dAz,objTel.dAlt,4)  
        a = Split(strSkyAzAltNew)
        strSkyAzNew = a(1)
        strSkyAltNew = a(4)

        objEngFile.WriteLine("SyncScope (" & Now & "): Old Telescope RA = " & strRA    & " Old Telescope Dec = " & strDec)
        objEngFile.WriteLine("SyncScope (" & Now & "): New Telescope RA = " & strRANew & " New Telescope Dec = " & StrDecNew)
        objEngFile.WriteLine("SyncScope (" & Now & "):        Actual RA = " & strRAAct &   "      Actual Dec = " & strDecAct)

        objEngFile.WriteLine("SyncScope (" & Now & "): Old TheSky6 RA = " & strSkyRAOld & " Old TheSky6 Dec = " & strSkyDecOld)
        objEngFile.WriteLine("SyncScope (" & Now & "): New TheSky6 RA = " & strSkyRANew & " New TheSky6 Dec = " & strSkyDecNew)
        objEngFile.WriteLine("SyncScope (" & Now & "):      Actual RA = " & strRAAct    & "      Actual Dec = " & strDecAct)

        objEngFile.WriteLine("SyncScope (" & Now & "): Old Telescope Altitude = " & strAltOld & " Old Telescope Azimuth = " & strAzOld)
        objEngFile.WriteLine("SyncScope (" & Now & "): New Telescope Altitude = " & strAltNew & " New Telescope Azimuth = " & strAzNew)

        objEngFile.WriteLine("SyncScope (" & Now & "): Old TheSky6 Altitude = " & strSkyAltOld & " Old TheSky6 Azimuth = " & strSkyAzOld)
        objEngFile.WriteLine("SyncScope (" & Now & "): New TheSky6 Altitude = " & strSkyAltNew & " New TheSky6 Azimuth = " & strSkyAzNew)

        objEngFile.WriteLine("SyncScope (" & Now & "): Sync RA = " & SyncRA & " Sync Dec = " & SyncDec)
        objEngFile.WriteLine("SyncScope (" & Now & "): Actual RA = " & RACenter & " Actual Dec = " & DecCenter)
        objEngFile.WriteLine("SyncScope (" & Now & "): Desired RA = " & RA & " Desired Dec = " & Dec)

        objEngFile.WriteLine("SyncScope (" & Now & "): Completed Coordinate Solution in " & Round((Now - coorSolveStart)*86400) & " seconds")
        objEngFile.WriteLine("SyncScope (" & Now & "): RA/Dec Actual: " & RACenter & " " & DecCenter & " RA/Dec Attempted: " & RA & " " &  Dec)
        objEngFile.WriteLine("SyncScope (" & Now & "): Pointing off by " & RAOffset & "' in RA and " & DecOffset & "' in Dec") 


        strBody = strBody & vbCrLf & "Pointing off by " & Round(RAOffset,2) & "' in RA and " & Round(DecOffset,2) & "' in Dec" & vbCrLf

        NotAligned = False
        BadPoint = 0

        Exit Sub
      Else 

        Call TalkToLX200(":GR#", strRANew, 2, 10)
        Call TalkToLX200(":GD#", strDecNew, 2, 10)

        Call TalkToLX200(":GA#", strAltNew, 2, 10)
        Call TalkToLX200(":GZ#", strAzNew, 2, 10)

        Call objTel.GetRaDec()
        strSkyADNew = Utils.ConvertEquatorialToString(objTel.dra,objTel.dDec,4)
        a = split(strSkyADNew)
        strSkyRANew = a(1) & a(2) & a(3)
        strSkyDecNew = a(6)

        Call objTel.GetAzAlt()
        strSkyAzAltNew = Utils.ConvertHorizonToString(objTel.dAz,objTel.dAlt,4)  
        a = Split(strSkyAzAltNew)
        strSkyAzNew = a(1)
        strSkyAltNew = a(4)

        objEngFile.WriteLine("SyncScope (" & Now & "): Error: " & Err.Number & " " & Err.Description & "; retrying sync")
        objEngFile.WriteLine("SyncScope (" & Now & "): Telescope RA = " & strRANew    & " Telescope Dec = " & StrDecNew)
        objEngFile.WriteLine("SyncScope (" & Now & "):   TheSky6 RA = " & strSkyRANew & "   TheSky6 Dec = " & strSkyDecNew)
        objEngFile.WriteLine("SyncScope (" & Now & "): Telescope Altitude = " & strAltNew    & " Telescope Azimuth = " & strAzNew)
        objEngFile.WriteLine("SyncScope (" & Now & "):   TheSky6 Altitude = " & strSkyAltNew & "   TheSky6 Azimuth = " & strSkyAzNew)

        Err.Clear
        NTaken = NTaken + 1
        RAOffset = -99
        DecOffset = -99
      End If
      On Error Goto 0

    Else
      objEngFile.WriteLine("SyncScope (" & FormatDateTime(Now,3) & "): Roof Closed; retry in 5 minutes")
      'Turn Tracking off (just in case)
      objEngFile.WriteLine("SyncScope (" & FormatDateTime(Now,3) & "): Making sure tracking is off")
      Call objTel.SetTracking(0, 0, 0, 0)
      WScript.Sleep 300000  
    End If

    'calculate the current JD
    jdNow = jd(Year(Now),Month(Now),Day(Now),Hour(Now),Minute(Now),Second(Now))

  Loop

  If SunAlt > MaxSunAlt or jdNow > jdEnd Then
    objEngFile.WriteLine("SyncScope (" & FormatDateTime(Now,3) & "): Object Set, aborting pointing; JD=" & jdNow & " Sun=" & SunAlt)  
    BadPoint = 3
  End If


  If NTaken >= MaxTries Then 
    objEngFile.WriteLine("SyncScope (" & FormatDateTime(Now,3) & "): WARNING: Sync Failed")  
    BadPoint = BadPoint+1
  End If

End Sub