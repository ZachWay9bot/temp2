from pathlib import Path
R=Path("SOURCE_KOXX3/common_files/src")

p=R/"defines.h"; s=p.read_text()
old='#define HW_NAME "G30D-FO76-PUSHSTART-R3I8"'
if old not in s: raise SystemExit("build id anchor")
p.write_text(s.replace(old,'#define HW_NAME "G30D-FO76-PUSHSTART-R3I9"',1))

p=R/"g30_r3i_pushstart.c"; s=p.read_text()
old='static uint8_t ha=255u,hb=255u,hc=255u,init_done,divn,last_sector=R3I_NO_SECTOR;'
new='static uint8_t ha=255u,hb=255u,hc=255u,init_done,divn,last_sector=R3I_NO_SECTOR,last_cal_hall_valid;'
if old not in s: raise SystemExit("static anchor")
s=s.replace(old,new,1)
old='static int32_t cal_sum;\nstatic uint8_t cal_persist_valid,arm_had_cal;'
new='static int32_t cal_sum;\nstatic uint16_t last_cal_hall;\nstatic uint8_t cal_persist_valid,arm_had_cal;'
if old not in s: raise SystemExit("cal static anchor")
s=s.replace(old,new,1)
old='last_sector=R3I_NO_SECTOR;last_edge_cycles=avg_edge_cycles=0;cal_sum=0;divn=0;'
new='last_sector=R3I_NO_SECTOR;last_edge_cycles=avg_edge_cycles=0;cal_sum=0;divn=0;last_cal_hall=0u;last_cal_hall_valid=0u;'
if old not in s: raise SystemExit("reset anchor")
s=s.replace(old,new,1)
old='''        if(!d.cal_valid && hall_speed_dpp<=-40){
            cal_sum+=(int16_t)(hall_angle-d.phase_base);
            if(d.cal_samples<65535u)d.cal_samples++;
            if(d.cal_samples>=R3I_CAL_SAMPLES){
                d.cal_offset=(int16_t)(cal_sum/(int32_t)d.cal_samples);
                d.cal_valid=1u;
                cal_persist_offset=d.cal_offset;
                cal_persist_valid=1u;
            }
        }
'''
new='''        if(!d.cal_valid && hall_speed_dpp<=-40){
            /* R3I9: hall_angle is the live capture angle (MeasuredElAngle),
             * not the FOC-integrated _Super.hElAngle which freezes while PWM
             * is off. Take one calibration sample per new Hall position so
             * twelve samples cover two electrical revolutions. */
            if(!last_cal_hall_valid || hall_angle!=last_cal_hall){
                cal_sum+=(int16_t)(hall_angle-d.phase_base);
                last_cal_hall=hall_angle;
                last_cal_hall_valid=1u;
                if(d.cal_samples<65535u)d.cal_samples++;
                if(d.cal_samples>=R3I_CAL_SAMPLES){
                    d.cal_offset=(int16_t)(cal_sum/(int32_t)d.cal_samples);
                    d.cal_valid=1u;
                    cal_persist_offset=d.cal_offset;
                    cal_persist_valid=1u;
                }
            }
        }
'''
if old not in s: raise SystemExit("calibration block anchor")
p.write_text(s.replace(old,new,1))

p=R/"mc_tasks.c"; s=p.read_text()
old='''      g30_r3i_tick((uint8_t)PWM_Handle_M1._Super.PWM_off,
                   (uint16_t)HALL_M1._Super.hElAngle,
                   HALL_M1._Super.hElSpeedDpp);
'''
new='''      g30_r3i_tick((uint8_t)PWM_Handle_M1._Super.PWM_off,
                   (uint16_t)HALL_M1.MeasuredElAngle,
                   HALL_M1._Super.hElSpeedDpp);
'''
if old not in s: raise SystemExit("safety hall angle anchor")
p.write_text(s.replace(old,new,1))

p=R/"terminal.c"; s=p.read_text()
s=s.replace('FO76_R3I8 pushstart_sensorless=1','FO76_R3I9 pushstart_sensorless=1',1)
s=s.replace('R3I8 ARM: serialized regular ADC; BEMF angle + observer frequency catch',
            'R3I9 ARM: live Hall-capture calibration + serialized ADC + observer catch',1)
p.write_text(s)

print("R3I9 transform applied")
