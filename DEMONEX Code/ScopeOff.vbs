Sub ScopeOff

  objEngFile.WriteLine("ScopeOff (" & FormatDateTime(Now,3) & "): Turning off the Scope")
  Status = PowerControl("Mount",False)
  objEngFile.WriteLine("ScopeOff (" & FormatDateTime(Now,3) & "): Status = " & Status)

End Sub