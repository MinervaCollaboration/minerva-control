'    Centers brightest star on the image.  Uses CCDSoft's built-in SExtractor
'  to locate sources within a subframe.  Brightest source's coordinates are
'  determined.  Plate scale calculated for KELT given current declination.
'  Script then iterates (with manual approval) and centers the brightest
'  object.  This will ultimately be used in lieu of Image Link and Sync for
'  automated mapping capability.  At present, this script operates as a
'  standalone to greatly simplify a manual mapping run.
'
'  NOTES / FUTURE IMPROVEMENTS:
'    -For the manual centering routine, a direct x,y offset input might be nice
'    -For the automated routine, sources ought to be scaled to a particular
'      instrumental magnitude.  This will get more photons for dimmer stars and
'      hopefully a more accurate centroid.  Additionally, I'll still need to
'      ensure that the ellipticity is as small as possible...
'
'Rob Siverd
'Created:      2008-04-21
'Last updated: 2008-05-30
'--------------------------------------------------------------------------
'**************************************************************************
'--------------------------------------------------------------------------
Option Explicit

'System stuff:
Dim objFSO : Set objFSO = CreateObject("Scripting.FileSystemObject")
Dim oWSH : Set oWSH = WScript.CreateObject("WScript.Shell")

'Astronomy stuff:
Dim objCam
Set objCam = WScript.CreateObject("CCDSoft.Camera")
Call objCam.Connect

Dim objImage
Set objImage = WScript.CreateObject("CCDSoft.Image")

Dim objTele                   'Paramount ME
Set objTele   = WScript.CreateObject("TheSky6.RASCOMTele")
Call objTele.Connect


'SExtractor inventory constants:
Const cdInventoryX=0
Const cdInventoryY=1
Const cdInventoryMagnitude=2
Const cdInventoryClass=3
Const cdInventoryFWHM=4
Const cdInventoryMajorAxis=5
Const cdInventoryMinorAxis=6
Const cdInventoryTheta=7
Const cdInventoryEllipticity=8

'Standard imaging options (with cutout)
Dim SF_Size,SF_L,SF_R,SF_T,SF_B,SF_HalfSize
SF_Size     = 300     'Size of subframe in pixels
SF_HalfSize = 1000
SF_T   = (2048 / 2) - SF_HalfSize
SF_R   = (2048 / 2) + SF_HalfSize
SF_B   = (2048 / 2) + SF_HalfSize
SF_L   = (2048 / 2) - SF_HalfSize

'Other variables:
Dim strLastImage,strSavePath,strFullImage,strFixtImage
strSavePath = objCam.AutoSavePath 'Where the image gets saved...
Dim MBAns  : MBAns  = 0  'Response to MsgBox
Dim AdjAns : AdjAns = 0
Dim PI : PI = 4 * Atn(1)

'Connect to camera and set image acquisition parameters:
Dim ExpTime : ExpTime = 0.25
Call objCam.Connect : WScript.Sleep 500
objCam.Frame = 1                 'Light frame
objCam.ImageReduction = 0        'No image reduction
objCam.ExposureTime   = ExpTime  'Set exposure time...
objCam.Subframe       = True     'Read out portion of chip...
objCam.SubframeLeft   = SF_L
objCam.SubframeTop    = SF_T
objCam.SubframeRight  = SF_R
objCam.SubframeBottom = SF_B

'Restore original imaging settings:
Sub ResetExposure
       objCam.ExposureTime = ExpTime
End Sub

'Inventory and position data:
Dim X,Y,Magnitude,Class1,FWHM,MajorAxis,MinorAxis,Theta,Ellipticity,i,Msg
Dim DeltaX,DeltaY,LastDX,LastDY,JogX,JogY,MovedX,MovedY
MovedX = 0
MovedY = 0
Dim Xscale,Yscale
Dim Y5min,X5min
Dim JogN,JogE

'Determine Paramount ME orientation:
Dim MountAZ,MountALT,bMountEast,OrientMult


Do While ( MBAns < 7 )
       Msg = ""
       ResetExposure
       'Figure out mount orientation:
       objTele.GetAzAlt
       MountAZ  = objTele.dAz
       MountALT = objTele.dAlt
       OrientMult = 1 : If ( MountAZ < 180 ) Then OrientMult = -1

       'Acquire baseline image:
       Call GetBrightestOffset

       'Begin centering procedure if necessary:
       AdjAns = MsgBox("Center star?",4,"Center star?")

       If ( AdjAns < 7 ) Then
         'KELT pixel scale (hopefully):
         objTele.GetRaDec
         Y5min = OrientMult * ( 300 / 0.75 )
         X5min = OrientMult * ( 300 / 0.75 ) * Cos(PI * objTele.dDec / 180)

         'Msg = "Current declination: " & CCur(objTele.dDec) & vbCrLf & vbCrLf
         'Msg = Msg & "Using:" & vbCrLf & vbCrLf
         'Msg = Msg & "X:  " & CCur(5/X5min) & " min E. / pixel." & vbCrLf
         'Msg = Msg & "Y:  " & CCur(5/Y5min) & " min N. / pixel." & vbCrLf
         'MsgBox(Msg)
       End If

       Do While ( AdjAns < 7 )
               LastDX = DeltaX
               LastDY = DeltaY
               JogN   = -5 * DeltaY / Y5min
               JogE   = -5 * DeltaX / X5min

               'Reposition mount, gather new offsets:
               Call objTele.Jog(JogN,"North") : WScript.Sleep 500
               Call objTele.Jog(JogE, "East") : WScript.Sleep 500
               Call GetBrightestOffset()

               'MsgBox("Moved scope: "  & vbCrLf &_
               '       CCur(MovedX) & " in X" & vbCrLf &_
               '       CCur(MovedY) & " in Y" )

               AdjAns = MsgBox(Msg,4,"Adjust again?")

       Loop

       MBAns = MsgBox("Star centered!  Another object?",4,"Continue?")
Loop

MsgBox("Click OK to exit.")

Sub ProbeScale
       'Determine directions and scale:
       LastDX = DeltaX : LastDY = DeltaY
       Call objTele.Jog( 5,"North") : WScript.Sleep 500
       Call GetBrightestOffset
       Y5min = MovedY
       'Move back:
       Call objTele.Jog(-5,"North") : WScript.Sleep 500
       Call GetBrightestOffset
       LastDY = DeltaX : LastDY = DeltaY
       'Move East & measure:
       Call objTele.Jog( 5,"East")  : WScript.Sleep 500
       Call GetBrightestOffset
       X5min = MovedX
       'Move back:
       Call objTele.Jog(-5,"East")  : WScript.Sleep 500
       Call GetBrightestOffset

       Msg = "Directions probed!" & vbCrLf & vbCrLf
End Sub

Sub GetBrightestOffset '(dX,dY)
       Dim BigEllip : BigEllip = 5.0
       Dim TempExpo : TempExpo = objCam.ExposureTime

       'Adjust exposure time until brightest star is round.
       Do While ( BigEllip > 1.5 )
               objCam.ExposureTime = TempExpo
               objCam.TakeImage
               objImage.AttachToActive
               objImage.ShowInventory

               'Put inventory into arrays:
               X            = objImage.InventoryArray(cdInventoryX)
               Y            = objImage.InventoryArray(cdInventoryY)
               Magnitude    = objImage.InventoryArray(cdInventoryMagnitude)
               Class1       = objImage.InventoryArray(cdInventoryClass)
               FWHM         = objImage.InventoryArray(cdInventoryFWHM)
               MajorAxis    = objImage.InventoryArray(cdInventoryMajorAxis)
               MinorAxis    = objImage.InventoryArray(cdInventoryMinorAxis)
               Theta        = objImage.InventoryArray(cdInventoryTheta)
               Ellipticity  = objImage.InventoryArray(cdInventoryEllipticity)

               'Loop control:
               BigEllip     = Ellipticity(0)
               'MsgBox("Exp. time: " & TempExpo & ", Ellipt.: " & BigEllip )
               TempExpo     = TempExpo / 2.0
               objImage.Close

       Loop

       'Determine offset from center:
       DeltaX = X(0) - SF_HalfSize
       DeltaY = Y(0) - SF_HalfSize
       Msg    = "Brightest object:" & vbCrLf
       Msg    = Msg & "X   = " & X(0) & "  DeltaX = " & CCur(DeltaX) & vbCrLf
       Msg    = Msg & "Y   = " & Y(0) & "  DeltaY = " & CCur(DeltaY) & vbCrLf
       Msg    = Msg & vbCrLf & "Adjust again?" & vbCrLf

       'MsgBox("Brightest object has ellipticity: " & Ellipticity(0))

       'Calculate distance moved:
       MovedX = DeltaX - LastDX
       MovedY = DeltaY - LastDY

       'Delete previous files:
       strLastImage = objCam.LastImageFileName
       strFullImage = strSavePath & "\" & strLastImage & " "
       On Error Resume Next
       objFSO.DeleteFile strFullImage
       strFullImage = Replace(strFullImage,"FIT","SRC")
       objFSO.DeleteFile strFullImage
       On Error Goto 0

End Sub