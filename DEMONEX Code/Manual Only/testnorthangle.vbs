
pi = 4*Atn(1)
Set Image = CreateObject("CCDSoft.Image")

'Image.Path = "E:\DEMONEX\DATA\N20090929\TmpPrefix.00004856.CoRoT-Exo-2b.S.FIT" 'should be ~180
'Image.Path = "E:\DEMONEX\DATA\N20090929\TmpPrefix.00005681.WASP-12b.S.FIT" 'should be ~0
Image.Path = "C:\Image.000.fits"

Image.Open
Image.ScaleInArcsecondsPerPixel = 0.754
Call Image.InsertWCS(1)
Image.FITSKeyword("PA_NCCW") = 0
'MsgBox(Image.NorthAngle)

cd1_1 = Image.FITSKeyword("CD1_1")
cd1_2 = Image.FITSKeyword("CD1_2")
cd2_1 = Image.FITSKeyword("CD2_1")
cd2_2 = Image.FITSKeyword("CD2_2")

xscale = sqr(cd1_1^2 + cd1_2^2)
yscale = sqr(cd2_1^2 + cd2_2^2)
sintheta = cd2_1/yscale
costheta = cd1_1/xscale

orientation = -atn(sintheta/costheta)*180/pi
If costheta < 0 then orientation = orientation + 180
If orientation > 180 then orientation = orientation - 360
'MsgBox(orientation)



    cd1_1 = Image.FITSKeyword("CD1_1")
    cd1_2 = Image.FITSKeyword("CD1_2")
    cd2_1 = Image.FITSKeyword("CD2_1")
    cd2_2 = Image.FITSKeyword("CD2_2")

    xscale = sqr(cd1_1^2 + cd1_2^2)
    yscale = sqr(cd2_1^2 + cd2_2^2)
    sintheta = cd2_1/yscale
    costheta = cd1_1/xscale

    orientation = -atn(sintheta/costheta)*180/pi
    If costheta < 0 then orientation = orientation + 180
    If orientation > 180 then orientation = orientation - 360

    RADec2000 = Image.XYToRaDec(TargetX,TargetY)
    RACenter = RADec2000(0)
    DecCenter = RADec2000(1)

ra = racenter + 2/15
dec = deccenter 
msgbox(ra & " " & racenter)
msgbox(cos(deccenter*pi/180))

    'ImageLink's solution cannot be trusted if offset more than FOV
    If (abs(orientation) > 5 and abs(abs(orientation) - 180) > 5) or abs(racenter - ra)*cos(deccenter*pi/180)*15 > 1 or abs(deccenter - dec) > 1 Then

msgbox("imagelink failed")
    End If


'Image.Close

if 0 then 

Image.Path = "C:\Image.090.fits"
Image.Open
Image.ScaleInArcsecondsPerPixel = 0.754
Call Image.InsertWCS(1)
Image.FITSKeyword("PA_NCCW") = 0
MsgBox(Image.NorthAngle)
cd1_1 = Image.FITSKeyword("CD1_1")
cd1_2 = Image.FITSKeyword("CD1_2")
cd2_1 = Image.FITSKeyword("CD2_1")
cd2_2 = Image.FITSKeyword("CD2_2")

xscale = sqr(cd1_1^2 + cd1_2^2)
yscale = sqr(cd2_1^2 + cd2_2^2)
sintheta = cd2_1/yscale
costheta = cd1_1/xscale

orientation = -atn(sintheta/costheta)*180/pi
If costheta < 0 then orientation = orientation + 180
If orientation > 180 then orientation = orientation - 360
MsgBox(orientation)
Image.Close

Image.Path = "C:\Image.180.fits"
Image.Open
Image.ScaleInArcsecondsPerPixel = 0.754
Call Image.InsertWCS(1)
Image.FITSKeyword("PA_NCCW") = 0
MsgBox(Image.NorthAngle)
cd1_1 = Image.FITSKeyword("CD1_1")
cd1_2 = Image.FITSKeyword("CD1_2")
cd2_1 = Image.FITSKeyword("CD2_1")
cd2_2 = Image.FITSKeyword("CD2_2")

xscale = sqr(cd1_1^2 + cd1_2^2)
yscale = sqr(cd2_1^2 + cd2_2^2)
sintheta = cd2_1/yscale
costheta = cd1_1/xscale

orientation = -atn(sintheta/costheta)*180/pi
If costheta < 0 then orientation = orientation + 180
If orientation > 180 then orientation = orientation - 360
MsgBox(orientation)
Image.Close

Image.Path = "C:\Image.270.fits"
Image.Open
Image.ScaleInArcsecondsPerPixel = 0.754
Call Image.InsertWCS(1)
Image.FITSKeyword("PA_NCCW") = 0
MsgBox(Image.NorthAngle)
cd1_1 = Image.FITSKeyword("CD1_1")
cd1_2 = Image.FITSKeyword("CD1_2")
cd2_1 = Image.FITSKeyword("CD2_1")
cd2_2 = Image.FITSKeyword("CD2_2")

xscale = sqr(cd1_1^2 + cd1_2^2)
yscale = sqr(cd2_1^2 + cd2_2^2)
sintheta = cd2_1/yscale
costheta = cd1_1/xscale


orientation = -atn(sintheta/costheta)*180/pi
If costheta < 0 then orientation = orientation + 180
If orientation > 180 then orientation = orientation - 360
MsgBox(orientation)
Image.Close
end if