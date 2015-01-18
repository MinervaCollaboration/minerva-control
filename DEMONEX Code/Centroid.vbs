'start = Timer
'xcen = 1011
'ycen = 1031
'subframesize = 100
't =  Centroid("C:\Image.000.fits",xcen,ycen,subframesize)
'msgbox(timer-start)
'msgbox(t(0)- subframesize/2 + xcen & " " & t(1)  - subframesize/2 + ycen & " " & t(2) & " " & t(3) & " " & t(4))

Function Centroid(filename,xcen,ycen,SubFrameSize)

  minX = xcen - Subframesize/2
  maxX = xcen + Subframesize/2
  minY = ycen - Subframesize/2
  maxY = ycen + Subframesize/2

  cmd = "C:\cfitsio\centroid.exe " & filename & "[" & minx & ":" & maxX & "," & minY & ":" & maxY & "]"

  objEngFile.WriteLine("Centroid (" & FormatDateTime(Now,3) & "): Issuing Command: " & cmd)

  'Run the program and capture output:
  Set objShell = WScript.CreateObject("WScript.Shell")
  Set oiExec   = objShell.Exec(cmd)
  Set oiStdOut = oiExec.StdOut
  sLine = oiStdOut.ReadLine
  Centroid = Split(sLine)

End Function