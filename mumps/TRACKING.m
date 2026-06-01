TRACKING ; Advanced Multi-F0 Tracking Logic in MUMPS
        ; This module implements frequency-domain proximity tracking
        ; and affordance state management.
        ;
        ; Author: Jordan Lenchitz

        ; Calculate distance between two frequencies
        ; In MUMPS, we'll use a simple ratio-based distance as a proxy for cents
        ; Dist(f1, f2) = |f1 - f2| / f1
DIST(F1,F2) NEW DIFF,RES
        SET DIFF=F1-F2
        IF DIFF<0 SET DIFF=-DIFF
        SET RES=DIFF/F1
        QUIT RES

        ; Find the best matching active track for a given frequency
        ; Returns TRACKID if found within tolerance, else 0
FINDMATCH(FREQ,TOL) NEW TRK,BESTTRK,BESTDIST,CURDIST,LASTF,STATE
        SET BESTTRK=0
        SET BESTDIST=TOL
        SET TRK=""
        FOR  SET TRK=$ORDER(^F0TRACK("TRACKS",TRK)) QUIT:TRK=""  DO
        . SET STATE=$GET(^F0TRACK("TRACKS",TRK,"STATE"),"ACTIVE")
        . IF STATE="TERMINATED" QUIT
        . ; Get last recorded frequency for this track
        . SET LASTF=$GET(^F0TRACK("TRACKS",TRK,"LASTF"))
        . IF LASTF="" QUIT
        . SET CURDIST=$$DIST(FREQ,LASTF)
        . IF CURDIST<BESTDIST DO
        . . SET BESTDIST=CURDIST
        . . SET BESTTRK=TRK
        QUIT BESTTRK

        ; Main process loop with linking logic
PROCESS NEW FRM,PIDX,DATA,FREQ,CONF,TOL,TRKID,NEXTID
        WRITE !,"Running Advanced MUMPS Tracking Logic...",!
        SET TOL=0.05 ; 5% frequency change tolerance (~80 cents)
        SET NEXTID=$GET(^F0TRACK("CONFIG","NEXTID"),1)
        
        SET FRM=""
        FOR  SET FRM=$ORDER(^F0TRACK("FRAME",FRM)) QUIT:FRM=""  DO
        . WRITE "  Frame ",FRM,":",!
        . SET PIDX=""
        . FOR  SET PIDX=$ORDER(^F0TRACK("FRAME",FRM,PIDX)) QUIT:PIDX=""  DO
        . . SET DATA=^F0TRACK("FRAME",FRM,PIDX)
        . . SET FREQ=$PIECE(DATA,"^",1)
        . . SET CONF=$PIECE(DATA,"^",2)
        . . 
        . . ; Try to match with existing track
        . . SET TRKID=$$FINDMATCH(FREQ,TOL)
        . . 
        . . IF TRKID=0 DO
        . . . ; Create new track
        . . . SET TRKID=NEXTID
        . . . SET NEXTID=NEXTID+1
        . . . WRITE "    New Voice Detected: Track ",TRKID," (",FREQ," Hz)",!
        . . 
        . . ; Update track
        . . SET ^F0TRACK("TRACKS",TRKID,FRM)=FREQ_"^"_CONF
        . . SET ^F0TRACK("TRACKS",TRKID,"LASTF")=FREQ
        . . SET ^F0TRACK("TRACKS",TRKID,"STATE")="ACTIVE"
        
        SET ^F0TRACK("CONFIG","NEXTID")=NEXTID
        WRITE "Tracking update complete.",!
        QUIT

        ; Affordance Field Logic
        ; Mark regions of spectral interest
AFFORD(TIME,FREQ,SAL) ;
        SET ^F0TRACK("AFFORDANCE",TIME,FREQ)=SAL
        IF SAL>0.8 WRITE "!!! High Affordance at ",TIME,"s / ",FREQ," Hz !!!",!
        QUIT

