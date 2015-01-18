Const ForReading = 1

Set objTel = WScript.CreateObject("TheSky6.RASCOMTele")
objTel.Connect()

'Include functions
Set objFSO = CreateObject("Scripting.fileSystemObject")
Set objFile = objFSO.OpenTextFile("../TalkToLX200.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("../TalkToDevice.vbs", ForReading)
Execute objFile.ReadAll()


Call TalkToDevice(":hF#", Rx, 0, 5)
WScript.Sleep 1000

Call TalkToDevice(":h?#", Rx, 1, 5)
WScript.Sleep 1000
HomeStart = Now

MsgBox("HomeScope (" & FormatDateTime(Now,3) & "): Homing Status = " & Rx)

  Do While Rx <> "1"
    Call TalkToDevice(":h?#", Rx, 1, 5)
    WScript.Sleep 1000

    MsgBox("HomeScope (" & FormatDateTime(Now,3) & "): Homing Status = " & Rx)

    If Rx = "0" or (Now - Homestart) > 300.0/86400.0 Then

      MsgBox("HomeScope (" & FormatDateTime(Now,3) & "): Error: Homing Failed! Entering safe mode to prevent cable wrapping")
      Rx = "1"

    End If

  Loop

MsgBox("Home!")