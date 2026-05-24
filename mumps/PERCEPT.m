PERCEPT ; Perceptual Modeling and Bayesian State Updates
        ;
        ; Implements stateful perceptual components like persistence,
        ; change detection, and Bayesian integration of multiple priors.
        ;
        ; Author: Jordan Lenchitz

        ; Leaky Integrator for persistence (Temporal Integration)
        ; ^F0TRACK("STATE","ENERGY",FREQ,"PERSIST") = current state
        ; VAL: New observation
        ; TAU: Time constant
        ; DT: Delta time
PERSIST(FREQ,VAL,TAU,DT) ;
        NEW ALPHA,PREV,STATE
        SET ALPHA=$$EXP^SCALES(-DT/TAU)
        SET PREV=$GET(^F0TRACK("STATE","ENERGY",FREQ,"PERSIST"),0)
        SET STATE=(ALPHA*PREV)+((1-ALPHA)*VAL)
        SET ^F0TRACK("STATE","ENERGY",FREQ,"PERSIST")=STATE
        QUIT STATE

        ; Change Detection (Rectified Positive Derivative)
        ; Detects onset of new spectral components
CHANGE(FREQ,VAL,TAU,DT) ;
        NEW SMOOTH,DIFF
        SET SMOOTH=$$PERSIST(FREQ,VAL,TAU,DT)
        SET DIFF=VAL-SMOOTH
        IF DIFF<0 SET DIFF=0
        SET ^F0TRACK("STATE","ENERGY",FREQ,"CHANGE")=DIFF
        QUIT DIFF

        ; Bayesian Update for a single frequency bin
        ; Integrates bottom-up measurement with top-down priors
        ; MEASLH: Measurement likelihood
        ; F0FAST: YIN-based pitch estimate
        ; RIDGE:  Wavelet-based ridge estimate
BUPDATE(FREQ,MEASLH,F0FAST,RIDGE) ;
        NEW ALPHA,BETA,FP,RP,PRIOR,COMB,POST
        ; Attentional weights (could be dynamic)
        SET ALPHA=0.6,BETA=0.3
        
        SET PRIOR=$GET(^F0TRACK("STATE","PRIOR",FREQ),0)
        
        ; Calculate Fast Prior (YIN) contribution (Gaussian window)
        SET FP=$$WINDOW(FREQ,F0FAST,15)
        
        ; Calculate Ridge Prior contribution
        SET RP=$$WINDOW(FREQ,RIDGE,10)
        
        ; Combine components into a Triadic Prior
        SET COMB=(ALPHA*FP)+(BETA*RP)+((1-ALPHA-BETA)*PRIOR)
        
        ; Apply likelihood (Measurement Update)
        SET POST=COMB*MEASLH
        
        ; Store posterior for next iteration
        SET ^F0TRACK("STATE","PRIOR",FREQ)=POST
        QUIT POST

        ; Gaussian Window helper for priors
        ; FREQ: target freq, CENTER: center freq, SIGMA: cents width
WINDOW(FREQ,CENTER,SIGMA) ;
        NEW DIFF,SLN,VAL
        IF CENTER<=0 QUIT 0
        SET SLN=SIGMA/1200
        SET DIFF=$$LN^SCALES(FREQ/CENTER)
        SET VAL=$$EXP^SCALES(-(DIFF*DIFF)/(2*SLN*SLN))
        QUIT VAL
