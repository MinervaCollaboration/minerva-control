Const ForReading = 1

cmd="asyncastrom.bat E:\demonex\data\n20110508\n20110508.HAT-P-3b.T.0036.fits 206.094075 48.028667"
Set ObjWS = WScript.CreateObject("WScript.Shell")
dummy = ObjWS.Run(cmd,1,1)

Set objFSO = CreateObject("Scripting.fileSystemObject")

targetx = 1024
targety = 1024

SolveName = "C:\demonex\share\solve.txt"

If objFSO.FileExists(solvename) Then

  MsgBox("BeforeDownload (" & FormatDateTime(Now,3) & "): reading coordinate solution")

  Set SolveFile = objFSO.OpenTextFile(Solvename, ForReading)
  line = SolveFile.Readline
  SolveFile.Close
  arr = split(line)
      
  If arr(0) <> "FAIL" Then

    X = arr(3)
    Y = arr(4)
    Peak = arr(5)

    MsgBox("BeforeDownload (" & FormatDateTime(Now,3) & "): Peak Counts around target: " & peak)

    'What about cosmic rays?
    If Peak > 55000 Then
      MsgBox("BeforeDownload (" & FormatDateTime(Now,3) & "): Target saturated; reducing exposure time")
    End If 

    PlateScale = 0.754
    RAOffset  = (X - TargetX)*Platescale
    DecOffset = (Y - TargetY)*Platescale       
    GuiderScaleArcsecPerPixel = 3.09
    Aggressiveness = 0.75
    FromX = 0
    FromY = 0
    ToX = RAOffset/GuiderScaleArcsecPerPixel*Aggressiveness
    ToY = DecOffset/GuiderScaleArcsecPerPixel*Aggressiveness
    Minoffset = 10*Platescale/GuiderScaleArcsecPerPixel' (mount jitter)
    Maxoffset = 300*Platescale/GuiderScaleArcsecPerPixel'fucked
    offset = sqr(tox^2 + toy^2)

    MsgBox(minoffset)
    MsgBox(maxoffset)
    MsgBox(offset)

    If offset > minoffset Then
      If Offset < MaxOffset Then
        'Reverse x correction if West of Meridian
        If MeridianFlip Then ToX = -ToX
        MsgBox("BeforeDownload (" & FormatDateTime(Now,3) & "): Moving from " & fromX & "," & fromY & " to " & toX & "," & toY)        
'        objCam.Autoguider = 1
'        objCam.EnabledXAxis = 1
'        objCam.EnabledYAxis = 1
'        Call objCam.Move(FromX, FromY, ToX, ToY)
        MsgBox("BeforeDownload (" & FormatDateTime(Now,3) & "): Done moving")        
'        objCam.EnabledXAxis = 0
'        objCam.EnabledYAxis = 0
'        objCam.Autoguider = 0
'        WScript.Sleep(5000)
      Else
        MsgBox("BeforeDownload (" & FormatDateTime(Now,3) & "): Object too far away -- recentering")
        AcquireObject = True
      End If 
    End If
  Else
    msgbox("BeforeDownload (" & FormatDateTime(Now,3) & "): Coordinate Solution Failed")
  End If

'  objFSO.DeleteFile(SolveName)

End If
