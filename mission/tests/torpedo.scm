(include "peacock-prelude")

(peacock "New Peacock Test"
  (setup
    (define timeout 300)
    (define torpedos-pos #(1 0 2))

    ; The 4 holes
    (define tl-pos #(1 -0.4 1.6))
    (define tr-pos #(1 0.4 1.6))
    (define bl-pos #(1 -0.4 2.4))
    (define br-pos #(1 0.4 2.4))
    (define hole-radius 0.1)

    (define torpedo-trigger 'actuator-desires.trigger-01)

    (vehicle-set!
      x: #(-1 0 0.4)
      )

    (note "Beginning single-hole torpedo test.")
    (>>= (after timeout) (lambda (_) (fail "Timed out.")))
    (>>= (on 'kalman.depth kalman.depth-ref (lambda (val) (< val 0.1))) (lambda (_) (fail "Surfaced, oh no!")))

    (camera forward
      q: (hpr->quat (vector 0 0 0))
      w: 512 h: 512 f: 440)

    (goals win)

    (shape forward >> board
      (torpedoes-results.board-prob-set!
       torpedoes-results.board-center-x-set!
       torpedoes-results.board-center-y-set!)
      x: torpedos-pos r: 1.3
      q: (hpr->quat (vector (* 3 (/ pi 2)) (/ pi 2) 0))
      xattrs: '(("render". "torpedo_board"))
      ; TODO Add this functionality is as an arugment to shape directly!
      f: (lambda (x y r d)
               (torpedoes-results.board-height-set! (inexact->exact (round (* 2 r))))
               (list x y r d))
    )

    (shape forward >> top_left
      ((lambda (_) 1)
       torpedoes-cutout-top-left.x-set!
       torpedoes-cutout-top-left.y-set!)
      x: tl-pos r: hole-radius
      q: (hpr->quat (vector (* 3 (/ pi 2)) (/ pi 2) 0))
      xattrs: '(("render". "torpedo_cover"))
    )

    (shape forward >> top_right
      ((lambda (_) 1)
       torpedoes-cutout-top-right.x-set!
       torpedoes-cutout-top-right.y-set!)
      x: tr-pos r: hole-radius
    )

    (shape forward >> bottom_left
      ((lambda (_) 1)
       torpedoes-cutout-bottom-left.x-set!
       torpedoes-cutout-bottom-left.y-set!)
      x: bl-pos r: hole-radius
    )

    (shape forward >> bottom_right
      ((lambda (_) 1)
       torpedoes-cutout-bottom-right.x-set!
       torpedoes-cutout-bottom-right.y-set!)
      x: br-pos r: hole-radius
    )

    (collision vehicle**board vehicle ** board)
    (collision vehicle**top_left vehicle ** top_left)

   (define sway_at_hole 0)

    (>>= (triggered vehicle**board)
         (lambda (_)
           (note "Found board.")

         (on 'kalman.east kalman.east-ref
           (lambda (val) (and (< val (+ -0.4 0.05)) (> val (- -0.4 0.05)) (< (kalman.depth-ref) (+ 1.6 0.05)) (> (kalman.depth-ref) (- 1.6 0.05))))))
           (lambda (_)
             (note "Found top left hole.")
             (set! sway_at_hole (kalman.sway-ref))

         (on 'kalman.sway kalman.sway-ref
           (lambda (val) (or (< val (- sway_at_hole 0.25)) (> val (+ sway_at_hole 0.25))))))
           (lambda (_)
             (note "Slid cover.")

         (on 'kalman.sway kalman.sway-ref
           (lambda (val) (and (< val (+ sway_at_hole 0.1)) (> val (- sway_at_hole 0.1))))))
           (lambda (_)
             (note "Returned to hole.")

         (on 'actuator-desires.trigger-01 actuator-desires.trigger-01-ref
           (lambda (val) (equal? val 1))))
           (lambda (_)
             ((note "Fired torpedo!")
             (complete win))))
  )

  (mission
    module: "torpedoes"
    task: "SetCourse")

  (options
    debug: #f)
  )

; vim: set lispwords+=peacock,vehicle,entity,camera,camera-stream,shape,collision :
