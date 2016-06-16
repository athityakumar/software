; Miscellaneous Peacock Utilities / Functions

(module peacock-misc (
  on
  vary-get
  vary-set
    )

  (import scheme chicken)
  (use raisin cuauv-shm fishbowl (prefix random-mtzig rnd:))
  (use extras)

  (use srfi-18 srfi-69)
  (use matchable)

  (import peacock)  

  ;; Deferred that becomes determined when the specified reference matches the specified condition, filled with the value of the specified reference at the time of condition fulfillment.
  ;; Note: SHM variables are consistently named; there should be some way to quote-splice this.
  (define (on name name-ref func)
    (begin
      (define var (new-ivar))
      (define (wait-inner)
        (>>= (changed name)
          (lambda (_) 
            (let ([current (name-ref)])
              (if (func current)
                (begin
                  (ivar-fill! var current)
                  (return 0))
                (wait-inner)
                )   
              )   
            )   
          )   
        )   
      (begin
        (wait-inner)
        (ivar-read var)
        )   
      )   
    )

  (define rnd-st (rnd:init))

  (define (vary-get name-ref sigma)
    (define (get)
      (let ((val (name-ref)) (rval (rnd:randn! rnd-st)))
        (+ val (* sigma rval))
      )
    )
    (lambda () (get))
  )

  (define (vary-set name-ref sigma)
    (define (set val)
      (let ((rval (rnd:randn! rnd-st))) 
        (name-ref (+ val rval))
      )
    )
    (lambda (val) (set val))
  )

  (define (rgauss mu sig)
    (+ mu (* sig (rnd:randn! rnd-st)))
  )

  )
