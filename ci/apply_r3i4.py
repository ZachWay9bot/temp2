from pathlib import Path

ROOT=Path("SOURCE_KOXX3")
SRC=ROOT/"common_files/src"

def one(path, old, new, label):
    p=path
    s=p.read_text()
    n=s.count(old)
    if n!=1:
        raise SystemExit(f"{label}: expected one anchor, got {n}")
    p.write_text(s.replace(old,new,1))

one(SRC/"defines.h",
    '#define HW_NAME "G30D-FO76-PUSHSTART-R3I3"',
    '#define HW_NAME "G30D-FO76-PUSHSTART-R3I4"',
    "build id")

# Critical R3I4 change:
# Do not register or touch the passive BEMF regular ADC channels during normal
# boot. The R3I3 hardware run became UART-silent immediately after reset.
# Registration now occurs only after the explicit push-start ARM request.
p=SRC/"g30_r3i_pushstart.c"; s=p.read_text()
old='''void g30_r3i_tick(uint8_t pwm_off,uint16_t hall_angle,int16_t hall_speed_dpp){
    init_once();
    if(!request_arm || !init_done)return;
'''
new='''void g30_r3i_tick(uint8_t pwm_off,uint16_t hall_angle,int16_t hall_speed_dpp){
    if(!request_arm)return;
    init_once();
    if(!init_done)return;
'''
if old not in s:
    raise SystemExit("deferred ADC init anchor missing")
p.write_text(s.replace(old,new,1))

p=SRC/"terminal.c"; s=p.read_text()
s=s.replace('FO76_R3I3 pushstart_sensorless=1','FO76_R3I4 pushstart_sensorless=1',1)
s=s.replace('R3I2 ARM: forced MCSDK STOP + PWM OFF; passive BEMF sampling only after coast',
            'R3I4 ARM: forced STOP/PWM OFF; passive BEMF ADC registration deferred until ARM',1)
p.write_text(s)

print("R3I4 transform applied")
