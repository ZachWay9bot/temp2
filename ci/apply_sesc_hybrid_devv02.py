from pathlib import Path

root=Path("SOURCE_KOXX3")

# Build ID
p=root/"common_files/src/defines.h"
s=p.read_text()
old='#define HW_NAME "SESC-HYBRID-DEVV0.1"'
new='#define HW_NAME "SESC-HYBRID-DEVV0.2"'
assert old in s
p.write_text(s.replace(old,new))

# 1) Sensorless MCSDK CLEAR must never energize PWM.
p=root/"common_files/src/mc_tasks.c"
s=p.read_text()
old='''#ifdef G30P
      if(VescToSTM_g30_sensorless_selected() && g30_fo76_sensorless_active()) VescToSTM_prepare_sensorless_start();
#endif
      R3_2_SwitchOnPWM( pwmcHandle[M1] );'''
new='''#ifdef G30P
      /* DevV0.2: sensorless rolling start owns the first PWM enable.
       * CLEAR may advance MCSDK to RUN, but while SENSORLESS is selected the
       * bridge stays off so passive BEMF acquisition remains truly passive.
       * Hall mode retains the established direct MCSDK startup path. */
      if(!VescToSTM_g30_sensorless_selected())
      {
        R3_2_SwitchOnPWM( pwmcHandle[M1] );
      }
#else
      R3_2_SwitchOnPWM( pwmcHandle[M1] );
#endif'''
assert old in s
p.write_text(s.replace(old,new))

# 2) First sensorless PWM cycle must already see <=1 A Iq reference.
p=root/"common_files/src/VescToSTM.c"
s=p.read_text()
old='''#ifdef G30P
        if(VescToSTM_g30_sensorless_selected() && g30_r3i_sensorless_active()){
            VescToSTM_prepare_sensorless_start();
        }else
#endif'''
new='''#ifdef G30P
        if(VescToSTM_g30_sensorless_selected() && g30_r3i_sensorless_active()){
            /* DevV0.2: clamp the already-prepared current reference BEFORE
             * gate outputs are enabled. The normal 800 ms hold + 1000 ms ramp
             * in VescToSTM_Iq_lim_hook continues to own subsequent updates. */
            int16_t one_a_q=(int16_t)current_to_torque(1000);
            if(FOCVars[M1].Iqdref.q>one_a_q) FOCVars[M1].Iqdref.q=one_a_q;
            else if(FOCVars[M1].Iqdref.q< -one_a_q) FOCVars[M1].Iqdref.q=(int16_t)-one_a_q;
            FOCVars[M1].hTeref=FOCVars[M1].Iqdref.q;
            VescToSTM_prepare_sensorless_start();
        }else
#endif'''
assert old in s
p.write_text(s.replace(old,new))

print("SESC Hybrid DevV0.2 sensorless start guards applied")
