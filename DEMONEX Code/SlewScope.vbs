Function SlewScope(objRA,objDec,objname)

  SlewStart = Now

  objEngFile.WriteLine("SlewScope (" & FormatDateTime(Now,3) & "): Begin tracking")
  Call objTel.SetTracking(1, 1, 1, 1)  

  objEngFile.WriteLine("SlewScope (" & FormatDateTime(Now,3) & "): Checking date/time")
  CheckTime
  CheckPos

  Call objTel.SlewToRaDec(objRA,objDec,objName)  

  'Wait for Telescope to finish slewing
  RACurrent = -1
  RAPrevious = -2
  DecCurrent = -1
  DecPrevious = -2
  Do While Round(RAPrevious,5) <> Round(RACurrent,5) and Round(DecPrevious,4) <> Round(DecCurrent,4)
    RAPrevious = RACurrent
    DecPrevious = DecCurrent
    Call objTel.GetRaDec()
    RACurrent  = objTel.dRa
    DecCurrent = objTel.dDec
    objEngFile.WriteLine("SlewScope (" & FormatDateTime(Now,3) & "): Slewing: Current RA/dec = " & RACurrent & ", " & DecCurrent & ", Previous RA/Dec = " & RAPrevious & ", " & DecPrevious & ", RA/Dec desired = " & adNow(0) & ", " & adNow(1) & "; waiting for completion.")
    WScript.Sleep 5000
  Loop
  WScript.Sleep 10000

  CheckPos

  objEngFile.WriteLine("SlewScope (" & FormatDateTime(Now,3) & "): Slew completed in " &_
    Round((Now - SlewStart)*86400,2) & " seconds")
  
End Function