Function SunAlt

   SunAlt = -15   'If not sure, assume twilight (in range of skyflat)
   Dim cstart, state
   Dim xml : Set xml = CreateObject("MSXML2.ServerXMLHTTP")

   On Error Resume Next
       xml.open "GET", "http://www.winer.org/engRoof.html", aSynch
       xml.setRequestHeader "Content-Type", "application/x-www-form-urlencoded"
       xml.send

       Do
         xml.waitForResponse 1*1000
       Loop Until xml.readyState=4 Or Err.Number<>0

       'assume twilight if unknown
       If xml.readyState<>4 Or Err.Number<>0 Then
         xml.abort
         SunAlt = -15
         Exit Function
       End If
   On Error Goto 0

   If xml.Status = 200 Then
       return = xml.ResponseText

       cstart = InStr(return,"SunNow(Alt,Az): ") + 16
       cstart2 = InStr(cstart, return, ",")
       SunAlt = Cdbl(Mid(return,cstart,cstart2-cstart))

   End If  ' xml.Status block
   Set xml = Nothing

   msgbox(SunAlt)

End Function
