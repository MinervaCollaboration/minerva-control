'Connect to TheSky
Set objTheSky = WScript.CreateObject("TheSky6.RASCOMTheSky")
objTheSky.Connect()

'Connect to the Telescope
Set objTel = WScript.CreateObject("TheSky6.RASCOMTele")
objTel.Connect()

'Connect to the Camera
Set objCam = CreateObject("CCDSoft.Camera")
objCam.Connect()

steps = 20
maxcounts = 65535
mincounts = 0
cntspersec = 175
Set objFSO = CreateObject("Scripting.fileSystemObject")
path = "C:\demonex\lab3\"
objName = "gain"

For i=1 to steps
   exptime = (maxcounts-mincounts)*i/steps/cntspersec
   objCam.ExposureTime = exptime

   'take two flats
   objCam.Frame = 1
   objCam.TakeImage
   strFileName = objName & "." & GetIndex & ".fits"
   objFSO.MoveFile path & objCam.LastImageFileName, path & strFileName
   objCam.TakeImage
   strFileName = objName & "." & GetIndex & ".fits"
   objFSO.MoveFile path & objCam.LastImageFileName, path & strFileName

   'take a dark
   objCam.Frame = 3
   objCam.TakeImage
   strFileName = objName & "." & GetIndex & ".fits"
   objFSO.MoveFile path & objCam.LastImageFileName, path & strFileName  

   'take constant exposure time image for baseline
   objCam.Frame = 1
   objCam.ExposureTime = (maxcounts-mincounts)/(2*cntspersec)
   objCam.TakeImage
   strFileName = objName & "." & GetIndex & ".fits"
   objFSO.MoveFile path & objCam.LastImageFileName, path & strFileName  

Next

Function GetIndex()
     Dim objFSO, folder, colFiles, strFolder
     strExt = ".fits"

     Set objFSO = CreateObject("Scripting.FileSystemObject")
     Set objFolder = objFSO.GetFolder(path)
     Set colFiles = objFolder.Files

     dtmNewestDate = Now - 10000
     objFileFound = False
     For each objFile In colFiles
        objNamePos = InStr(objFile,objName)
        objExtPos = InStr(objFile,strExt)
        If objNamePos <> 0 and objExtPos <> 0 Then
  	  If objFile.DateCreated > dtmNewestDate Then
            dtmNewestDate = objFile.DateCreated
            strNewestFile = objFile.Path
            objNewestExt = objExtPos
            objFileFound = True
          End If
        End If
     Next

     If Not objFileFound Then
        GetIndex = "0001"
     Else
        objExtPos = InStr(strNewestFile,strExt)
        objIndex = Mid(strNewestFile, objExtPos-4,4)+1
        GetIndex = Right(string(4,"0") & objIndex, 4)
     End If
End Function