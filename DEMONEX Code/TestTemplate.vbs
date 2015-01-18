Const ForReading = 1
Const ForWriting = 2
Const ForAppending = 8

dim objCam, objTel, objTheSky

dim NotAligned, RAOffset, DECOffset  
NotEmailed = True
NotEmailedDaemon = True
NotEmailedRainWise = True
NotEmailedOmega = True
NotEmailedDPM = True


RoofMovingTime = 0
Centered = False
UseGuider = False

BadPoint = 0

dim NTaken

TLastFocus = Now

'Contacts
PIEmail = "gaudi@astronomy.ohio-state.edu"
CuratorEmail = "winer.obs@gmail.com,pat.trueblood@gmail.com,mtrueblood@noao.edu"
StudentEmail = "jdeast@astronomy.ohio-state.edu"
EmergencyTxt = "6178403045@txt.att.net"
Set ObjWS = WScript.CreateObject("WScript.Shell")

'Include functions
Set objFSO = CreateObject("Scripting.fileSystemObject")
Set objFile = objFSO.OpenTextFile("CenterObject.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("Centroid.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("CheckCam.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("CheckTel.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("CheckTime.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("ConnectAll.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("DisconnectAll.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("DiskCheck.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("DoBias.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("DoDark.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("DoObject.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("DoSkyFlat.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("Email.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("EndNight.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("FindGuideStar.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("Focus.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("GetIndex.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("GetWeather.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("HomeScope.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("imstat.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("jd.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("LX200Cancel.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("MyCamera_CameraEvent.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("PowerControl.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("PrepNight.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("RebootScope.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("Reverse.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("RoofOpen.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("ScopeOff.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("ScopeOn.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("SetCamTemp.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("SlewScope.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("SolveField.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("SunAlt.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("SyncScope.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("SyncTime.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("TalkToDevice.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("TalkToLX200.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("WriteLog.vbs", ForReading)
Execute objFile.ReadAll()


night = "YYYYMMDD"
datadir = "C:\demonex\data\n" & night & "\"
'Open log and engineering files
strLogFile = logdir & "n" & night & ".log"
strEngFile = logdir & "n" & night & ".eng"
Set objLogFile = objFSO.OpenTextFile(strLogFile, ForAppending)
Set objEngFile = objFSO.OpenTextFile(strEngFile, ForAppending)

  DisconnectAll
  ScopeOff
  Wscript.Sleep 30000
  ScopeOn
  CheckTel
  CheckCam
  CheckTime

DisconnectAll
WScript.Sleep 5000
ScopeOff
If False Then

ObjName = "SkyFlat"

      Alt = 75 'degrees (somewhat site dependent)
      Az = SunAz + 180 'degrees
      If Az > 360 Then Az = Az - 360
      CheckTel
      CheckTime
      objEngFile.WriteLine("SkyFlat (" & FormatDateTime(Now,3) & "): Slewing Telescope to Az=" &_
        Az & " Alt=" & Alt)
      Call objTel.SlewToAzAlt(Az, Alt, objName)
      WScript.Sleep 10000 'Wait for telescope to settle
End If
MsgBox("Done!")