SCALES ; Frequency Scale Conversions in MUMPS
        ;
        ; This module provides essential mathematical transforms for 
        ; auditory frequency scales (ERB, Cents, MIDI).
        ;
        ; Author: Jordan Lenchitz

        ; Freq to ERB (Equivalent Rectangular Bandwidth)
        ; Reference: Glasberg and Moore (1990)
        ; erb(f) = 24.7 * (1 + 4.37 * f / 1000)
ERB(F)  QUIT 24.7*(1+(4.37*F/1000))

        ; Calculate distance in Cents between two frequencies
        ; Cents = 1200 * log2(f2/f1)
CENTS(F1,F2) NEW RES
        IF F1=0!(F2=0) QUIT 0
        ; log2(x) = ln(x) / ln(2)
        SET RES=1200*($ZLOG(F2/F1)/$ZLOG(2))
        IF RES<0 SET RES=-RES
        QUIT RES

        ; Convert frequency to nearest MIDI note number
MIDI(F) NEW RES
        IF F<=0 QUIT 0
        SET RES=69+(12*($ZLOG(F/440)/$ZLOG(2)))
        QUIT $FNUMBER(RES,"",0)

        ; Natural Logarithm (Proxy if $ZLOG not standard, but YottaDB has it)
LN(X)   QUIT $ZLOG(X)

        ; Exponential
EXP(X)  QUIT $ZEXP(X)
