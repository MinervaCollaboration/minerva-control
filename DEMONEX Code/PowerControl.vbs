Function PowerControl(strDevice, TurnOn)

   strIP = "192.168.2.19"
   username = "admin"
   password = "12345678"

   If strDevice = "Mount" Then 
     port_id = "P63"
   ElseIf strDevice = "Camera" Then 
     port_id = "P61"
   ElseIf strDevice = "Guider" Then 
     port_id = "P62"
   ElseIf strDevice = "P60" or strDevice = "P61" or strDevice = "P62" or strDevice = "P63" Then
     port_id = strDevice
   Else
'     objEngFile.WriteLine("PowerControl (" & FormatDateTime(Now,3) & "): strDevice note valid: " & strDevice)
     PowerControl = -1 
     Exit Function
   End If

   If TurnOn Then 
     State = "1"
   Else
     State = "0"
   End If     

   'construct the URL to turn on/off the device
   strURL = "http://" & username & ":" & password & "@" & strIP &_
     "/Set.cmd?CMD=SetPower+" & port_id & "=" & State

'   objEngFile.WriteLine("PowerControl (" & FormatDateTime(Now,3) & "): strURL = " & strURL)

Set WshShell = WScript.CreateObject("WScript.Shell")
Set WshExec = WshShell.Exec("wget " & strURL)
WScript.Sleep 1000
Set objFSO = CreateObject("Scripting.FileSystemObject")
Filename = "C:\demonex\scripts\Set.cmd@CMD=SetPower+" & port_id & "=" & State
If objFSO.FileExists(Filename) Then objFSO.DeleteFile Filename, True
PowerControl=1
Exit Function


'WTF?! doesn't always work with XML
'   Set xml = CreateObject("MSXML2.XMLHTTP")
'set xml = CreateObject("Microsoft.XMLHTTP")
'   Set xml = CreateObject("MSXML2.ServerXMLHTTP")
'   Set xml = CreateObject("WinHttp.WinHttpRequest.5.1")
   Set xml = CreateObject("MSXML2.XMLHTTP.3.0")

   On Error Resume Next
       xml.open "GET", strURL, false
       xml.send()

       Do
         xml.waitForResponse 1*1000
       Loop Until xml.readyState=4 Or Err.Number<>0

   On Error Goto 0

   If xml.Status = 200 Then
       objEngFile.WriteLine("PowerControl (" & FormatDateTime(Now,3) & "): Status good; response = " & xml.ResponseText)

       return = xml.ResponseText

       'Make sure the port is on/off as desired
       cstart = InStr(return,port_id)
       port_status = Mid(return,cstart+4,1)   

       If port_status <> state Then
         objEngFile.WriteLine("PowerControl (" & FormatDateTime(Now,3) & "): Port not as desired, returning error. port_status = " & port_status)
         PowerControl = -1
         Exit Function
       End If
   Else
       objEngFile.WriteLine("PowerControl (" & FormatDateTime(Now,3) & "): Error sending URL, xml.Status = " & xml.Status)
       PowerControl = -1
       Exit Function
   End If  ' xml.Status block

   Set xml = Nothing
   PowerControl = 1

End Function