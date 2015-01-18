
racenter = 1
deccenter = 1

Set Utils = CreateObject("TheSky6.Utils")
Do
  Err.Clear
  RADecActNow = Utils.Precess2000ToNow(RACenter,DecCenter)
Loop Until Err.Number <> 0


msgbox("50""")

if 0 then 
Const ForReading = 1
Set objFSO = CreateObject("Scripting.fileSystemObject")

  'read the results of the field
  Set solvedFile = objFSO.OpenTextFile("C:\demonex\share\solved.txt", ForReading)
  RACenter = solvedFile.Readline

  If RACenter = "FAIL" then 
    DecCenter = "FAIL"
'    objEngFile.WriteLine("SolveField (" & FormatDateTime(Now,3) & "): Coordinate solution for " & filename & " failed")
msgbox("SolveField (" & FormatDateTime(Now,3) & "): Coordinate solution for " & filename & " failed")
  else 
    DecCenter = solvedFile.Readline
'    objEngFile.WriteLine("SolveField (" & FormatDateTime(Now,3) & "): Center of image " & filename & " is RA=" & RACenter & " Dec=" & DecCenter)
MsgBox("SolveField (" & FormatDateTime(Now,3) & "): Center of image " & filename & " is RA=" & RACenter & " Dec=" & DecCenter)
  End If
  solvedFile.Close

end if