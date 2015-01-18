Sub SyncTime

'Leap seconds since Jan 6, 1980 
'must agree with MAX Mount (plus 1 second for communication lag); doesn't really have to be "right"
LocalTime = Now - 12/86400

'Get the current time
StrTime = Right(string(2,"0") & Hour(LocalTime), 2) & ":" &_
          Right(string(2,"0") & Minute(LocalTime), 2) & ":" &_
          Right(string(2,"0") & Second(LocalTime), 2) 
Tx = ":SL" & StrTime & "#"

'Transmit the Time Sync string
Call TalkToDevice(Tx, Rx, 1, 5)

'Get the current UT date (:SCMM/DD/YY# Sets in UT date!)
UTDate = Now + 7/24
StrDate = Right(string(2,"0") & Month(UTDate), 2) & "/" &_
          Right(string(2,"0") & Day(UTDate), 2) & "/" &_
          Right(string(2,"0") & Year(UTDate), 2) 
Tx = ":SC" & StrDate & "#"
Call TalkToLX200(Tx, Rx, 0, 1)
WScript.Sleep 250

'Confirm values scope has make sense
CheckTime

End SUb