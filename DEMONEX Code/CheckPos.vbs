Sub CheckPos

Call TalkToDevice(":GL#", TelTime, 9, 5)
Call TalkToDevice(":GC#", TelDate, 9, 5)
LocalTime = Now - 13/86400
StrTime = Right(string(2,"0") & Hour(LocalTime), 2) & ":" &_
           Right(string(2,"0") & Minute(LocalTime), 2) & ":" &_
           Right(string(2,"0") & Second(LocalTime), 2) & "#"
StrDate = Right(string(2,"0") & Month(LocalTime),2) & "/" &_
          Right(string(2,"0") & Day(LocalTime), 2) & "/" &_
          Right(string(2,"0") & Year(LocalTime), 2) & "#"

Call objTel.GetRaDec()
TheSky6RA  = objTel.dRa
TheSky6Dec = objTel.dDec

Call objTel.GetAzAlt()
TheSky6Az  = objTel.dAz
TheSky6Alt = objTel.dAlt


Call TalkToLX200(":GR#", TelRA, 2, 10)
Call TalkToLX200(":GD#", TelDec, 2, 10)

Call TalkToLX200(":GZ#", TelAz, 2, 10)
Call TalkToLX200(":GA#", TelAlt, 2, 10)

objEngFile.WriteLine("CheckPos (" & FormatDateTime(Now,3) & "): Current Time: " & StrTime)
objEngFile.WriteLine("CheckPos (" & FormatDateTime(Now,3) & "): Current Telescope Time: " & TelTime)
objEngFile.WriteLine("CheckPos (" & FormatDateTime(Now,3) & "): Current Date: " & StrDate)
objEngFile.WriteLine("CheckPos (" & FormatDateTime(Now,3) & "): Current Telescope Date: " & TelDate)
objEngFile.WriteLine("CheckPos (" & FormatDateTime(Now,3) & "): Current TheSky6 RA: " & TheSky6RA)
objEngFile.WriteLine("CheckPos (" & FormatDateTime(Now,3) & "): Current Telescope RA:" & TelRA)
objEngFile.WriteLine("CheckPos (" & FormatDateTime(Now,3) & "): Current TheSky6 Dec: " & Thesky6Dec)
objEngFile.WriteLine("CheckPos (" & FormatDateTime(Now,3) & "): Current Telescope Dec:" & TelDec)
objEngFile.WriteLine("CheckPos (" & FormatDateTime(Now,3) & "): Current TheSky6 Az: " & TheSky6Az)
objEngFile.WriteLine("CheckPos (" & FormatDateTime(Now,3) & "): Current Telescope Az:" & TelAz)
objEngFile.WriteLine("CheckPos (" & FormatDateTime(Now,3) & "): Current TheSky6 Alt: " & TheSky6Alt)
objEngFile.WriteLine("CheckPos (" & FormatDateTime(Now,3) & "): Current Telescope Alt:" & TelAlt)

End Sub