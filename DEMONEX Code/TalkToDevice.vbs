'///////////////////////////////////////////////////////////
'
' The TalkToDevice() function encapsulates all of the
' required serial port initialization, use and
' termination operations when sending a command to the
' telescope, as well as waits for the specified number of
' return characters for a specified time out interval.
' Tx - transmit string.
' Rx - receive string.
' RxLen - length of the string returned by the transmit command.
' TimeOutInSecs - The duration of time, in seconds,
'                 to wait for a response from the telescope.
'
'///////////////////////////////////////////////////////////

Function TalkToDevice(Tx, Rx, RxLen, TimeOutInSecs)
Const TUC_LOCKPORT=0
Const TUC_PURGE_TX=1
Const TUC_PURGE_RX=2
Const TUC_WRITE_STRING=3
Const TUC_GET_RX_BYTES_AVAILABLE=4
Const TUC_READ_STRING=5
Const TUC_UNLOCKPORT=6

Dim StrRet
Dim Start
Dim DidTimeout
Dim bIn
Dim bBytesAvailable

' Lock the port...
strRet = objTel.DoCommand(TUC_LOCKPORT,"")

' Purge the transmit buffer...
strRet = objTel.DoCommand(TUC_PURGE_TX,"")

' Purge the receive buffer...
strRet = objTel.DoCommand(TUC_PURGE_RX,"")

' Send the command to the telescope...
strRet = objTel.DoCommand(TUC_WRITE_STRING,Tx)
 
' Wait for a response...
Start = Now

do

  ' Get the number of characters (bytes) to be read from the port...
  strRet = objTel.DoCommand(TUC_GET_RX_BYTES_AVAILABLE,"")
  bIn = CLng(strRet)

  if (bIn>=RxLen) Then
    bBytesAvailable = True
  else
    bBytesAvailable = False
  end if

  if ((Now-Start)*86400 >TimeOutInSecs) then
    DidTimeout = True
  else
    DidTimeout = false
  end if

loop while (Not bBytesAvailable And Not DidTimeout)

' Read the specified number of characters from the port...
Rx = objTel.DoCommand(TUC_READ_STRING,CStr(RxLen))

' Done with port, unlock it...
strRet = objTel.DoCommand(TUC_UNLOCKPORT,"")

End Function