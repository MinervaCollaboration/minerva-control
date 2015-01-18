Sub CheckTime

objEngFile.WriteLine("CheckTime (" & FormatDateTime(Now,3) & "): Getting Telscope Date") 
Call TalkToDevice(":GC#", TelDate, 9, 5)
WScript.Sleep 250
objEngFile.WriteLine("CheckTime (" & FormatDateTime(Now,3) & "): Getting Telescope Time") 
Call TalkToDevice(":GL#", TelTime, 9, 5)
objEngFile.WriteLine("CheckTime (" & FormatDateTime(Now,3) & "): Done With Telescope Communication") 


'Leap seconds since Jan 6, 1980 
'must agree with MAX Mount (plus 1 second for communication lag); doesn't really have to be "right"
LocalTime1 = Now - 14/86400
LocalTime2 = LocalTime1 + 1/86400
LocalTime3 = LocalTime1 + 2/86400

'Get the current time
StrTime1 = Right(string(2,"0") & Hour(LocalTime1), 2) & ":" &_
           Right(string(2,"0") & Minute(LocalTime1), 2) & ":" &_
           Right(string(2,"0") & Second(LocalTime1), 2) & "#"
StrTime2 = Right(string(2,"0") & Hour(LocalTime2), 2) & ":" &_
           Right(string(2,"0") & Minute(LocalTime2), 2) & ":" &_
           Right(string(2,"0") & Second(LocalTime2), 2) & "#"
StrTime3 = Right(string(2,"0") & Hour(LocalTime3), 2) & ":" &_
           Right(string(2,"0") & Minute(LocalTime3), 2) & ":" &_
           Right(string(2,"0") & Second(LocalTime3), 2) & "#"

StrDate = Right(string(2,"0") & Month(LocalTime2),2) & "/" &_
          Right(string(2,"0") & Day(LocalTime2), 2) & "/" &_
          Right(string(2,"0") & Year(LocalTime2), 2) & "#"

WScript.Sleep 250
If TelTime <> StrTime1 and TelTime <> StrTime2 and TelTime <> StrTime3 or TelDate <> strDate Then
  objEngFile.WriteLine("CheckTime (" & FormatDateTime(Now,3) & "): WARNING: Telescope Time=" & TelTime & ", Real time=" & StrTime1 & StrTime2 & StrTime3 & " Telescope Date=" & TelDate & " Real Date=" & strDate & "; Resetting clock") 
  SyncTime
  Exit Sub
End If

objEngFile.WriteLine("CheckTime (" & FormatDateTime(Now,3) & "): Telescope Time Correct! Telescope Time=" & TelTime & ", Real time=" & StrTime1 & StrTime2 & StrTime3 & " Telescope Date=" & TelDate & " Real Date=" & strDate) 

End SUb