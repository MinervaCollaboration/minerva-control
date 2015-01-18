Const ForReading = 1
Const ForWriting = 2
Const ForAppending = 8

Set objFSO = CreateObject("Scripting.fileSystemObject")
Set objFile = objFSO.OpenTextFile("PowerControl.vbs", ForReading)
Execute objFile.ReadAll()

MsgBox("ScopeOff (" & FormatDateTime(Now,3) & "): Turning off the Scope")
Status = PowerControl("Mount",False)
MsgBox(Status)
