  'Must have GPS disabled; assumes ungraceful (not parked) shutdown.

  Set objFSO = CreateObject("Scripting.fileSystemObject")
  Set objFile = objFSO.OpenTextFile("PowerControl.vbs", 1)
  Execute objFile.ReadAll()

  Status = PowerControl("Mount",True)
  msgbox(status)
  Status = PowerControl("Mount",False)
  msgbox(status)

  Status = PowerControl("Camera",True)
  msgbox(status)
  Status = PowerControl("Camera",False)
  msgbox(status)

  Status = PowerControl("Guider",True)
  msgbox(status)
  Status = PowerControl("Guider",False)
  msgbox(status)