Sub Align

  'Get date/time from Computer
  objEngFile.WriteLine("Align (" & FormatDateTime(Now,3) & "): Syncing Date/Time from Computer")
  SyncTime

  'Align on Home
  objEngFile.WriteLine("Align (" & FormatDateTime(Now,3) & "): Aligning on home")
  Call TalkToLX200(":hF#", Rx, 0, 0)
  
  WScript.Sleep 120000

End Sub