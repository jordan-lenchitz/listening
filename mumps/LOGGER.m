LOGGER  ; Structured Event Logger for Tracking History
        ;
        ; Author: Jordan Lenchitz

LOG(EVT,DATA) ;
        NEW TS,ID
        SET TS=$ZTIMESTAMP
        SET ID=$INCREMENT(^F0TRACK("LOG",TS))
        SET ^F0TRACK("LOG",TS,ID)=EVT_"|"_DATA
        QUIT

DUMP    ; Dump log to terminal
        NEW TS,ID,DATA
        SET TS=""
        FOR  SET TS=$ORDER(^F0TRACK("LOG",TS)) QUIT:TS=""  DO
        . SET ID=""
        . FOR  SET ID=$ORDER(^F0TRACK("LOG",TS,ID)) QUIT:ID=""  DO
        . . SET DATA=^(ID)
        . . WRITE TS," [",ID,"] ",$PIECE(DATA,"|",1),": ",$PIECE(DATA,"|",2),!
        QUIT
