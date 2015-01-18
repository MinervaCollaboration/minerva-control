
StrTime1 = "12:00:23#"
StrTime2 = "12:00:24#"
StrTime3 = "12:00:25#"
StrDate = "05/27/10#"

TelTime = "12:00:20#"
TelDate = "05/27/10#"

If TelTime <> StrTime1 Then
  MsgBox(TelTime & " != " & StrTime1)
End If

If TelTime <> StrTime2 Then
  MsgBox(TelTime & " != " & StrTime2)
End If

If TelTime <> StrTime3 Then
  MsgBox(TelTime & " != " & StrTime3)
End If

If TelTime <> StrTime1 and TelTime <> StrTime2 and TelTime <> StrTime3 or TelDate <> strDate Then
  MsgBox("CheckTime (" & FormatDateTime(Now,3) & "): WARNING: Telescope Time=" & TelTime & ", Real time=" & StrTime1 & StrTime2 & StrTime3 & " Telescope Date=" & TelDate & " Real Date=" & strDate & "; Resetting clock")
End If

MsgBox("CheckTime (" & FormatDateTime(Now,3) & "): Telescope Time Correct! Telescope Time=" & TelTime & ", Real time=" & StrTime1 & StrTime2 & StrTime3 & " Telescope Date=" & TelDate & " Real Date=" & strDate)
