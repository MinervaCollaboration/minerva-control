Sub AsynchSolve(filename, raobject, decobject)

  'Copy the image to the shared directory
  set objFSO = CreateObject("Scripting.FileSystemObject")

  If Not objFSO.FileExists(filename) Then
    RACenter = "FAIL"
    DecCenter = "FAIL"
    objEngFile.WriteLine("AsyncSolve (" & FormatDateTime(Now,3) & "): Error: image does not exist")
    Exit Sub
  End If


  solveStart = Now
  'SSH into the linux machine and solve the field with Astrometry.net's software
  Set ObjWS = WScript.CreateObject("WScript.Shell")
  cmd = "astrometry.bat " & filename & " " & raobject*15 & " " & decobject  
  objEngFile.WriteLine("AsyncSolve (" & FormatDateTime(Now,3) & "): Running command: " & cmd)

  'Run the program and capture output  
  Set oiExec   = objWS.Exec(cmd)
  Set oiStdOut = oiExec.StdOut
  Do While (Not oiStdOut.AtEndOfStream)
    sLine = oiStdOut.ReadLine
    output = Split(sLine)
  Loop

  RACenter = output(0)
  DecCenter = output(1)
  Orientation = output(2)
  xobject = output(3)
  yobject = output(4)

  objEngFile.WriteLine("AsyncSolve (" & FormatDateTime(Now,3) & "): Done with coordinate solution in " &_
    Round((Now - solveStart)*86400,2) & " seconds")

  If RACenter = "FAIL" then 
    objEngFile.WriteLine("AsyncSolve (" & FormatDateTime(Now,3) & "): Coordinate solution for " & filename & " failed")
  else 
    objEngFile.WriteLine("AsyncSolve (" & FormatDateTime(Now,3) & "): Center of image " & filename & " is RA=" & RACenter & " Dec=" & DecCenter)
  End If

End Sub