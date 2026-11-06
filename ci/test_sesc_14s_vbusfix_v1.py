#!/usr/bin/env python3
from pathlib import Path
import math

root=Path("SOURCE_KOXX3")
vs=(root/"common_files/src/VescToSTM.c").read_text()
fo=(root/"common_files/src/g30_fo76_shadow.c").read_text()
fh=(root/"common_files/src/g30_fo76_shadow.h").read_text()
mc=(root/"common_files/src/mc_tasks.c").read_text()
de=(root/"common_files/src/defines.h").read_text()
pr=(root/"common_files/inc/product.h").read_text()

assert 'SESC-DRV126-POWERCORE6500-14S-VBUSFIX-V1' in de
assert '#define G30_VBUS_RAIL_DETECT_ADC 65400u' in fo
assert '#define G30_VBUS_14S_MODEL_MV 52379u' in fo
assert 'g30_fo76_sensorless_model_vbus_mv' in fh
assert 'g30_fo76_sensorless_vbus_rail_mode' in fh
assert 'sensorless_external ?\n        (uint32_t)g30_fo76_sensorless_model_vbus_mv(vbus_adc)' in fo

p0=mc.index('static uint16_t g30_drv126_final_power_step')
p1=mc.index('\nstatic ',p0+40)
core=mc[p0:p1]
for bad in ('VBS_GetAvBusVoltage_d','VescToSTM_get_bus_voltage','BATTERY_VOLTAGE_GAIN','AvBusVoltage_d'):
    assert bad not in core, bad

s0=vs.index('if(VescToSTM_g30_hall_selected()){',vs.index('void VescToSTM_pwm_start'))
s1=vs.index('}else',s0)
hall=vs[s0:s1]
assert 'PIDIqHandle_M1.wIntegralTerm=0;' in hall
assert 'PIDIdHandle_M1.wIntegralTerm=0;' in hall
assert 'g30_drv126_final_preload(0,0);' in hall
assert 'VescToSTM_get_bus_voltage' not in hall

p0=vs.index('void VescToSTM_prepare_sensorless_start')
p1=vs.index('\n#ifdef G30P',p0+60)
pre=vs[p0:p1]
assert 'g30_fo76_sensorless_model_vbus_mv' in pre
assert 'VescToSTM_get_bus_voltage()' not in pre
assert 'uint16_t Vin = VBS_GetAvBusVoltage_d' in vs
assert 'if(Vin < fp.battery_cut_start)' in vs
assert 'if(g30_fo76_sensorless_vbus_rail_mode())' in vs
assert 'kmh*2000.0f' in vs
assert 'if(rail_ma>60000)rail_ma=60000;' in vs

div=3363.5
gain=div*(3.3/4095.0)*512.0
vlo=65400.0/gain
vfull=65535.0/gain
vhi=58.8
vm=2.0*vfull*vhi/(vfull+vhi)
assert abs(vm*1000.0-52379.0)<1.0
assert max(abs(vm/vlo-1.0),abs(vm/vhi-1.0))<0.112

R=.583
L=640e-6
lam=24.2e-3
wheel=.250
pp=15
minmag=99.0
maxmag=0.0
maxphase=0.0
count=0
worst=None
for ikmh in range(300,6001,25):
    kmh=ikmh/100.0
    cap=min(2.0*kmh,60.0)
    omega=2.0*math.pi*((kmh/3.6)/(math.pi*wheel))*pp
    for ii in range(-20,21):
        I=cap*ii/20.0
        for iv in range(121):
            v=vlo+(vhi-vlo)*iv/120.0
            scale=vm/v
            pd=scale*lam+(scale-1.0)*R*I/omega
            pq=(scale-1.0)*L*I
            mag=math.hypot(pd,pq)/lam
            phase=abs(math.degrees(math.atan2(pq,pd)))
            minmag=min(minmag,mag)
            maxmag=max(maxmag,mag)
            if phase>maxphase:
                maxphase=phase
                worst=(kmh,I,v,mag,phase)
            count+=1
assert minmag>=.72,(minmag,maxmag)
assert maxmag<=1.30,(minmag,maxmag)
assert maxphase<14.0,(maxphase,worst)

print(f'14S_VBUSFIX_STATIC=PASS')
print(f'ADC_FULLSCALE_V={vfull:.6f}')
print(f'RAIL_DETECT_V={vlo:.6f}')
print(f'MODEL_V={vm:.6f}')
print(f'SWEEP_SAMPLES={count}')
print(f'FLUX_RATIO={minmag:.6f}..{maxmag:.6f}')
print(f'MAX_PHASE_ERROR_DEG={maxphase:.6f}')
print(f'WORST={worst}')
