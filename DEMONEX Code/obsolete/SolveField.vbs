Sub solvefield(filename, RACenter, DecCenter, Orientation)

  'Copy the image to the shared directory
  set objFSO = CreateObject("Scripting.FileSystemObject")

  If Not objFSO.FileExists(filename) Then
    RACenter = "FAIL"
    DecCenter = "FAIL"
    objEngFile.WriteLine("SolveField (" & FormatDateTime(Now,3) & "): Error: image does not exist")
'msgbox("SolveField (" & FormatDateTime(Now,3) & "): Error: image does not exist")
    Exit Sub
  End If

  objEngFile.WriteLine("SolveField (" & FormatDateTime(Now,3) & "): Copying " & filename)
'msgbox("SolveField (" & FormatDateTime(Now,3) & "): Copying " & filename)
  set objImage = objFSO.GetFile(filename)
  objImage.Copy("C:\demonex\share\")

  objEngFile.WriteLine("SolveField (" & FormatDateTime(Now,3) & "): Creating tosolve.txt file")
'msgbox("SolveField (" & FormatDateTime(Now,3) & "): Creating tosolve.txt file")
  'Write the name of the file to solve
  Set toSolveFile = objFSO.OpenTextFile("C:\demonex\share\tosolve.txt", ForWriting)
  toSolveFile.WriteLine(objFSO.GetFileName(objImage))
  toSolveFile.Close


  objEngFile.WriteLine("SolveField (" & FormatDateTime(Now,3) & "): Beginning Coordinate Solution on " & filename)
'msgbox("SolveField (" & FormatDateTime(Now,3) & "): Beginning Coordinate Solution on " & filename)
  solveStart = Now
  'SSH into the linux machine and solve the field with Astrometry.net's software
  Set ObjWS = WScript.CreateObject("WScript.Shell")
  ObjWS.Run "astrometry.bat", 0, True

  objEngFile.WriteLine("SolveField (" & FormatDateTime(Now,3) & "): Done with coordinate solution in " &_
    Round((Now - solveStart)*86400,2) & " seconds")
'msgbox("SolveField (" & FormatDateTime(Now,3) & "): Done with coordinate solution in " & Round((Now - solveStart)*86400,2) & " seconds")

  'read the results of the field
  Set solvedFile = objFSO.OpenTextFile("C:\demonex\share\solved.txt", ForReading)
  RACenter = solvedFile.Readline

  If RACenter = "FAIL" then 
    DecCenter = "FAIL"
    objEngFile.WriteLine("SolveField (" & FormatDateTime(Now,3) & "): Coordinate solution for " & filename & " failed")
'msgbox("SolveField (" & FormatDateTime(Now,3) & "): Coordinate solution for " & filename & " failed")
  else 
    DecCenter = solvedFile.Readline
    Orientation = solvedFile.Readline
    objEngFile.WriteLine("SolveField (" & FormatDateTime(Now,3) & "): Center of image " & filename & " is RA=" & RACenter & " Dec=" & DecCenter)
'MsgBox("SolveField (" & FormatDateTime(Now,3) & "): Center of image " & filename & " is RA=" & RACenter & " Dec=" & DecCenter)
  End If
  solvedFile.Close

'Write FAIL to the file in case the next solution doesn't complete
  objEngFile.WriteLine("SolveField (" & FormatDateTime(Now,3) & "): Overwriting solve.txt file")
'msgbox("SolveField (" & FormatDateTime(Now,3) & "): Overwriting solved.txt file")
  Set SolvedFile = objFSO.OpenTextFile("C:\demonex\share\solved.txt", ForWriting)
  SolvedFile.WriteLine("FAIL")
  SolvedFile.Close

End Sub


