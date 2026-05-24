ASA     ; Auditory Scene Analysis - Global Manager
        ;
        ; The "Ecological High-Level" of the tracker.
        ; Manages schemas, group formation, and attentional affordances.
        ;
        ; Author: Jordan Lenchitz

        ; Initialize a new listening session
INIT(ID) ;
        NEW CFG
        SET CFG="^F0TRACK(""SESSIONS"","_ID_")"
        SET @CFG@("STATUS")="INITIALIZING"
        SET @CFG@("START_TIME")=$HOROLOG
        SET @CFG@("AFFORDANCE_COUNT")=0
        WRITE "Session ",ID," initialized.",!
        QUIT

        ; Record a spectral affordance (structurally supported perception)
AFFORD(ID,TIME,FREQ,SAL,TYPE) ;
        NEW NODE,COUNT
        SET COUNT=$INCREMENT(^F0TRACK("SESSIONS",ID,"AFFORDANCE_COUNT"))
        SET NODE="^F0TRACK(""SESSIONS"","_ID_",""AFFORDANCES"","_COUNT_")"
        SET @NODE@("TIME")=TIME
        SET @NODE@("FREQ")=FREQ
        SET @NODE@("SAL")=SAL
        SET @NODE@("TYPE")=TYPE ; e.g., "GHOST", "OVERTONE", "SUNG"
        
        IF SAL>0.9 DO
        . WRITE "!!! Schema Match: ",TYPE," at ",FREQ," Hz detected !!!",!
        QUIT

        ; Group multiple tracks into a single "Source" or "Object"
GROUP(ID,TRACKS) ;
        NEW GID,I,TRK
        SET GID=$INCREMENT(^F0TRACK("SESSIONS",ID,"GROUPS"))
        FOR I=1:1:$LENGTH(TRACKS,"^") DO
        . SET TRK=$PIECE(TRACKS,"^",I)
        . SET ^F0TRACK("SESSIONS",ID,"GROUPS",GID,"TRACKS",TRK)=""
        WRITE "Formed Auditory Object ",GID," from tracks: ",TRACKS,!
        QUIT