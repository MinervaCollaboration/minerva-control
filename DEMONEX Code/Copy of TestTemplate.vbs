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

filename = "E:\DEMONEX\DATA\N20110411\TmpPrefix.00080755.11h46m14.3s_01d41m32sN.FIT"
raobject = 11.769503
decobject = 1.6875361

  solveStart = Now
  'SSH into the linux machine and solve the field with Astrometry.net's software
  Set ObjWS = WScript.CreateObject("WScript.Shell")
  cmd = "astrometry.bat " & filename & " " & raobject*15 & " " & decobject  
  objEngFile.WriteLine("SolveField (" & FormatDateTime(Now,3) & "): Running command: " & cmd)

  'Run the program and capture output  
  Set oiExec   = objWS.Exec(cmd)
  Set oiStdOut = oiExec.StdOut
  Do While (Not oiStdOut.AtEndOfStream)
    sLine = oiStdOut.ReadLine
    output = Split(sLine)
  Loop

  RACenter = output(0)
  DecCenter = output(1)
  Orientation = output(2)
  xobject = output(3)
  yobject = output(4)


msgbox(orientation)
  Orientation = cdbl(Orientation)
msgbox(vartype(orientation))
  If Orientation > 180 Then Orientation = Orientation - 360
msgbox(orientation > -90)
msgbox(orientation < 90)

  If Orientation < 90 and Orientation > -90 Then
    MeridianAct = CBool(False)
  Else
    MeridianAct = CBool(True)
  End If
msgbox(orientation)
msgbox(meridianAct)

msgbox(sLine)

msgbox("done!")