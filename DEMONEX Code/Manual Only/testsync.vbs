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

'On Error Resume Next

'Global Variables
dim objCam, objTel, objTheSky

'Camera Event variables
dim AcquireObject, Calibrate, MeridianFlip, strFileName, adNow, AcquireGuideStar, RestartGuider, GuideBoxSize

Const SunAltRoofClosed = 5

dim NotAligned  
NotEmailed = True

BadPoint = 0

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
Set objFile = objFSO.OpenTextFile("Align.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("Autoguide.vbs", ForReading)
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
Set objFile = objFSO.OpenTextFile("PointAndSync.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("PowerCycle.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("PrepNight.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("QuitGuiding.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("RebootScope.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("RoofOpen.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("ScopeOff.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("ScopeOn.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("SetCamTemp.vbs", ForReading)
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




'datadir = "D:\demonex\data\n20090309\"
strfilename= "test"
objName = "test"

night = "20090526"

'Set up and check the directories
DataDrive = "D"
BackupDrive = "J"
'DiskCheck
tgtdir  = "C:\demonex\targets\"
datadir = DataDrive & ":\demonex\data\n" & night & "\"
logdir  = "C:\demonex\logs\"
tgtdir  = "C:\demonex\targets\"

'Open log and engineering files
strLogFile = logdir & "n" & night & ".log"
strEngFile = logdir & "n" & night & ".eng"
strTargetList = tgtdir & "n" & night & ".tgt"
Set objLogFile = objFSO.OpenTextFile(strLogFile, ForAppending)
Set objEngFile = objFSO.OpenTextFile(strEngFile, ForAppending)

connectall
Set Utils = CreateObject("TheSky6.Utils")

Call objTel.GetRaDec()
StrSkyADOld = Utils.ConvertEquatorialToString(objTel.dra,objTel.dDec,4)
a = split(strSkyADOld)
strSkyRAOld = a(1) & a(2) & a(3)
strSkyDecOld = a(6)

Call objTel.GetRaDec()
ra = objTel.dRa
dec = objTel.dDec
'MsgBox(ra & " " & dec)

actra = ra + 0.1
actdec = dec - 0.2

StrADAct = Utils.ConvertEquatorialToString(actra,actdec,4)
a = split(StrADAct)
strRAAct = a(1) & a(2) & a(3)
strDecAct = a(6)

strRA = "Communication Error: TimeOut"
Do While strRA = "Communication Error: TimeOut"
  Call TalkToLX200(":GR#", strRA, 2, 10)
  WScript.Sleep 300
Loop

strDec = "Communication Error: TimeOut"
Do While strDec = "Communication Error: TimeOut"
  Call TalkToLX200(":GD#", strDec, 2, 10)
  WScript.Sleep 300
Loop

'MsgBox(strra)
'MsgBox(strdec)



RawRA  = utils.ConvertStringToRA(strRA)
RawDec = utils.ConvertStringToDec(strDec)
SyncRA  = RawRA + (ra - actra)*Cos(ra)
SyncDec = RawDec + (dec - actdec)

'MsgBox(ra & " " & dec)
'MsgBox(actra & " " & actdec)
'MsgBox(rawra & " " & rawdec)
'MsgBox(syncra & " " & syncdec)

'Sync TheSky6
Call objTel.Sync(SyncRA,SyncDec, "Image Link's Solution")

WScript.Sleep 5000

Call objTel.GetRaDec()
StrSkyADNew = Utils.ConvertEquatorialToString(objTel.dra,objTel.dDec,4)
a = split(strSkyADNew)
strSkyRANew = a(1) & a(2) & a(3)
strSkyDecNew = a(6)

strRANew = "Communication Error: TimeOut"
Do While strRANew = "Communication Error: TimeOut"
  Call TalkToLX200(":GR#", strRANew, 2, 10)
  WScript.Sleep 300
Loop

strDecNew = "Communication Error: TimeOut"
Do While strDecNew = "Communication Error: TimeOut"
  Call TalkToLX200(":GD#", strDecNew, 2, 10)
  WScript.Sleep 300
Loop

msgbox(" Old Telescope RA = " & strRA & " Old Telescope Dec = " & strDec & VBCrLf &_
       "New Telescope RA = " & strRANew & " New Telescope Dec = " & strDecNew & VBCrLf &_
       "         Actual RA = " & strRAAct    & "      Actual Dec = " & strDecAct)

msgbox(" Old TheSky6 RA = " & strSkyRAOld & " Old TheSky6 Dec = " & strSkyDecOld & VBCrLf &_
       "New TheSky6 RA = " & strSkyRANew & " New TheSky6 Dec = " & strSkyDecNew & VBCrLf &_
       "         Actual RA = " & strRAAct    & "      Actual Dec = " & strDecAct)





