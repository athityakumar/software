=========
- ASLAM -
=========

"auv-SLAM"

Summary
-------

CUAUV uses a modified version of FastSLAM.

Dependencies
------------

> Eigen

Installation
------------

Usage
-----

Paper Implementation Notes
--------------------------

We have closed heading / depth measurement (robot in paper just has heading rate, e.g. two turning wheels). Thus instead we use Kalman heading and apply Gaussian noise.

Sources / Inspiration
-----------------------

FastSLAM 1.0 paper: http://ai.stanford.edu/~koller/Papers/Montemerlo+al:AAAI02.pdf
FastSLAM 2.0 paper: http://robots.stanford.edu/papers/Montemerlo03a.pdf
FastSLAM C++ implementation: https://github.com/bushuhui/fastslam
FastSLAM MatLab implementations: http://www-personal.acfr.usyd.edu.au/tbailey/software/slam_simulations.htm
