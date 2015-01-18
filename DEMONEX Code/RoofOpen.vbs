Function RoofOpen()

   RoofOpen = False   ' False means not open

   Dim cstart, state
   Dim xml : Set xml = CreateObject("MSXML2.ServerXMLHTTP")

   On Error Resume Next
       xml.open "GET", "http://192.168.2.1/roof.html", aSynch
       xml.setRequestHeader "Content-Type", "application/x-www-form-urlencoded"
       xml.send

       Do
         xml.waitForResponse 1*1000
       Loop Until xml.readyState=4 Or Err.Number<>0

       'assume roof is open if unknown
       If xml.readyState<>4 Or Err.Number<>0 Then
         xml.abort
         RoofOpen = True
         objEngFile.WriteLine("RoofOpen (" & FormatDateTime(Now,3) & "): Error: cannot connect to http://www.winer.org/roof.html, assuming roof is open")
         Exit Function
       End If
   On Error Goto 0

   If xml.Status = 200 Then
       return = xml.ResponseText       

      'Make sure the page is current
       cstart = InStr(return,"LASTUPDATED")
       If cstart=0 Then
           objEngFile.WriteLine("RoofOpen (" & FormatDateTime(Now,3) & "): Error: cannot find 'LASTUPDATED' tag, assuming roof is open")
           RoofOpen = True
           Exit Function
       End If 
  
       cstart2 = InStr(cstart, return, ">")
       jdLastUpdated = Mid(return,cstart+13,cstart2-cstart-13)       
       jdNow = jd(Year(Now),Month(Now),Day(Now),Hour(Now),Minute(Now),Second(Now)) + 0.5

       objEngFile.WriteLine("RoofOpen (" & FormatDateTime(Now,3) & "): roof page last updated " & ((jdNow - jdLastUpdated)*1440) & " minutes ago")


       If ((jdNow - jdLastUpdated)*1440) > 5 Then
           RoofOpen = True
           objEngFile.WriteLine("RoofOpen (" & FormatDateTime(Now,3) & "): Error: page not updated for " & ((jdNow - jdLastUpdated)*1440) & " minutes; emailing and assuming roof is OPEN")
           If NotEmailedDaemon Then
'             Call Email(curatoremail & "," & studentEmail ,_
             Call Email(studentEmail ,_
                        "obsDaemon Down","Mark and Pat," & vbCrLf & vbCrLf &_
                        "The obsDaemon last updated the roof page " &_
                        Round((jdNow - jdLastUpdated)*1440,2) &_
                        " minutes ago, can you please check it out for me?" &_
                        vbCrLf & vbCrLf & "Love," & vbCrLf & "DEMONEX","","","") 
              NotEmailedDaemon = False
            End If
            Exit Function
       Else
         If Not NotEmailedDaemon Then
           NotEmailedDaemon = True
'           Call Email(curatoremail & "," & studentEmail ,_
           Call Email(studentEmail ,_
           	        "obsDaemon Back Up","Mark and Pat," & vbCrLf & vbCrLf &_
                        "The obsDaemon is back online and last updated the roof page " &_
                        Round((jdNow - jdLastUpdated)*1440,2) &_
                        " minutes ago." &_
                        vbCrLf & vbCrLf & "Love," & vbCrLf & "DEMONEX","","","") 
         End If
       End If

       cstart = InStr(return,"ROOFSTATE")
       If cstart=0 Then
           objEngFile.WriteLine("RoofOpen (" & FormatDateTime(Now,3) & "): Error: cannot find 'ROOFSTATE' tag, assuming roof is open")
           RoofOpen = True
           Exit Function
       End If

       cstart2 = InStr(cstart, return, " >")
       state = Mid(return,cstart+10,cstart2-cstart-10)

       If state="CLOSED" or state="PANIC" Then
           objEngFile.WriteLine("RoofOpen (" & FormatDateTime(Now,3) & "): Roof is " & state)
           RoofOpen = False
           NotEmailed = True
           RoofMovingTime = 0                 
       Elseif state="OPEN" or state="MANUAL" Then
           objEngFile.WriteLine("RoofOpen (" & FormatDateTime(Now,3) & "): Roof is " & state) 
           RoofOpen = True
           NotEmailed = True
           RoofMovingTime = 0
       Elseif state="OPENING" or state="CLOSING" Then
           objEngFile.WriteLine("RoofOpen (" & FormatDateTime(Now,3) & "): Roof is " & state)
           RoofOpen = False
           If RoofMovingTime = 0 Then 
             RoofMovingTime = Now
           End If
           If (Now - RoofMovingTime) > 40/1440 Then
             If NotEmailed Then
               StrTo = CuratorEmail & "," & StudentEmail
               Call Email(StrTo,_
                          "Roof state n" & night & ": " & state,"Mark and Pat," & vbCrLf & vbCrLf &_
                          "The roof is stuck, can you please check it out for me?" &_
                          vbCrLf & vbCrLf & "Love," & vbCrLf & "DEMONEX","","","")
               NotEmailed = False  
             End If
             objEngFile.WriteLine("RoofOpen (" & FormatDateTime(Now,3) & "): Roof is stuck, not taking exposures")     
           End If
       Elseif state="STUCK" Then
           If NotEmailed Then
             StrTo = CuratorEmail & "," & StudentEmail
             Call Email(StrTo,_
                        "Roof state n" & night & ": " & state,"Mark and Pat," & vbCrLf & vbCrLf &_
                        "The roof is stuck, can you please check it out for me?" &_
                        vbCrLf & vbCrLf & "Love," & vbCrLf & "DEMONEX","","","")
             NotEmailed = False  
           End If
           RoofOpen = False
           objEngFile.WriteLine("RoofOpen (" & FormatDateTime(Now,3) & "): Roof is stuck, not taking exposures") 
       Else
           If NotEmailed Then
             StrTo = CuratorEmail & "," & StudentEmail
             Call Email(StrTo,_
                        "Roof state n" & night & ": " & state,"Mark and Pat," & vbCrLf & vbCrLf &_
                        "I've detected an unrecognized roof state (" & state & "). Can you please check it out for me?" &_
                        vbCrLf & vbCrLf & "Love," & vbCrLf & "DEMONEX","","","")
             NotEmailed = False
           End If
           RoofOpen = True
           objEngFile.WriteLine("RoofOpen (" & FormatDateTime(Now,3) & "): Unrecognized roof state (" & state & "), assuming roof is open")
       End If

   End If  ' xml.Status block
   Set xml = Nothing

End Function
