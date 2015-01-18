Const ForReading = 1
Const ForAppending = 8

Set objFSO = CreateObject("Scripting.fileSystemObject")
Set objFile = objFSO.OpenTextFile("SolveField.vbs", ForReading)
Execute objFile.ReadAll()

strEngFile = "nYYYYMMDD.eng"
Set objEngFile = objFSO.OpenTextFile(strEngFile, ForAppending)

  'Start TheSky6
  set objTheSky6 = CreateObject("TheSky6.RASSERVERAPP")
  objTheSky6.SetVisible(1)
  Set objTheSky = WScript.CreateObject("TheSky6.RASCOMTheSky")
  objTheSky.Connect()

  'Connect to the Telescope
  Set objTel = WScript.CreateObject("TheSky6.RASCOMTele")
  objTel.Connect()

  Set Utils = CreateObject("TheSky6.Utils")

  set objCCDSoft = CreateObject("CCDSOFT.RASSERVERAPP")
  objCCDSoft.SetVisible(1)

  Set objCam = WScript.CreateObject("CCDSoft.Camera")
  objCam.Connect()
  objCam.AutoSaveOn = True
  objCam.ExposureTime = 15
  objCam.Frame = 1 'Light

'  Call objTel.SlewToAzAlt(270,75,"Syncing")

  Call objTel.SetTracking(1, 1, 1, 1)

  objCam.TakeImage

  Set Image = CreateObject("CCDSoft.Image")
  Image.AttachToActiveImager
  Image.Save
  ra = 1
  dec = 1
  Call SolveField(Image.Path, RACenter, DecCenter, Orientation, ra, dec, CurrentX, CurrentY)

  If RACenter = "FAIL" then 
    MsgBox("Alignment Failed")
  Else 
  
  MsgBox(racenter & " " & deccenter)
    RADecActNow = Utils.Precess2000ToNow(RACenter,DecCenter)
    Call objTel.Sync(RADecActNow(0),RADecActNow(1), "Image Link's Solution")
    MsgBox("Alignment Succeeded")
  End If