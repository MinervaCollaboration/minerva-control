Function Reverse( myarray )

  Dim i, idxLast
  idxLast = UBound( myarray )
  redim ReversedArray(idxLast)

  For i = 0 To idxLast
    ReversedArray(i) = myarray(idxLast - i)
  Next

  Reverse = ReversedArray

End Function