(include "peacock-prelude")

(peacock "Buoy Mission Test"
  (setup
    (note "Buoy ramming test begun! Will check that the sub rams the red then green buoys and drags down the yellow buoy.")

    (define timeout 120)
    (define sub-initial-pos #(0 0 1))
    (define red-buoy-pos #(2.5 -1.2 0.5))
    (define yellow-buoy-pos #(2.5 0.0 0.75))
    (define yellow-buoy-tow-depth 1.5)
    (define green-buoy-pos #(2.5 1.2 0.8))

    ; (>>= (on 'kalman.depth kalman.depth-ref (lambda (val) (< val 0.1))) (lambda (_) (fail "Surfaced, oh no!")))
    (>>= (after timeout) (lambda (_) (fail "Mission timed out!")))

    (vehicle-set!
      x: sub-initial-pos
      )

    ; Can we simulate two forward cameras?
    ; @chesley: Do you need downward camera simulation for buoys / do you use that for the yellow buoy?
    (camera forward
      q: (hpr->quat (vector 0 0 0))
      w: 1024 h: 1024 f: 440
    )

    (entity red-buoy-ent
      x: red-buoy-pos r: 0.2
      corporeal: #f
      xattrs: '(("render". "red_buoy")) ; tie to visualizer
    )

    (entity yellow-buoy-ent
      x: yellow-buoy-pos r: 0.2
      q: (hpr->quat (vector 0 0 (/ pi -2)))
      corporeal: #f
      xattrs: '(("render". "yellow_buoy")) ; tie to visualizer
    )

    (entity green-buoy-ent
      x: green-buoy-pos r: 0.2
      corporeal: #f
      xattrs: '(("render". "green_buoy")) ; tie to visualizer
    )

    (goals
      ram-red-buoy
      ram-green-buoy
      ram-yellow-buoy
      tow-yellow-buoy
    )

    ; TODO: Simulated vision.
    (shape forward >> red-buoy
      (red-buoy-results.probability-set!
       red-buoy-results.center-x-set!
       red-buoy-results.center-y-set!)
      x: red-buoy-pos r: 0.2)

    (shape forward >> green-buoy
      (green-buoy-results.probability-set!
       green-buoy-results.center-x-set!
       green-buoy-results.center-y-set!)
      x: green-buoy-pos r: 0.2)

    (shape forward >> yellow-buoy
      (yellow-buoy-results.probability-set!
       yellow-buoy-results.top-x-set!
       yellow-buoy-results.top-y-set!)
      x: yellow-buoy-pos r: 0.2)

    (collision vehicle**red-buoy vehicle ** red-buoy)
    (collision vehicle**green-buoy vehicle ** green-buoy)
    (collision vehicle**yellow-buoy vehicle ** yellow-buoy)

    (red-buoy-results.percent-frame-set! 0)
    (green-buoy-results.percent-frame-set! 0)
    (yellow-buoy-results.percent-frame-set! 0)

    (>>= (triggered vehicle**red-buoy) (lambda (_) (complete ram-red-buoy)))

    ; Ordering: red must be rammed first. At the moment, this is done by ordering the goals; in the future a points-based system could be used.
    (>>= (completed ram-red-buoy) (lambda (_)
      (note "Rammed red buoy!")
      (red-buoy-results.percent-frame-set! 100)
      (>>= (triggered vehicle**green-buoy) (lambda (_) (complete ram-green-buoy)))
      ))

    (>>= (completed ram-green-buoy) (lambda (_)
      (note "Rammed green buoy!")
      (green-buoy-results.percent-frame-set! 100)
      (return #t)
      ))

    ; No particular ordering of red/green vs. yellow buoy ramming seems to be required.
    (>>= (triggered vehicle**yellow-buoy) (lambda (_) (complete ram-yellow-buoy)))

    (>>= (completed ram-yellow-buoy) (lambda (_)
      (note "Rammed yellow buoy!")
      (yellow-buoy-results.percent-frame-set! 100)
      (yellow-buoy-results.center-y-set! 2000)
      (>>=
        (on 'kalman.depth kalman.depth-ref (lambda (val) (> val yellow-buoy-tow-depth)))
        (lambda (_)
          (note "Towed down ship cutout!")
          (complete tow-yellow-buoy)
          )
        )
      ))

  )

  (mission
    module: "buoys"
    task: "full")

  (options
    debug: #f)
)
