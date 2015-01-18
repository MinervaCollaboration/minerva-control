Function DisconnectAll

  On Error Resume Next

  'Disconnect to the Camera
  objEngFile.WriteLine("DisconnectAll (" & FormatDateTime(Now,3) & "): Disconnecting from the camera")
  objCam.Disconnect()

  If UseGuider Then
    objEngFile.WriteLine("DisconnectAll (" & FormatDateTime(Now,3) & "): Disconnecting from the guider")
    objCam.AutoGuider = 1
    objCam.Disconnect()
    objCam.AutoGuider = 0
  End If

  objEngFile.WriteLine("DisconnectAll (" & FormatDateTime(Now,3) & "): Closing CCDSoft")
  objCCDSoft.Quit(1)

  'Disconnect from the Telescope
  objEngFile.WriteLine("DisconnectAll (" & FormatDateTime(Now,3) & "): Disconnecting from the telescope")
  objTel.Disconnect
  objTheSky.DisconnectTelescope
  objEngFile.WriteLine("DisconnectAll (" & FormatDateTime(Now,3) & "): Closing TheSky6")
  objTheSky.Disconnect
  objTheSky6.Quit(1)

  WScript.Sleep 1000
  'Kill all remaining processes
  strComputer = "."
  Set objWMIService = GetObject("winmgmts:" _
      & "{impersonationLevel=impersonate}!\\" & strComputer & "\root\cimv2")
  Set colProcessList = objWMIService.ExecQuery _
      ("SELECT * FROM Win32_Process WHERE Name = 'CCDSoft.exe' or Name = 'TP.exe' or Name = 'TheSky6.exe' or Name = 'Orch.exe' or Name = 'my_imstat.exe'")
  For Each objProcess in colProcessList
      objProcess.Terminate()
  Next
  WScript.Sleep 1000

  On Error Goto 0

End Function