F0TRACK ; Multi-F0 Tracker Database Backend in ANSI MUMPS for YottaDB
        ; This module implements the state management and tracking data
        ; structures using MUMPS globals, ideal for persistent hierarchical data.
        ;
START   WRITE !,"Initializing A Cappella Tracker Database in YottaDB...",!
        KILL ^F0TRACK
        SET ^F0TRACK("CONFIG","MAX_VOICES")=8
        SET ^F0TRACK("CONFIG","MIN_FREQ")=65
        SET ^F0TRACK("CONFIG","MAX_FREQ")=1400
        SET ^F0TRACK("STATE")="READY"
        WRITE "Tracker Configuration Stored in ^F0TRACK Global.",!
        QUIT

ADDPITCH(TRACKID,FRAME,FREQ,CONF) ; Add a pitch observation to a track
        ; ^F0TRACK("TRACKS", track_id, frame_id) = frequency ^ confidence
        SET ^F0TRACK("TRACKS",TRACKID,FRAME)=FREQ_"^"_CONF
        WRITE "Added pitch ",FREQ," Hz to Track ",TRACKID," at Frame ",FRAME,!
        QUIT

TERMINAT(TRACKID) ; Mark a track as terminated
        SET ^F0TRACK("TRACKS",TRACKID,"STATE")="TERMINATED"
        WRITE "Track ",TRACKID," terminated.",!
        QUIT

REPORT  ; Print summary of all tracked voices
        NEW TRK,FRM,DATA,STATE
        WRITE !,"--- YOTTADB MULTI-F0 TRACKING REPORT ---",!
        SET TRK=""
        FOR  SET TRK=$ORDER(^F0TRACK("TRACKS",TRK)) QUIT:TRK=""  DO
        . WRITE "Voice Track ",TRK
        . SET STATE=$GET(^F0TRACK("TRACKS",TRK,"STATE"),"ACTIVE")
        . WRITE " (",STATE,"):",!
        . SET FRM=""
        . FOR  SET FRM=$ORDER(^F0TRACK("TRACKS",TRK,FRM)) QUIT:FRM=""  DO
        . . IF FRM="STATE" QUIT  ; Skip state metadata node
        . . SET DATA=^F0TRACK("TRACKS",TRK,FRM)
        . . WRITE "  Frame ",FRM," -> Freq: ",$PIECE(DATA,"^",1)," Hz, Conf: ",$PIECE(DATA,"^",2),!
        WRITE "--- END OF REPORT ---",!
        QUIT
