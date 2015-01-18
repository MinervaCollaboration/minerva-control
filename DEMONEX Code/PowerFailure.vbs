'On Error Resume Next

Set objFSO = CreateObject("Scripting.fileSystemObject")

Set objFile = objFSO.OpenTextFile("CheckCam.vbs", 1)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("CheckTel.vbs", 1)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("CheckTime.vbs", 1)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("ConnectAll.vbs", 1)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("DisconnectAll.vbs", 1)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("Email.vbs", 1)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("HomeScope.vbs", 1)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("PowerControl.vbs", 1)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("TalkToDevice.vbs", 1)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("ScopeOff.vbs", 1)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("ScopeOn.vbs", 1)
Execute objFile.ReadAll()

'Kill Processes
strComputer = "."
Set objWMIService = GetObject("winmgmts:" _
    & "{impersonationLevel=impersonate}!\\" & strComputer & "\root\cimv2")
Set colProcessList = objWMIService.ExecQuery _
    ("SELECT * FROM Win32_Process WHERE Name = 'CCDSoft.exe' or Name = 'TP.exe' or Name = 'TheSky6.exe' or Name = 'Orch.exe' or Name = 'my_imstat.exe'")
For Each objProcess in colProcessList  
    objProcess.Terminate()
Next
WScript.Sleep 1000
  
Dim objCam, objTel, objTheSky

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

logdir = "C:\demonex\logs\"
strEngFile = logdir & "n" & night & ".eng"

'Create the engineering file (don't overwrite)
If objFSO.FileExists(strEngFile) Then
   Set objFolder = objFSO.GetFolder(logdir)
Else
   Set objFile = objFSO.CreateTextFile(strEngFile)
   objFile.Close
End If

Set objEngFile = objFSO.OpenTextFile(strEngFile, 8)

objEngFile.WriteLine("PowerFailure (" & FormatDateTime(Now,3) & "): Error: Power Failure, beginning graceful shutdown...")

ConnectAll
CheckTel
CheckCam
HomeScope
DisconnectAll
ScopeOff

'Turn off everything to extend battery life for KELT
Call PowerControl("Camera",False)
Call PowerControl("Guider",False)

'Send email of power failure
strTo = "jdeast@astronomy.ohio-state.edu"
strSubject = "DEMONEX Power Failure n" & night
strBody = "DEMONEX Suffered a power failure and gracefully shut down"
Call Email(strTo,strSubject,strBody,"","","")

'Shut down computer
set objShell = CreateObject("WScript.Shell") 
objShell.Run "shutdown -s -t 0 -f"