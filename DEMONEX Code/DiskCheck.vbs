Sub DiskCheck

'Get list of drives:
Set DriveList = objFSO.Drives

For Each DRV in DriveList
   Letter = DRV.DriveLetter
   DrvTyp = DRV.DriveType
   If ( DrvTyp = 2 ) Then
      Set Disk = objFSO.GetDrive(Letter)

      Total    = FormatNumber( Disk.TotalSize / 1000^3 , 0 )
      Free     = FormatNumber( Disk.FreeSpace / 1000^3 , 0 )
      Percent  = FormatNumber( 100 * Disk.FreeSpace / Disk.TotalSize , 0 )

      sSummary = UCase(Letter) & " " & Disk.VolumeName & ":" & vbCrLf &_
                 "Total Space: " & Total & " GB" & vbCrLf &_
                 "Free Space: " & Free & " GB (" & Percent & "%)" & vbCrLf
     If Letter = DataDrive and Free < 10 Then 
       strTo = StudentEmail
       strSubject = "Data Drive Full"
       Call Email(strTo,strSubject,sSummary,"","","")
     End If

     If Letter = BackupDrive and Free < 10 Then 
       strTo = StudentEmail
       strSubject = "Backup Drive Full"
       Call Email(strTo,strSubject,sSummary,"","","")
     End If

   End If

Next

End Sub