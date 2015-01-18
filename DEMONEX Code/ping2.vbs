On Error Resume Next

Dim strTarget, strPingResults


Set WshShell = WScript.CreateObject("WScript.Shell")

Const ForAppending = 8

Set objFSO = CreateObject("Scripting.fileSystemObject")
iter = 1

Do While True

  Set WshExec = WshShell.Exec("ping -n 3 -w 2000 google.com")
  strPingResults = LCase(WshExec.StdOut.ReadAll)
  Set objPingFile = objFSO.OpenTextFile("C:\demonex\share\ping.txt", ForAppending)

  If InStr(strPingResults, "reply from") Then
    objPingFile.WriteLine(Now & " 1") 
    objPingFile.Close
    WScript.Sleep 58000
  Else
    Set WshExec = WshShell.Exec("ping -n 3 -w 2000 cnn.com")
    strPingResults = LCase(WshExec.StdOut.ReadAll)
    If InStr(strPingResults, "reply from") Then
      objPingFile.WriteLine(Now & " 2")  
    Else
      objPingFile.WriteLine(Now & " 0") 
    End If
    objPingFile.Close
    WScript.Sleep 56000
  End If

  iter = iter+1

Loop


