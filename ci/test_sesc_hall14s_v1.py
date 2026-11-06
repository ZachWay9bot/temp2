#!/usr/bin/env python3
from pathlib import Path
import hashlib,re

root = Path("SOURCE_KOXX3")

def sha(rel):
    return hashlib.sha256((root/rel).read_bytes()).hexdigest()

# The actual fast motor path must remain EXACTLY the hardware-validated restore.
expected = {
    "common_files/src/mc_tasks.c": "1c3f61ad12855960ddf25ea96730328bdfaa4d8653d6f7ec9fe89d2114518c98",
    "common_files/MotorControl/MCSDK/MCLib/F1xx/Src/r3_2_f1xx_pwm_curr_fdbk.c": "14ccd029244f230d5632f18c6c278aa3021976ede8a4513939af068456eee276",
}
for rel,want in expected.items():
    got = sha(rel)
    assert got == want, (rel, got, want)
    print(f"EXACT_VALIDATED_FASTPATH {rel}=PASS {got}")

defs=(root/"common_files/src/defines.h").read_text()
vs=(root/"common_files/src/VescToSTM.c").read_text()

assert 'SESC-DRV126-POWERCORE6500-HALL14S-V1' in defs
assert '#define G30_HALL14S_V1 1' in defs
assert '#define G30_POWERPATH_RESTORE_V1 1' in defs

start = vs.index("void VescToSTM_pwm_start(void)")
end = vs.index("void VescToSTM_update_torque", start)
fn = vs[start:end]

# Hall branch must not derive preload from speed/flux/VBUS.
hall = fn[fn.index("if(VescToSTM_g30_hall_selected())"):]
assert "hall_erpm" not in hall
assert "hall_rad_s" not in hall
assert "foc_motor_flux_linkage" not in hall
# VBUS exists only in retained unreachable non-Hall fallback.
hall_branch = hall[:hall.index("}else")]
assert "VescToSTM_get_bus_voltage()" not in hall_branch
assert "g30_drv126_final_preload" not in hall_branch
assert "wIntegralTerm = 0;" in hall_branch
assert "FOCVars[M1].Vqd.q = 0;" in hall_branch
assert "FOCVars[M1].Vqd.d = 0;" in hall_branch
assert "motor_voltage = 0.0f;" in hall_branch

# Hall angle is still loaded immediately before gate enable.
assert "HALL_M1._Super.hElAngle = HALL_M1.MeasuredElAngle;" in fn
assert "PWMC_SwitchOnPWM(&PWM_Handle_M1._Super);" in fn

# Existing Hall-only selection and fault latch remain.
assert "return false;" in vs.split("bool VescToSTM_g30_sensorless_selected(void){",1)[1].split("}",1)[0]
assert "return true;" in vs.split("bool VescToSTM_g30_hall_selected(void){",1)[1].split("}",1)[0]

print("HALL_RESTART_NO_VBUS_PRELOAD=PASS")
print("HALL_RESTART_ZERO_PI_STATE=PASS")
print("HALL_ANGLE_BEFORE_PWM_ENABLE=PASS")
print("FAST_FOC_BYTE_EXACT_RESTORE=PASS")
print("HALL14S_V1_STATIC=PASS")
