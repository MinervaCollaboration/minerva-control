SubFrameSize = 40
TargetX = 1029
TargetY = 1108
dataDir = "E:\demonex\data\n20110411\"
strFilename = "TmpPrefix.00080526.TYC0272-00458-1.R.FIT"

XY = Centroid(dataDir & strFileName, targetX,targetY,subFrameSize)

msgbox(xy(0) & " " & xy(1) & " " & xy(2) & " " & xy(3) & " " & xy(4))

XY(0) = TargetX - subFrameSize/2 + XY(0) 
XY(1) = TargetY - subFrameSize/2 + XY(1) 

msgbox(xy(0) & " " & xy(1) & " " & xy(2) & " " & xy(3) & " " & xy(4))

Function Centroid(filename,xcen,ycen,SubFrameSize)

  minX = xcen - Subframesize/2
  maxX = xcen + Subframesize/2
  minY = ycen - Subframesize/2
  maxY = ycen + Subframesize/2

  cmd = "C:\cfitsio\centroid.exe " & filename & "[" & minx & ":" & maxX & "," & minY & ":" & maxY & "]"


 msgbox("Centroid (" & FormatDateTime(Now,3) & "): Issuing Command: " & cmd)

  'Run the program and capture output:
  Set objShell = WScript.CreateObject("WScript.Shell")
  Set oiExec   = objShell.Exec(cmd)
  Set oiStdOut = oiExec.StdOut
  sLine = oiStdOut.ReadLine
  Centroid = Split(sLine)

End Function