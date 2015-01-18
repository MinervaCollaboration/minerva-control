Const ForReading = 1
Const ForWriting = 2
Const ForAppending = 8
Set objFSO = CreateObject("Scripting.fileSystemObject")
Set objFile = objFSO.OpenTextFile("../Email.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("../jd.vbs", ForReading)
Execute objFile.ReadAll()
night = "20090127"
PIEmail = "gaudi@astronomy.ohio-state.edu"
CuratorEmail = "winer.obs@gmail.com,pat.trueblood@gmail.com,mtrueblood@noao.edu"
StudentEmail = "jdeast@astronomy.ohio-state.edu"
EmergencyTxt = "6178403045@txt.att.net"
NotEmailed = True

'Function RoofOpen()
   RoofOpen = False   ' False means not open

   Dim cstart, state
   Dim xml : Set xml = CreateObject("MSXML2.ServerXMLHTTP")

   On Error Resume Next
       xml.open "GET", "http://www.winer.org/roof.html", aSynch
       xml.setRequestHeader "Content-Type", "application/x-www-form-urlencoded"
       xml.send

       Do
         xml.waitForResponse 1*1000
       Loop Until xml.readyState=4 Or Err.Number<>0

       'assume roof is open if unknown
       If xml.readyState<>4 Or Err.Number<>0 Then
         xml.abort
         RoofOpen = True
         MsgBox("RoofOpen (" & FormatDateTime(Now,3) & "): Error: cannot connect to http://www.winer.org/roof.html, assuming roof is open")

'         Exit Function
       End If
   On Error Goto 0

   If xml.Status = 200 Then
       return = xml.ResponseText


      'Make sure the page is current
       cstart = InStr(return,"LASTUPDATED")
       If cstart=0 Then
           MsgBox("RoofOpen (" & FormatDateTime(Now,3) & "): Error: cannot find 'LASTUPDATED' tag, assuming roof is open")
           RoofOpen = True
       End If 
  
       cstart2 = InStr(cstart, return, " >")
       jdLastUpdated = Mid(return,cstart+13,cstart2-cstart-13)       
       jdNow = jd(Year(Now),Month(Now),Day(Now),Hour(Now),Minute(Now),Second(Now)) + 0.5

       If ((jdNow - jdLastUpdated)*1440) > 10 Then
           MsgBox("RoofOpen (" & FormatDateTime(Now,3) & "): Error: page not updated for " & ((jdNow - jdLastUpdated)*1440) & " minutes; emailing and assuming roof is OPEN")
           RoofOpen = True
           If NotEmailed Then
             Call Email(curatoremail & "," & studentEmail & ",pnd@noao.edu",_
                        "obsDaemon Down","Phil," & vbCrLf & vbCrLf &_
                        "The obsDaemon last updated the roof page " &_
                        Round((jdNow - jdLastUpdated)*1440,2) &_
                        " minutes ago, can you please check it out for me?" &_
                        vbCrLf & vbCrLf & "Love," & vbCrLf & "DEMONEX","","","") 
              NotEmailed = False
            End If
'            Exit Function
       End If

       cstart = InStr(return,"ROOFSTATE")
       If cstart=0 Then ' assume roof is open
           RoofOpen = True
           MsgBox("RoofOpen (" & FormatDateTime(Now,3) & "): Error: cannot find 'ROOFSTATE' tag, assuming roof is open")
'           Exit Function
       End If

       cstart2 = InStr(cstart, return, " >")
       state = Mid(return,cstart+10,cstart2-cstart-10)

       If state = "OPENING" or state="CLOSING" or state="CLOSED" Then

           if InStr(return,"STUCK?") <> 0 Then
             Call Email("jdeast@astronomy.ohio-state.edu",_
                        "Roof state n" & night & ": STUCK?","Mark and Pat," & vbCrLf & vbCrLf &_
                        "The roof is stuck, can you please check it out for me?" &_
                        vbCrLf & vbCrLf & "Love," & vbCrLf & "DEMONEX","","","")
             MsgBox("RoofOpen (" & FormatDateTime(Now,3) & "): Roof is stuck, not taking exposures")   
           Else
             RoofOpen = False
             MsgBox("RoofOpen (" & FormatDateTime(Now,3) & "): Roof is " & state & ", not taking exposures")                  
           End if

         Elseif state = "OPEN" Then
           RoofOpen = True
         Else
           'Unknown roof state, assuming open
           MsgBox("RoofOpen (" & FormatDateTime(Now,3) & "): Unrecognized roof state (" & state & "), assuming roof is open")

           Call Email("jdeast@astronomy.ohio-state.edu",_
                      "Roof state n" & night & ": " & state,"Mark and Pat," & vbCrLf & vbCrLf &_
                      "I've detected an unrecognized roof state (" & state & "). Can you please check it out for me?" &_
                      vbCrLf & vbCrLf & "Love," & vbCrLf & "DEMONEX","","","")

           RoofOpen = True
       End If

   End If  ' xml.Status block
   Set xml = Nothing

'End Function
