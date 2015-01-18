Sub AlignEasy

  On Error Resume Next

  AlignStart = Now

  'Sync Telescope Clock
  objEngFile.WriteLine("Align (" & Now & "): Syncing telescope clock with computer clock")
  SyncTime

  'Find Home
  objEngFile.WriteLine("Align (" & Now & "): Finding Home")
  objTel.FindHome()

  'Home position (dynamic recalculation; updated after every sucessful sync on home)
  Set HomePosFile = objFSO.OpenTextFile("HomeAzAlt.txt", ForReading)
  HomeAz = HomePosFile.Readline
  HomeAlt = HomePosFile.Readline
  HomePosFile.Close

  Set Utils = CreateObject("TheSky6.Utils")
  adHome = Utils.ConvertAzAltToRADec(HomeAz,HomeAlt)
  adHomeNow = Utils.Precess2000ToNow(adHome(0),adHome(1))

  objEngFile.WriteLine("Align (" & Now & "): Syncing Telescope position")
  Call objTel.Sync(adHome(0),adHome(1), "Home Position")

  'IMAGE LINK AND SYNC; redefine home position (if it drifts more)??
  objCam.TakeImage
  coorSolveStart = Now
  Call objTheSky.ImageLink(0.75,adHome(0),adHome(1))
  If Err.Number <> 0 Then
    objEngFile.WriteLine("Align (" & Now & "): WARNING: Alignment failed; clouds? " &_
      strFileName & ":" & Err.Description)
    Err.Clear
  Else 

    Call objTheSky.GetObjectRaDec("Image Link Information") 
    CheckTel
    Call objTel.Sync(objTheSky.dObjectRa,objTheSky.dObjectDec, "Image Link's Sync")
    objEngFile.WriteLine("Align (" & Now & "): Completed Coordinate Solution in " & Round((Now - coorSolveStart)*86400) & " seconds")

    'Write the new coordinates of the home position
    adHome2000 = Utils.PrecessNowTo2000(objTheSky.dObjectRa,objTheSky.dObjectDec)
    AzAlt = Utils.ConvertRADecToAZAlt(adHome2000(0),adHome2000(1))
    objEngFile.WriteLine("Align (" & Now & "): Updating home position from Az = " & HomeAz & " Alt = " & HomeAlt & " to Az = " & AzAlt(0) & " Alt = " & AzAlt(1))
    
    Set objFSO = CreateObject("Scripting.FileSystemObject") 
    Set HomePosFile = objFSO.CreateTextFile("HomeAzAlt.txt") 
    HomePosFile.WriteLine AzAlt(0)
    HomePosFile.WriteLine AzAlt(1)
    HomePosFile.Close  

  End If

  objEngFile.WriteLine("Align (" & Now & "): Alignment complete in " & Round((Now - AlignStart)*86400) & " seconds")

End Sub