import shm
import numpy as np
from control import vehicle
from control import quat
from control.thrusters import thrusters
from control.util import DOFSet

class ThrusterManager(object):
    """
        Thruster Manager is an aide to the controller and simulator for
        handling thrusters and other control related entities.
    """
    def __init__(self):
        self.thrusters = thrusters

        self.axes = DOFSet(f=np.array((1, 0, 0)), s=np.array((0, 1, 0)),
                           d=np.array((0, 0, 1)), p=np.array((0, 1, 0)),
                           r=np.array((1, 0, 0)), y=np.array((0, 0, 1)))

        # Find the max and min possible torques and thrusts in each axis
        dof_limits = []
        for axis, torque in zip(self.axes, DOFSet.torque):
            dof_limits.append(self.max_forces(axis, torque))
        self.dof_limits = DOFSet(dof_limits)

        self.thrust_mat = np.empty((len(self.thrusters), 3))
        self.torque_mat = np.empty((len(self.thrusters), 3))
        for i, t in enumerate(self.thrusters):
            self.thrust_mat[i] = t.force_hat
            self.torque_mat[i] = t.torque_hat

        """
            thrusts_to_sub is a matrix satisfying Ax = b, where x is a vector of
            thruster thrusts and b is a vector of outputs in sub space.
            The first three components of b are the x, y, z of the force
            and the last three components are the x, y, z of the torque.

            sub_to_thrusts is the pseudo inverse of that matrix
        """
        self.thrusts_to_sub = np.hstack((self.thrust_mat, self.torque_mat)).T
        # This assumes our matrix A is full rank, i.e. can meet any desired
        # thrust and torque i.e. our sub has 6 independent degrees of freedom
        # Since that is the case, we have an underdetermined system and we
        # we calculate the solution to Ax = b in such a way such that the norm
        # of x is minimized (to save power!) The pseudoinverse has this property
        # WARNING: If thrusters are removed, this may fail
        self.sub_to_thrusts = np.linalg.pinv(self.thrusts_to_sub)

    def max_forces(self, axis, torque=False):
        """ Returns [min_force, max_force] where min_force and max_force
            represent the minimum and maximum possible thrust or torque able to
            be imparted on the given axis by our thrusters
        """
        forces = [0, 0]
        f = lambda t: t.torque_about if torque else t.thrust_in
        for thruster in thrusters:
            max_t = (f(thruster))(axis, thruster.max_thrust)
            min_t = (f(thruster))(axis, thruster.max_neg_thrust)
            forces[0] += min(max_t, min_t)
            forces[1] += max(max_t, min_t)

        return forces

    def limit_thrusts(self, thrusts):
        """ Takes in a vector of thrust in SUB SPACE
            and limits the outputs based on max_forces
        """
        limits = [self.dof_limits.forward, self.dof_limits.sway, \
                  self.dof_limits.depth]
        return self.limit(thrusts, limits)

    def limit_desires(self, desires):
        """ Takes in a DOFSet desires and limits the outputs to reasonable
            values calculated using max possible thrust or torque
        """
        return self.limit(desires, self.dof_limits)

    def limit(self, desires, limits):
        out = []
        for d, (min_t, max_t) in zip(desires, limits):
            if d < min_t:
                out.append(min_t)
            elif d > max_t:
                out.append(max_t)
            else:
                out.append(d)

        return out

    def update(self, g):
        self.orientation = quat.Quaternion(q=[g.q0, g.q1, g.q2, g.q3])
        self.heading_quat = quat.Quaternion(hpr=(g.heading, 0, 0))
        self.hp_quat = quat.Quaternion(hpr=(g.heading, g.pitch, 0))
        self.spitz_to_sub_quat = self.orientation.conjugate() * self.heading_quat

    def get_thrusts(self):
        """ Returns thrusts produced by the thrusters """
        return [t.pwm_to_thrust(t.get()) for t in self.thrusters]

    def total_thrust(self, thrusts):
        """
            Given a list of thrusts for each thruster
            returns total thrust as a vector IN SUB SPACE
        """
        return thrusts.dot(self.thrust_mat)

    def total_torque(self, thrusts):
        """
            Given a list of thrusts for each thruster
            returns total torque as a vector IN SUB SPACE
        """
        return thrusts.dot(self.torque_mat)

    def hpr_to_world(self, heading, pitch, roll):
        """
        Converts heading, pitch, and roll components into a WORLD SPACE vector
        """
        # Heading is unaltered
        heading_w = np.array((0, 0, heading))
        # Pitch needs to be rotated by heading
        pitch_w = self.heading_quat * np.array((0, pitch, 0))
        # Roll needs to be rotated by heading AND pitch
        roll_w = self.hp_quat * np.array((roll, 0, 0))

        return heading_w + pitch_w + roll_w
