Sub SyncTime2

If RoofOpen Then

  objEngFile.WriteLine("SyncTime2 (" & FormatDateTime(Now,3) & "): Setting time via GPS")
  Call TalkToLX200(":gT#", Rx)

  If Rx = "0" Then 
    objEngFile.WriteLine("SyncTime2 (" & FormatDateTime(Now,3) & "): GPS Timeout. Roof closed?")
  Else 
    objEngFile.WriteLine("SyncTime2 (" & FormatDateTime(Now,3) & "): Done setting time via GPS")
  End If

Else 
  objEngFile.WriteLine("SyncTime2 (" & FormatDateTime(Now,3) & "): Roof closed; cannot use GPS.")
End If

End SUb