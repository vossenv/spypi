import time
from cmath import sin

from simple_pid import PID
pid = PID(1, 0.5, 0.05, setpoint=1)
#pid.output_limits = (0, 15)
# assume we have a system we want to control in controlled_system
v = sin(0)

while True:
    # compute new ouput from the PID according to the systems current value
    control = pid(v)

    # feed the PID output to the system and get its current value
    v = sin(control)
    print(v)
    time.sleep(1)