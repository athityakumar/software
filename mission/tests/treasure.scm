(include "peacock-prelude")
(use posix)

(peacock "New Peacock Test"
  (setup
    (define timeout 90)
    (define table-depth 4.0)
    ; XXX not a flonum if table-depth used?
    (define table-pos #(2 -2 4))
    (define doubloon-depth 4.0)
    ; XXX not a flonum if doubloon-depth used?
    (define doubloon-pos #(2 -3 4))
    (define tower-pos #(2 -3 4))
    (define x1-pos #(2.5 -2 4))
    (vehicle-set!
      x: #(0 0 0.4)
      )

    (note "Beginning treasure test.")
    (>>= (after timeout) (lambda (_) (fail "Timed out.")))
    ;(>>= (when 'kalman.depth kalman.depth-ref (lambda (val) (< val 0.1))) (lambda (_) (fail "Surfaced, oh no!")))

    (camera downward
      q: (hpr->quat (vector 0 (- (/ pi 2)) 0))
      x: #(0 0 0)
      w: 1024 h: 768)

    (camera forward
      q: (hpr->quat (vector 0 0 0))
      w: 1020 h: 1020 f: 440)

    (goals win)

    (shape downward >> tower
      (recovery-results.tower-downward-area-set!
       recovery-results.tower-downward-center-x-set!
       recovery-results.tower-downward-center-y-set!)
      x: tower-pos r: 2.0
    )

    (shape downward >> doubloon
      (recovery-results.doubloon-1-probability-set!
       recovery-results.doubloon-1-x-set!
       recovery-results.doubloon-1-y-set!)
      x: doubloon-pos r: 1.0
      xattrs: '(("render". "gold_doubloon"))
    )

    (shape downward >> table
      ((lambda (_) 1)
       recovery-results.table-center-x-set!
       recovery-results.table-center-y-set!)
      q: (hpr->quat (vector 0 0 (/ pi -2)))
      x: table-pos r: 10.0
      xattrs: '(("render". "doubloon_table"))
      f: (lambda (x y r d)
               (recovery-results.table-area-set! (inexact->exact (round (* r r))))
               (list x y r d))
    )

    (shape downward >> x1
      ((lambda (_) 1)
       recovery-results.first-mark-x-set!
       recovery-results.first-mark-y-set!)
      q: (hpr->quat (vector 0 0 (/ pi -2)))
      x: x1-pos r: 5.0
    )

    (define doubloon-stream downward>>doubloon)

    (>>= (on 'kalman.depth kalman.depth-ref
           (lambda (val) (> val doubloon-depth)))
           (lambda (_)
             (note "Dove to first doubloon!")
             (camera-stream-off! doubloon-stream)

         (on 'kalman.depth kalman.depth-ref
           (lambda (val) (< val 0))))
           (lambda (_)
             (note "Surfaced with doubloon!")
             (recovery-results.first-mark-score-set! 1000)

         (on 'kalman.north kalman.north-ref
           (lambda (val) (and (< val 3) (> val 2.3) (< (kalman.east-ref) -1.5) (> (kalman.east-ref) -2.5)))))
           (lambda (_)
             (note "Centered on table X.")

         (on 'actuator-desires.trigger-03 actuator-desires.trigger-03-ref
           (lambda (val) val)))
           (lambda (_)
             (sleep 2)
             (bowl:eset doubloon 'x x1-pos)
             (camera-stream-on! doubloon-stream)
             (complete win))

  ))

  (mission
    module: "recovery"
    task: "mission")

  (options
    debug: #t)
  )

; vim: set lispwords+=peacock,vehicle,entity,camera,camera-stream,shape,collision :
