set Image = CreateObject("CCDSoft.Image")

Image.Path = "C:\demonex\share\TmpPrefix.00005527.WASP-10b.S.FIT"
Image.Open
Image.ScaleInArcsecondsPerPixel = 0.754

'Call Image.InsertWCS(1)

XY = Image.RADecToXY(348.99167/15,31.462778)

msgbox(xy(0) & " " & xy(1))

Image.Close
