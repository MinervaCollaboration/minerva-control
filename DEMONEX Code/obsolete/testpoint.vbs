Set Image = CreateObject("CCDSoft.Image")
'Image.Path = "C:\demonex\data\n20081115\TmpPrefix.00035172.Pointing.FIT"
'Image.Open()


Set objCam = WScript.CreateObject("CCDSoft.Camera")

objCam.Connect
'objCam.TakeImage

Image.AttachToActive'Imager
Image.ScaleInArcsecondsPerPixel = 0.754
On Error Resume Next
Image.InsertWCS True
If Err.Number <> 0 Then
  Msgbox(err.description)
Else
  RaDec = Image.XYToRaDec(Image.Width/2,Image.Height/2)
  msgbox(radec(0) & " " & radec(1))
End If

Err.Clear
On Error Goto 0