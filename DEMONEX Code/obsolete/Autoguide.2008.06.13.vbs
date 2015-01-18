Const ForReading = 1
Const ForAppending = 8

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

GuideBoxSize = 128

'If started between midnight and noon, use the yesterday's date
If Hour(Now) < 12 Then
  night = Right(string(4,"0") & Year(Now-1), 4) &_
  Right(string(2,"0") & Month(Now-1), 2) &_
  Right(string(2,"0") & Day(Now-1), 2)
Else 
  night = Right(string(4,"0") & Year(Now), 4) &_
    Right(string(2,"0") & Month(Now), 2) &_
    Right(string(2,"0") & Day(Now), 2)
End If

datapath = "C:\demonex\data\n" & night & "\"

'Open guider log file
Set objFSO = CreateObject("Scripting.FileSystemObject")
strGdrFile = datapath & "n" & night & ".gdr"

If objFSO.FileExists(strGdrFile) Then
   'do nothing
Else
   Set objFile = objFSO.CreateTextFile(strGdrFile)
   objFile.Close
End If

Set objGdrFile = objFSO.OpenTextFile(strGdrFile, ForAppending)
Set objFile = objFSO.OpenTextFile("FindGuideStar.vbs", ForReading)
Execute objFile.ReadAll()

  Set objCam = WScript.CreateObject("CCDSoft.Camera","MyCamera_")
  objGdrFile.WriteLine("ConnectAll (" & FormatDateTime(Now,3) & "): Connecting to the Autoguider")
  objCam.Autoguider = 1
  objCam.Connect()

  'Set the Merdian Flip
  MerdianFlip = WScript.Arguments.Item(0)
  objCam.ReverseX = CLng(MeridianFlip)

  FindGuideStar

  'Never Found Guide Star; exit guider
  If objCam.GuideStarX = -1 Then
    Wscript.Quit
  End If

  objGdrFile.WriteLine("Autoguide (" & FormatDateTime(Now,3) & "): Beginning Autoguiding")

  objCam.Autoguider = 1
  objCam.Asynchronous = 1
 
  objGdrFile.WriteLine("Autoguide (" & FormatDateTime(Now,3) & "): Setting up subframe")
  'Set the size of the subframe
  objCam.subframetop = objCam.GuideStarY - GuideBoxSize/2
  objCam.subframebottom = objCam.GuideStarY + GuideBoxSize/2
  objCam.subframeleft = objCam.GuideStarX - GuideBoxSize/2
  objCam.subframeright = objCam.GuideStarX + GuideBoxSize/2
  objCam.Subframe = True

  Do While 1

    objCam.TakeImage
    Do While Not cBool(objCam.IsExposureComplete)
      WScript.Sleep 100
    Loop

  Loop


Public Sub MyCamera_CameraEvent(EventID, WhichCamera, MyString, Param1, Param2)

  Const cdGuideError=21
  EventNames = Array("cdConnected","cdDisconnected","cdBeforeTakeImage","cdAfterTakeImage","cdBeforeSelectFilter","cdAfterSelectFilter","cdBeforeFlipMirror","cdAfterFlipMirror","cdBeforeDelay","cdAfterDelay","cdBeforeExposure","cdAfterExposure","cdBeforeDigitize","cdAfterDigitize","cdBeforeDownload","cdAfterDownload","cdBeforeImageCalibration","cdAfterImageCalibration","cdBeforeAutoSave","cdAfterAutoSave","cdBeforeDisplayImage","cdAfterDisplayImage","cdGuideError","cdMaximumFound","cdExposing")

'msgbox(eventid & " " & cdGuideError) 

  'Before Guider Corrections
  If (EventId = cdGuideError) Then



'msgbox("yay!")


    Agressiveness = 0.25

    objCam.Autoguider = 1

    objCam.EnabledXAxis = True
    objCam.EnabledYAxis = True

    Set objImage = WScript.CreateObject("CCDSoft.Image")

    objImage.AttachToActiveAutoGuider


If objImage.Width = GuideBoxSize Then

    objImage.ShowInventory
    X = objImage.InventoryArray(cdInventoryX)
    Y = objImage.InventoryArray(cdInventoryY)
    Magnitude    = objImage.InventoryArray(cdInventoryMagnitude)
    objClass     = objImage.InventoryArray(cdInventoryClass)
    FWHM         = objImage.InventoryArray(cdInventoryFWHM)
    MajorAxis    = objImage.InventoryArray(cdInventoryMajorAxis)
    MinorAxis    = objImage.InventoryArray(cdInventoryMinorAxis)
    Theta        = objImage.InventoryArray(cdInventoryTheta)
    Ellipticity  = objImage.InventoryArray(cdInventoryEllipticity)

    Nstars = UBound(X)
    TargetMag = 2.0   
    MaxMag = 2.5
    MaxBadGuides = 3

CurrentExpTime = objCam.AutoGuiderExposureTime

    If NStars > 0 Then
      If Magnitude(0) < MaxMag Then

	'Scale the Exposure Time to get Mag = TargetMag
        Scale = 10^(-0.4*(TargetMag - Magnitude(0)))

	If CurrentExpTime*Scale < 0.001 Then
          objGdrFile.WriteLine("Camera Event " & EventNames(EventID) & " (" & FormatDateTime(Now,3) & "): Scaling Autoguider exposure from " & CurrentExpTime & " to 0.001") 
          objCam.AutoGuiderExposureTime = 0.001
        Else
          objGdrFile.WriteLine("Camera Event " & EventNames(EventID) & " (" & FormatDateTime(Now,3) & "): Scaling Autoguider exposure from " & CurrentExpTime & " to " & CurrentExpTime*Scale)
          objCam.AutoGuiderExposureTime = CurrentExpTime*Scale
        End If        

        FromX = objImage.Width/2 + (X(0) - objImage.Width/2)*Agressiveness
        FromY = objImage.Height/2 + (Y(0) - objImage.Height/2)*Agressiveness

        ToX = objImage.Width/2
        ToY = objImage.Height/2
        objGdrFile.WriteLine("Camera Event " & EventNames(EventID) & " (" & FormatDateTime(Now,3) & "): Moving Guide Star from (" & FromX & "," & FromY & ") to (" & ToX & "," & ToY & ")")
'        Call objCam.Move(FromX, FromY, ToX, ToY)
        BadGuideCounter = 0
   
      Else
        objGdrFile.WriteLine("Camera Event " & EventNames(EventID) & " (" & FormatDateTime(Now,3) & "): Guide star dimmed beyond threshhold; doubling exposure time and ignoring correction")
        objCam.AutoGuiderExposureTime = CurrentExpTime*2
        BadGuideCounter = BadGuideCounter + 1      
      End If
    Else 
      objGdrFile.WriteLine("Camera Event " & EventNames(EventID) & " (" & FormatDateTime(Now,3) & "): No stars in subframe; doubling exposure time and increasing subframe size")
      objCam.AutoGuiderExposureTime = CurrentExpTime*2
      GuideBoxSize = GuideBoxSize*1.5
      If GuideBoxSize > 108 Then
        objGdrFile.WriteLine("Camera Event " & EventNames(EventID) & " (" & FormatDateTime(Now,3) & "): Cannot recover guide star; clouds?")
       GuideBoxSize = 32
      End If 
      BadGuideCounter = BadGuideCounter + 1  
    End If

    objCam.EnabledXAxis = False
    objCam.EnabledYAxis = False 


    If BadGuideCounter >= MaxBadGuides Then
      objGdrFile.WriteLine("Camera Event " & EventNames(EventID) & " (" & FormatDateTime(Now,3) & "): Too many bad guides, Reacquiring Guide Star")
'      StopGuiding = True
'
'      objCam.TakeImage     
    End If

End If
    objImage.Close
 
  End If 'Camera Event cdGuideError

End Sub