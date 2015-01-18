Sub QuitGuiding

  objEngFile.WriteLine("QuitGuiding (" & FormatDateTime(Now,3) & "): Halting the guider")

  'Kill The Guider Thread (more robust way?)
  strComputer = "."
  Set objWMIService = GetObject("winmgmts:" _
      & "{impersonationLevel=impersonate}!\\" & strComputer & "\root\cimv2")
  Set colProcessList = objWMIService.ExecQuery _
      ("SELECT * FROM Win32_Process WHERE Name = 'wscript.exe'")

  MostRecent = 0
  NProcesses = 0
  For Each objProcess in colProcessList
    If objProcess.CreationDate > MostRecent Then
      MostRecent = objProcess.CreationDate
    End If
    NProcesses = NProcesses + 1
  Next

  'Guider Never Started
  If NProcesses <= 1 Then
    Exit Sub
  End If

  For Each objProcess in colProcessList
    If objProcess.CreationDate = MostRecent Then
      objEngFile.WriteLine("QuitGuiding (" & FormatDateTime(Now,3) & "): Found " & NProcesses & " Processes; killing ProcessID " & objProcess.ProcessID )
      objProcess.Terminate()
    End If
  Next

End Sub