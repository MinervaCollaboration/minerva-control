Sub DoBias(Nbias)

  Const Bias = 2
  CheckCam
  objCam.ExposureTime = 0
  objCam.Frame = Bias
  objName = "bias"

  For i=1 to Nbias
    objCam.TakeImage

    'Rename the image to something reasonable
    'filename of the image -- nYYYYMMDD.objName.####.fits
    strFileName = "n" & night & "." & objName & "." & GetIndex(objName) & ".fits"
    objEngFile.WriteLine("DoBias (" & FormatDateTime(Now,3) & "): Renaming file from " &_
    objCam.LastImageFileName & " to " & strFileName)
    objFSO.MoveFile datadir & objCam.LastImageFileName, datadir & strFileName

    'Write to the Log
    Call WriteLog
  Next

End Sub
