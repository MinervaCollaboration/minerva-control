Sub DoDark(Ndark,ExpTime)

  Const Dark = 3
  objCam.ExposureTime = ExpTime
  objCam.Frame = Dark
  objName = "dark"
  
  For i=1 to Ndark
    objCam.TakeImage 

    'Rename the image to something reasonable
    'filename of the image -- nYYYYMMDD.objName.####.fits
    strFileName = "n" & night & "." & objName & "." & GetIndex(objName) & ".fits"
    objEngFile.WriteLine("DoDark (" & FormatDateTime(Now,3) & "): Renaming file from " &_
      objCam.LastImageFileName & " to " & strFileName)
    objFSO.MoveFile datadir & objCam.LastImageFileName, datadir & strFileName

    'Write to the Log
    Call WriteLog
  
  Next

End Sub
