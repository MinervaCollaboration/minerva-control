'Acquire the object and set up the initial exposure time

Sub Point(ra,dec,ExpTime)
 
  TelAsych = objTel.Asynchronous
  CamAsych = objCam.Asynchronous

  objTel.Asynchronous = 1
  objCam.Asynchronous = 1

  'Slew Telescope
  objEngFile.WriteLine("Point (" & Now & "): Slewing to " & objName & " " & ra & " " & dec )
  CheckTel
  Call objTel.SlewToRaDec(ra,dec,objName)
  objEngFile.WriteLine("Point (" & Now & "): Slew Completed in " & Round((Now - slewStart)*86400) & " seconds")

  Do While (Not Cbool(objTel.IsSlewComplete))
    CheckTel
  Loop

  Do While (Not Good)

    'TakeImage
    objEngFile.WriteLine("Point (" & Now & "): Taking image")
    objCam.TakeImage
          
    Do While (Not Cbool(objTel.IsSlewComplete) or Not CBool(objCam.IsExposureComplete))
      CheckTel
    Loop

    'Get the coordinate solution
    Call objTheSky.ImageLink(0.75,ra,dec)

    If Err.Number = 0 Then
      Good = True
    End If
  Loop

  objTel.Asynchronous = TelAsych
  objCam.Asynchronous = CamAsych

End Sub