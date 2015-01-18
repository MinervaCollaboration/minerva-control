Sub imStat(strFilename, mean, median, mode, min, max, sum)

  Set ObjWS = WScript.CreateObject("WScript.Shell")
  ObjWS.Run "C:\cfitsio\my_imstat.exe " & strFilename,0,1
  Set objFile = objFSO.OpenTextFile("C:\demonex\scripts\fileio.txt")

  mean = Cdbl(objFile.ReadLine)
  median = Cdbl(objFile.ReadLine)
  mode = Cdbl(objFile.ReadLine)
  min = Cdbl(objFile.ReadLine)
  max = Cdbl(objFile.ReadLine)
  sum = Cdbl(objFile.ReadLine)

End Sub