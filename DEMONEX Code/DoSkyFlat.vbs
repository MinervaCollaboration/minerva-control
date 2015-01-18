Sub DoSkyFlat(arrFilters, NImages)

on error resume next

Const Flat = 4

'Window in which to attempt skyFlats
const minSunAlt = -12
Const maxSunAlt = -3

'parameters
Dither = 3 'arcminutes
'chase the sun
If Hour(Now) > 12 Then 
  Direction = "Up"
Else 
  Direction = "Down"
End If
Direction = "West"

biasLevel = 2300
targetCounts = 20000 'includes bias level
saturation = 45000 'throw away image if mode is above saturation 
maxExpTime = 60   'Maximum Exposure time (stars imprint through)
minExpTime = 10   'Minimum Exposure time (shutter effects become significant)

objName = "SkyFlat"

'Wait for Twilight
Do While (SunAlt > maxSunAlt or SunAlt < minSunAlt)
  If Hour(Now) > 12 and SunAlt < minSunAlt then 
    objEngFile.WriteLine("SkyFlat (" & FormatDateTime(Now,3) & "): Warning: Sun setting and too low for flats, skipping flats")
    Exit Sub
  Elseif Hour(Now) < 12 and SunAlt > maxSunAlt then
    objEngFile.WriteLine("SkyFlat (" & FormatDateTime(Now,3) & "): Warning: Sun rising and too high for flats, skipping flats")
    Exit Sub
  End If
  objEngFile.WriteLine("SkyFlat (" & FormatDateTime(Now,3) & "): Sun at " & SunAlt & "; waiting")
  Wscript.Sleep 60000
  RoofOpen
Loop

'Do commands serially
objEngFile.WriteLine("SkyFlat (" & FormatDateTime(Now,3) & "): Doing commands serially")
CheckCam
objCam.Asynchronous = 0
objCam.AutoGuider = 0
CheckTel
objTel.Asynchronous = 0

objEngFile.WriteLine("SkyFlat (" & FormatDateTime(Now,3) & "): Setting IMAGETYP=Flat")
CheckCam
objCam.Frame = Flat

objEngFile.WriteLine("SkyFlat (" & FormatDateTime(Now,3) & "): Setting ExpTime=minExpTime")
ExpTime = minExpTime
CheckCam
objCam.ExposureTime = ExpTime

'Set tracking rate to sidereal
objEngFile.WriteLine("SkyFlat (" & FormatDateTime(Now,3) & "): Turn on sidereal tracking")
CheckTel
Call objTel.SetTracking(1, 1, 1, 1)

For Each objFilter in arrFilters

  Ntaken = 0

  'Change the filter
  CheckCam
  objEngFile.WriteLine("SkyFlat (" & FormatDateTime(Now,3) & "): Changing filter from " &_
    objCam.szFilterName(objCam.FilterIndexZeroBased) & " to " & objCam.szFilterName(objFilter))
  objCam.FilterIndexZeroBased = objFilter

  Do While (NTaken < NImages)  
    If RoofOpen Then
      objEngFile.WriteLine("SkyFlat (" & FormatDateTime(Now,3) & "): Roof open; beginning image " &_
        Ntaken + 1 & " of " & NImages)

      'Slew to the optimally Flat part of the sky
      'See Chromey & Hasselbacher, 1996
      'There is enough time between images (~1 min) that slewing to the same alt/az is like dithering.
      Alt = 75 'degrees (somewhat site dependent)
      Az = SunAz + 180 'degrees
      If Az > 360 Then Az = Az - 360
      CheckTel

'      If Not TimeSet Then 
        CheckTime
'        TimeSet = True
'      End If

      CheckPos
      objEngFile.WriteLine("SkyFlat (" & FormatDateTime(Now,3) & "): Slewing Telescope to Az=" & Az & " Alt=" & Alt)

      Call objTel.SlewToAzAlt(Az, Alt, objName)
      WScript.Sleep 10000 'Wait for telescope to settle
      CheckPos

Call objTel.GetAzAlt()
TheSky6Az  = objTel.dAz
TheSky6Alt = objTel.dAlt

Do While TheSky6Alt < 30 
  objEngFile.WriteLine("SkyFlat (" & FormatDateTime(Now,3) & "): Slewing Error; rebooting scope. Az = " & TheSky6Az & " Alt=" & TheSky6Alt)
  HomeScope
  DisconnectAll
  ScopeOff
  WScript.Sleep 30000
  ScopeOn
  ConnectAll
  CheckPos
  Call objTel.SlewToAzAlt(Az, Alt, objName)
  WScript.Sleep 10000 'Wait for telescope to settle
  CheckPos
  Call objTel.GetAzAlt()
  TheSky6Az  = objTel.dAz
  TheSky6Alt = objTel.dAlt
Loop

      strFileName = "n" & night & "." & objName & "." & GetIndex(objName) & ".fits"
      objEngFile.WriteLine("SkyFlat (" & FormatDateTime(Now,3) & "): Beginning Exposure")
      CheckCam
      objCam.AutoGuider=0
      objCam.TakeImage

      'Rename the image to something reasonable
      'filename of the image -- nYYYYMMDD.objName.####.fits
      strFileName = "n" & night & "." & objName & "." & GetIndex(objName) & ".fits"
      objEngFile.WriteLine("DoSkyFlat (" & FormatDateTime(Now,3) & "): Renaming file from " &_
        objCam.LastImageFileName & " to " & strFileName)
      objFSO.MoveFile datadir & objCam.LastImageFileName, datadir & strFileName      

      'Determine the mode of the image
      objEngFile.WriteLine("SkyFlat (" & FormatDateTime(Now,3) & "): Finding Mode")
      call imstat(datadir & strFilename, mean, median, mode, min, max, sum)      

      'If the mode is above the saturation limit or not significantly above the bias, 
      'delete image and don't write log
      If mode > Saturation Then
        objEngFile.WriteLine("SkyFlat (" & FormatDateTime(Now,3) & "): Flat Deleted (Mode=" & mode & "; Sun altitude="& SunAlt & "; exptime=" & objCam.ExposureTime & "; filter=" & objCam.szFilterName(objFilter) & ")")
        objFSO.DeleteFile datadir & strFilename
        If hour(now) < 12 and objCam.ExposureTime = MinExpTime Then 
          objEngFile.WriteLine("SkyFlat (" & FormatDateTime(Now,3) & "): Saturated and sun rising, next filter")
          Exit Do
        End If
      Elseif mode < 3*biasLevel Then
        objEngFile.WriteLine("SkyFlat (" & FormatDateTime(Now,3) & "): Flat Deleted (Mode=" & mode & "; Sun altitude="& SunAlt & "; exptime=" & objCam.ExposureTime & "; filter=" & objCam.szFilterName(objFilter) & ")")
        objFSO.DeleteFile datadir & strFilename
        If hour(now) > 12 and objCam.ExposureTime = MaxExpTime Then
          objEngFile.WriteLine("SkyFlat (" & FormatDateTime(Now,3) & "): Counts too low and sun setting, next filter")
          Exit Do
        End If
      Else
        objEngFile.WriteLine("SkyFlat (" & FormatDateTime(Now,3) & "): Writing Log (Mode=" & mode & "; Sun altitude="& SunAlt & "; exptime=" & objCam.ExposureTime & "; filter=" & objCam.szFilterName(objFilter) & ")")
        Call WriteLog
        Ntaken = Ntaken + 1
      End If

      'Scale exposure time to get a mode of "targetCounts" counts in next image
      'Assumes sky not changing brightness - overestimate at sunrise, underestimate at sunset
      If (mode - biaslevel) <= 0 Then 
        Exptime = maxExpTime
      Else 
        Exptime = ExpTime*(targetcounts-biasLevel)/(mode - biasLevel)
      End If

      If Exptime < minExpTime Then
        'If exposure time is too short, use the minimum exposure time
        objEngFile.WriteLine("SkyFlat (" & FormatDateTime(Now,3) & "): New exposure time below minumum; setting to minimum")
        ExpTime = minExpTime
      Elseif Exptime > MaxExpTime Then 
        'If the exposure time is too long, use the maximum exposure time
        objEngFile.WriteLine("SkyFlat (" & FormatDateTime(Now,3) & "): New exposure time above maximum; setting to maximum")
        ExpTime = maxExpTime
      End If

      CheckCam
      objEngFile.WriteLine("SkyFlat (" & FormatDateTime(Now,3) & "): Scaling exposure time from " &_	
        objCam.Exposuretime & " to " & ExpTime)
      objCam.Exposuretime = ExpTime

    Else 
      'wait 5 minutes if roof closed
      objEngFile.WriteLine("SkyFlat (" & FormatDateTime(Now,3) & "): Waiting 5 minutes")
      WScript.Sleep 300000
    End If

    If SunAlt > maxSunAlt or SunAlt < minSunAlt Then
      objEngFile.WriteLine("SkyFlat (" & FormatDateTime(Now,3) & "): The Sun's altitude (" & SunAlt & ") does not allow additional sky flats")
      strBody = strBody & "Sky Flats (" & objCam.szFilterName(objFilter) & "): " & NTaken & vbCrLf & vbCrLf
      Exit For
    End If

  Loop

  strBody = strBody & "Sky Flats (" & objCam.szFilterName(objFilter) & "): " & NTaken & vbCrLf

Next

objEngFile.WriteLine("SkyFlat (" & FormatDateTime(Now,3) & "): Sky flats finished")
objEngFile.WriteLine("SkyFlat (" & FormatDateTime(Now,3) & "): Turn off tracking")
Call objTel.SetTracking(0, 0, 0, 0)

End Sub

Function SunAz

  Set Chart = CreateObject("TheSky6.StarChart")
  Set ObjInfo = Chart.Find("Sun")
  AzPropNo = 58 'as defined by TheSky6
  SunAz = objInfo.property(AzPropNo)

End Function
