Const ForReading = 1
Const ForWriting = 2
Const ForAppending = 8

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

'Global Variables
dim objCam, objTel, objTheSky, objCCDSoft, objTheSky6, Utils

'Camera Event variables
dim AcquireObject, Calibrate, MeridianFlip, strFileName, adNow, AcquireGuideStar, RestartGuider
GuideBoxSize = 32

'position to move the stars to in the stamp 
'start at center, changes according to analysis of science images
ToX = GuideboxSize/2
ToY = GuideboxSize/2

TargetX = 1024 'X pixel to place the object
TargetY = 1024 'Y pixel to place the object

Const SunAltRoofClosed = 5

dim NotAligned, RAOffset, DECOffset  
NotEmailed = True
NotEmailedDaemon = True
NotEmailedRainWise = True
NotEmailedOmega = True
NotEmailedDPM = True
RoofMovingTime = 0
Centered = False
UseGuider = False
'UseGuider = True
TimeSet = False

BadPoint = 0
nHomeFail = 0

dim NTaken

TLastFocus = Now

'Contacts
PIEmail = "gaudi@astronomy.ohio-state.edu"
CuratorEmail = "winer.obs@gmail.com,pat.trueblood@gmail.com,mtrueblood@noao.edu"
StudentEmail = "jdeast@astronomy.ohio-state.edu"
EmergencyTxt = "6178403045@txt.att.net"

Set ObjWS = WScript.CreateObject("WScript.Shell")
BadGuideCounter = 0

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
Set objFile = objFSO.OpenTextFile("CheckPos.vbs", ForReading)
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

'If started between midnight and noon, use the yesterday's date
If Hour(Now) < 12 Then
  night = Right(string(4,"0") & Year(Now-1), 4) &_
  Right(string(2,"0") & Month(Now-1), 2) &_
  Right(string(2,"0") & Day(Now-1), 2)
Else 
  night = Right(string(4,"0") & Year(Now), 4) &_
    Right(string(2,"0") & Month(Now), 2) &_
    Right(string(2,"0") & Day(Now), 2)
End If

'Set up and check the directories
'DataDrive must be shared for Astrometry.net to succeed!
DataDrive = "E"
BackupDrive = "H"
'DiskCheck
tgtdir  = "C:\demonex\targets\"
datadir = DataDrive & ":\demonex\data\n" & night & "\"
logdir  = "C:\demonex\logs\"
tgtdir  = "C:\demonex\targets\"

PrepNight(night)

'Open log and engineering files
strLogFile = logdir & "n" & night & ".log"
strEngFile = logdir & "n" & night & ".eng"
Set objLogFile = objFSO.OpenTextFile(strLogFile, ForAppending)
Set objEngFile = objFSO.OpenTextFile(strEngFile, ForAppending)

  DisconnectAll
WScript.Sleep 3000
ConnectAll
WScript.Sleep 3000
  CheckTel
  CheckCam
  CheckTime

  objTel.Disconnect() 
  objTheSky.DisconnectTelescope()


exptime = 15
objCam.ExposureTime = ExpTime
objCam.Frame = 1'Light
TargetX = 1024
TargetY = 1024


filename = "E:\demonex\data\n20110504\n20110504.KELT-03667.P.0001.fits"
raobject = 12.429321 
decobject = 27.480165 

'Solve Asynchronously
cmd = "asyncastrom.bat " & filename & " " & raobject*15 & " " & decobject 
Set ObjWS = WScript.CreateObject("WScript.Shell")
dummy = ObjWS.Run(cmd,1,0)

objCam.TakeImage 

cmd = "asyncastrom.bat " & filename & " " & raobject*15 & " " & decobject 
Set ObjWS = WScript.CreateObject("WScript.Shell")
dummy = ObjWS.Run(cmd,1,0)

'wait for exposure to complete
Do While (Not CBool(objCam.IsExposureComplete))
  CheckCam
Loop

objCam.TakeImage  


MsgBox("Done!")