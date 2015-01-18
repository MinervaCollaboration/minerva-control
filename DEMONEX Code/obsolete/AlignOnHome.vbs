Sub AlignOnHome

  'Align on Home
  objEngFile.WriteLine("DoNight (" & FormatDateTime(Now,3) & "): Aligning Scope on Home Position")
  SyncTime
  Call TalkToLX200(":ES6052#",Rx,0,1)

  'Wait until home found
  Call TalkToLX200(":h?#",Rx,1,1)
  Do Until Rx = "1"
    WScript.Sleep 1000
    Call TalkToLX200(":h?#",Rx,1,1)
    If Rx = "0" then 
      'home failed, rehome
       SyncTime
       Call TalkToLX200(":ES6052#",Rx2,0,1)
    End If
    objEngFile.WriteLine("DoNight (" & FormatDateTime(Now,3) & "): Homing status:" & Rx)
  Loop
  'WScript.Sleep 15000
  objEngFile.WriteLine("DoNight (" & FormatDateTime(Now,3) & "): Done Aligning")

End Sub