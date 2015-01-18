Function GetIndex(objName)

     Dim objFSO, colFiles, strFolder

     Set objFSO = CreateObject("Scripting.FileSystemObject")
     Set objFolder = objFSO.GetFolder(datadir)
     Set colFiles = objFolder.Files

     strExt = ".fits"
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