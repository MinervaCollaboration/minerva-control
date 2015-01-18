Sub RebootScope

  'Disconnect from the Telescope
  objEngFile.WriteLine("RebootScope (" & FormatDateTime(Now,3) & "): Disconnecting from everything")
  DisconnectAll

  'Power Cycle the Mount
  objEngFile.WriteLine("RebootScope (" & FormatDateTime(Now,3) & "): Power Cycling the mount")
  Set ObjWS = WScript.CreateObject("WScript.Shell")
  ObjWS.Run "poweroff.bat"
  WScript.Sleep 10000
  ObjWS.Run "poweron.bat"

  'Wait for Telescope Initialization
  objEngFile.WriteLine("RebootScope (" & FormatDateTime(Now,3) & "): Waiting for Initialization")
  Wscript.Sleep 25000

  LX200Cancel
  WScript.Sleep 30000

  objEngFile.WriteLine("RebootScope (" & FormatDateTime(Now,3) & "): Canceling back to main menu")
  for i=0 to 5
    LX200Cancel
    WScript.Sleep 1000
  Next

  'Reconnect to the Telescope
  objEngFile.WriteLine("RebootScope (" & FormatDateTime(Now,3) & "): Reconnecting to everything")
  ConnectAll

End Sub