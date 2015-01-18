Sub SolveFieldAndMap(filename)

  'Copy the image to the shared directory
  set objFSO = CreateObject("Scripting.FileSystemObject")

  If Not objFSO.FileExists(filename) Then
    Exit Sub
  End If

  set objImage = objFSO.GetFile(filename)
  objImage.Copy("C:\demonex\share\")

  'Write the name of the file to solve
  Set toSolveFile = objFSO.OpenTextFile("C:\demonex\share\tosolve.txt", ForWriting)
  toSolveFile.WriteLine(objFSO.GetFileName(objImage))
  toSolveFile.Close

  'SSH into the linux machine and solve the field with Astrometry.net's software
  Set ObjWS = WScript.CreateObject("WScript.Shell")
  ObjWS.Run "astrometrymap.bat", 0, False


End Sub


