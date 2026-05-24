JUSTINT ; Just Intonation Helpers in MUMPS
        ;
        ; Author: Jordan Lenchitz

        ; Calculate frequency from root and ratio (num/den)
CHORD(ROOT,NUM,DEN) ;
        QUIT ROOT*NUM/DEN

        ; Generate combination tones for two frequencies
COMBOS(F1,F2) NEW DIFF,C1,C2
        IF F1>F2 NEW TMP SET TMP=F1,F1=F2,F2=TMP
        ; Difference tone
        SET DIFF=F2-F1
        ; Cubic difference tones
        SET C1=(2*F1)-F2
        SET C2=(2*F2)-F1
        WRITE "Combination Tones for ",F1," and ",F2,":",!
        WRITE "  Difference: ",DIFF,!
        IF C1>0 WRITE "  Cubic 1:    ",C1,!
        IF C2>0 WRITE "  Cubic 2:    ",C2,!
        QUIT
