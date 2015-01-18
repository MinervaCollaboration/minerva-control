Const ForReading = 1

Set objTel = WScript.CreateObject("TheSky6.RASCOMTele")
objTel.Connect()

'Include functions
Set objFSO = CreateObject("Scripting.fileSystemObject")
Set objFile = objFSO.OpenTextFile("../TalkToLX200.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("../TalkToDevice.vbs", ForReading)
Execute objFile.ReadAll()


'Leap seconds since Jan 6, 1980 
'must agree with MAX Mount (plus 1 second for communication lag); doesn't really have to be "right"
LocalTime = Now - 12/86400

'Get the current time
StrTime = Right(string(2,"0") & Hour(LocalTime), 2) & ":" &_
          Right(string(2,"0") & Minute(LocalTime), 2) & ":" &_
          Right(string(2,"0") & Second(LocalTime), 2) 
Tx = ":SL" & StrTime & "#"

'Transmit the Time Sync string
Call TalkToLX200(Tx, Rx, 0, 1)
WScript.Sleep 250

'Get the current UT date
UTDate = Now + 7/24
StrDate = Right(string(2,"0") & Month(UTDate), 2) & "/" &_
          Right(string(2,"0") & Day(UTDate), 2) & "/" &_
          Right(string(2,"0") & Year(UTDate), 2) 
Tx = ":SC" & StrDate & "#"
Call TalkToLX200(Tx, Rx, 0, 1)
WScript.Sleep 250

CheckTime


Sub CheckTime

'Leap seconds since Jan 6, 1980 
'must agree with MAX Mount (plus 1 second for communication lag); doesn't really have to be "right"
LocalTime1 = Now - 14/86400
LocalTime2 = LocalTime1 + 1/86400
LocalTime3 = LocalTime1 + 2/86400


Call TalkToDevice(":GC#", TelDate, 9, 5)
WScript.Sleep 250
Call TalkToDevice(":GL#", TelTime, 9, 5)
WScript.Sleep 250

'MsgBox("CheckTime (" & FormatDateTime(Now,3) & "): Telescope Date is " & TelDate) 
'MsgBox("CheckTime (" & FormatDateTime(Now,3) & "): Telescope Time is " & TelTime) 
'MsgBox("CheckTime (" & FormatDateTime(Now,3) & "): Done With Telescope Communication") 


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

If TelTime <> StrTime1 and TelTime <> StrTime2 and TelTime <> StrTime3 or TelDate <> strDate Then
  MsgBox("CheckTime (" & FormatDateTime(Now,3) & "): WARNING: Telescope Time=" & TelTime & ", Real time=" & StrTime1 & StrTime2 & StrTime3 & " Telescope Date=" & TelDate & " Real Date=" & strDate & "; Resetting clock") 
  Exit Sub
End If

MsgBox("CheckTime (" & FormatDateTime(Now,3) & "): Telescope Time Correct! Telescope Time=" & TelTime & ", Real time=" & StrTime1 & StrTime2 & StrTime3 & " Telescope Date=" & TelDate & " Real Date=" & strDate)

End SUb