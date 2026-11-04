from pathlib import Path

root=Path("SOURCE_KOXX3")

# Build ID only; observer/pushstart core stays frozen.
p=root/"common_files/src/defines.h"
s=p.read_text()
old='#define HW_NAME "SESC-HYBRID-DEVV0.2"'
new='#define HW_NAME "SESC-HALL-DEVV0.1"'
assert old in s
p.write_text(s.replace(old,new))

# Export one Hall validity helper used by startup and RUN guards.
p=root/"common_files/src/VescToSTM.h"
s=p.read_text()
old='''bool VescToSTM_g30_sensorless_selected(void);
bool VescToSTM_g30_hall_selected(void);
void VescToSTM_g30_sensor_mode_sync(void);'''
new='''bool VescToSTM_g30_sensorless_selected(void);
bool VescToSTM_g30_hall_selected(void);
bool VescToSTM_g30_hall_feedback_valid(void);
void VescToSTM_g30_sensor_mode_sync(void);'''
assert old in s
p.write_text(s.replace(old,new))

p=root/"common_files/src/VescToSTM.c"
s=p.read_text()
old='''bool VescToSTM_g30_hall_selected(void){
    return mc_conf.foc_sensor_mode == FOC_SENSOR_MODE_HALL;
}

void VescToSTM_g30_sensor_mode_sync(void){'''
new='''bool VescToSTM_g30_hall_selected(void){
    return mc_conf.foc_sensor_mode == FOC_SENSOR_MODE_HALL;
}

bool VescToSTM_g30_hall_feedback_valid(void){
    /* HallDevV0.1: use the live GPIO state, not only the last captured state.
     * This also catches a Hall connector/power loss while the wheel is stopped. */
    uint8_t raw=HALL_read(&HALL_M1);
    if(raw==0u || raw==7u) return false;
    if(HALL_M1.lut[raw]==255u) return false;
    return HALL_M1.SensorIsReliable;
}

void VescToSTM_g30_sensor_mode_sync(void){'''
assert old in s
s=s.replace(old,new)

old='''void VescToSTM_pwm_start(void){
#ifdef G30P
    if(VescToSTM_g30_sensorless_selected() && g30_r3i_block_pwm_start()) return;
#endif'''
new='''void VescToSTM_pwm_start(void){
#ifdef G30P
    /* HallDevV0.1: never energize the bridge with an invalid Hall state.
     * Sensorless keeps its separate frozen rolling-start gate. */
    if(VescToSTM_g30_hall_selected() && !VescToSTM_g30_hall_feedback_valid()) return;
    if(VescToSTM_g30_sensorless_selected() && g30_r3i_block_pwm_start()) return;
#endif'''
assert old in s
p.write_text(s.replace(old,new))

# Startup and RUN fail-safe: invalid Hall feedback must fault/coast before torque.
p=root/"common_files/src/mc_tasks.c"
s=p.read_text()
old='''  case CLEAR:
    HALL_Clear( &HALL_M1 );

    if ( STM_NextState( &STM[M1], START ) == true )
    {'''
new='''  case CLEAR:
    HALL_Clear( &HALL_M1 );
#ifdef G30P
    /* HallDevV0.1: a disconnected/illegal Hall state at standstill must never
     * reach the direct Hall PWM start below. */
    if(VescToSTM_g30_hall_selected() && !VescToSTM_g30_hall_feedback_valid())
    {
      STM_FaultProcessing( &STM[M1], MC_SPEED_FDBK, 0u );
      break;
    }
#endif

    if ( STM_NextState( &STM[M1], START ) == true )
    {'''
assert old in s
s=s.replace(old,new)

old='''  case RUN:
    /* USER CODE BEGIN MediumFrequencyTask M1 2 */

    /* USER CODE END MediumFrequencyTask M1 2 */
#ifdef G30P
    /* R3H: observer-only exit is Coast. Use the normal motor state machine
     * stop path instead of switching the FOC angle back to Hall. */
    if(g30_fo76_coast_requested())'''
new='''  case RUN:
    /* USER CODE BEGIN MediumFrequencyTask M1 2 */

    /* USER CODE END MediumFrequencyTask M1 2 */
#ifdef G30P
    /* HallDevV0.1: fail safe on Hall loss/illegal transition before another
     * medium-frequency torque update is accepted. */
    if(VescToSTM_g30_hall_selected() && !VescToSTM_g30_hall_feedback_valid())
    {
      VescToSTM_pwm_stop();
      STM_FaultProcessing( &STM[M1], MC_SPEED_FDBK, 0u );
      break;
    }
    /* R3H: observer-only exit is Coast. Use the normal motor state machine
     * stop path instead of switching the FOC angle back to Hall. */
    if(g30_fo76_coast_requested())'''
assert old in s
p.write_text(s.replace(old,new))

# G30-specific Hall IRQ validation: only one Hall bit may change per 60-degree edge.
p=root/"common_files/MotorControl/MCSDK/MCLib/Any/Src/hall_speed_pos_fdbk.c"
s=p.read_text()
old='''    /* A capture event generated this interrupt */
    bPrevHallState = pHandle->lut[pHandle->HallState];
    PrevDirection = pHandle->Direction;

    pHandle->HallState  = HALL_read(pHandle);

    if(pHandle->HallState == 0 || pHandle->HallState == 7){
    	pHandle->_Super.bSpeedErrorNumber++;
    	pHandle->SensorIsReliable = false;

    }else{'''
new='''    /* A capture event generated this interrupt */
#ifdef G30P
    uint8_t g30PrevRawHall = pHandle->HallState;
#endif
    bPrevHallState = pHandle->lut[pHandle->HallState];
    PrevDirection = pHandle->Direction;

    pHandle->HallState  = HALL_read(pHandle);

#ifdef G30P
    uint8_t g30HallXor=(uint8_t)(g30PrevRawHall ^ pHandle->HallState);
    bool g30HallAdjacent=(g30HallXor==1u || g30HallXor==2u || g30HallXor==4u);
    bool g30HallInvalid=(pHandle->HallState==0u || pHandle->HallState==7u ||
                         g30PrevRawHall==0u || g30PrevRawHall==7u ||
                         pHandle->lut[pHandle->HallState]==255u ||
                         pHandle->lut[g30PrevRawHall]==255u ||
                         !g30HallAdjacent);
    if(g30HallInvalid){
        /* HallDevV0.1: 000/111 and skipped/multi-bit Hall transitions are not
         * valid rotor sectors. Drop speed immediately and let the Hall-mode
         * medium task coast + latch MC_SPEED_FDBK. Do not feed this capture
         * into the speed FIFO. */
        if(pHandle->_Super.bSpeedErrorNumber < 255u) pHandle->_Super.bSpeedErrorNumber++;
        pHandle->SensorIsReliable=false;
        pHandle->_Super.hElSpeedDpp=0;
        pHandle->_Super.hAvrMecSpeedUnit=0;
        pHandle->AvrElSpeedDpp=0;
        pHandle->CompSpeed=0;
        pHandle->OVFCounter=0u;
        (void)LL_TIM_IC_GetCaptureCH1(TIMx);
        return MC_NULL;
    }else{
#else
    if(pHandle->HallState == 0 || pHandle->HallState == 7){
    	pHandle->_Super.bSpeedErrorNumber++;
    	pHandle->SensorIsReliable = false;

    }else{
#endif'''
assert old in s
s=s.replace(old,new)
p.write_text(s)


# HallDevV0.1 second audit pass: latch faults and prohibit counter-torque reversal.

p=root/"common_files/src/VescToSTM.h"
x=p.read_text()
old='''bool VescToSTM_g30_hall_feedback_valid(void);
void VescToSTM_g30_sensor_mode_sync(void);'''
new='''bool VescToSTM_g30_hall_feedback_valid(void);
bool VescToSTM_g30_hall_direction_allowed(int32_t requested);
void VescToSTM_g30_sensor_mode_sync(void);'''
assert old in x
p.write_text(x.replace(old,new))

p=root/"common_files/src/VescToSTM.c"
x=p.read_text()
old='''    if(HALL_M1.lut[raw]==255u) return false;
    return HALL_M1.SensorIsReliable;
}

void VescToSTM_g30_sensor_mode_sync(void){'''
new='''    if(HALL_M1.lut[raw]==255u) return false;
    return HALL_M1.SensorIsReliable;
}

bool VescToSTM_g30_hall_direction_allowed(int32_t requested){
    /* HallDevV0.1: FWD and REV remain supported, but a request opposite to a
     * clearly rotating wheel coasts first instead of applying counter-torque. */
    if(!VescToSTM_g30_hall_selected() || requested==0) return true;
    int32_t measured=(int32_t)HALL_M1._Super.hAvrMecSpeedUnit*(int32_t)DIR_MUL;
    const int32_t coast_deadband_speed_unit=20; /* about 120 ERPM */
    if(measured>coast_deadband_speed_unit && requested<0) return false;
    if(measured< -coast_deadband_speed_unit && requested>0) return false;
    return true;
}

void VescToSTM_g30_sensor_mode_sync(void){'''
assert old in x
x=x.replace(old,new)

old='''void VescToSTM_update_torque(int32_t q, int32_t min_erpm, int32_t max_erpm){
	q *= DIR_MUL;'''
new='''void VescToSTM_update_torque(int32_t q, int32_t min_erpm, int32_t max_erpm){
#ifdef G30P
    if(!VescToSTM_g30_hall_direction_allowed(q)){
        VescToSTM_set_brake(0);
        return;
    }
#endif
	q *= DIR_MUL;'''
assert old in x
x=x.replace(old,new)

old='''void VescToSTM_set_speed(int32_t erpm){
#ifdef G30P
	/* R3I14: VESC +ERPM stays positive.'''
new='''void VescToSTM_set_speed(int32_t erpm){
#ifdef G30P
    if(!VescToSTM_g30_hall_direction_allowed(erpm)){
        VescToSTM_set_brake(0);
        return;
    }
	/* R3I14: VESC +ERPM stays positive.'''
assert old in x
x=x.replace(old,new)
p.write_text(x)

# Latch an illegal physical Hall transition until HALL_Clear().
p=root/"common_files/MotorControl/MCSDK/MCLib/Any/Src/hall_speed_pos_fdbk.c"
x=p.read_text()
old='''        if(pHandle->_Super.bSpeedErrorNumber < 255u) pHandle->_Super.bSpeedErrorNumber++;
        pHandle->SensorIsReliable=false;'''
new='''        pHandle->_Super.bSpeedErrorNumber=pHandle->_Super.bMaximumSpeedErrorsNumber;
        pHandle->SensorIsReliable=false;'''
assert old in x
x=x.replace(old,new)

old='''    if(--pHandle->speed_fault_reset_cnt < 0){
    	pHandle->speed_fault_reset_cnt = HALL_FAULT_RESET_CNT;
    	pHandle->SensorIsReliable = true;
    }'''
new='''#ifndef G30P
    if(--pHandle->speed_fault_reset_cnt < 0){
    	pHandle->speed_fault_reset_cnt = HALL_FAULT_RESET_CNT;
    	pHandle->SensorIsReliable = true;
    }
#else
    /* HallDevV0.1: reliability faults are cleared only by HALL_Clear(). */
    pHandle->speed_fault_reset_cnt = HALL_FAULT_RESET_CNT;
#endif'''
assert old in x
x=x.replace(old,new)

old='''  }else{
	  HALL_Init_Electrical_Angle( pHandle );
  }
  return MC_NULL;'''
new='''  }else{
#ifndef G30P
	  HALL_Init_Electrical_Angle( pHandle );
#else
      /* HallDevV0.1: no timer-IRQ auto-heal after an illegal Hall edge. */
#endif
  }
  return MC_NULL;'''
assert old in x
x=x.replace(old,new)

# The last invalid-state block belongs to HALL_Init_Electrical_Angle.
old='''    if(pHandle->HallState == 0 || pHandle->HallState == 7){
    	pHandle->_Super.bSpeedErrorNumber++;
    	pHandle->SensorIsReliable = false;
    }else{'''
new='''    if(pHandle->HallState == 0 || pHandle->HallState == 7){
#ifdef G30P
        pHandle->_Super.bSpeedErrorNumber=pHandle->_Super.bMaximumSpeedErrorsNumber;
#else
    	pHandle->_Super.bSpeedErrorNumber++;
#endif
    	pHandle->SensorIsReliable = false;
    }else{'''
pos=x.rfind(old)
assert pos>=0
x=x[:pos]+x[pos:].replace(old,new,1)
p.write_text(x)

# Kill TIM1 MOE immediately in the physical Hall IRQ on an illegal transition.
p=root/"common_files/src/stm32f10x_mc_it.c"
x=p.read_text()
old='''#ifdef G30P
#include "g30_fo76_shadow.h"
#include "g30_hall_trace.h"
#endif'''
new='''#ifdef G30P
#include "g30_fo76_shadow.h"
#include "g30_hall_trace.h"
#include "VescToSTM.h"
#endif'''
assert old in x
x=x.replace(old,new)
old='''    HALL_TIMx_CC_IRQHandler(&HALL_M1);
#ifdef G30P
    /* Diagnostic data only. This branch is reached by a physical CC1 event,''';
new='''    HALL_TIMx_CC_IRQHandler(&HALL_M1);
#ifdef G30P
    /* HallDevV0.1: remove gate drive immediately; the medium task records the
     * MC_SPEED_FDBK fault and performs the full stop sequence. */
    if(VescToSTM_g30_hall_selected() && !HALL_M1.SensorIsReliable){
        PWM_Handle_M1._Super.PWM_off=true;
        LL_TIM_DisableAllOutputs(TIM1);
    }
    /* Diagnostic data only. This branch is reached by a physical CC1 event,''';
assert old in x
x=x.replace(old,new)
p.write_text(x)

# VESC command layer checks direction before Hall pushstart can turn PWM on.
p=root/"common_files/src/VescCommand.c"
x=p.read_text()
old='''				VescToSTM_g30_pushstart_command(raw != 0);
				if(raw == 0){ VescToSTM_timeout_reset(); break; }'''
new='''                if(raw != 0 && !VescToSTM_g30_hall_direction_allowed(raw)){
                    VescToSTM_g30_pushstart_command(false);
                    VescToSTM_timeout_reset();
                    break;
                }
				VescToSTM_g30_pushstart_command(raw != 0);
				if(raw == 0){ VescToSTM_timeout_reset(); break; }'''
count=x.count(old)
assert count>=3, count
x=x.replace(old,new)

old='''				VescToSTM_g30_pushstart_command(val != 0.0f);
					if(val == 0.0f){ VescToSTM_timeout_reset(); break; }'''
new='''                int32_t hall_dir=(val>0.0f)?1:((val<0.0f)?-1:0);
                if(hall_dir && !VescToSTM_g30_hall_direction_allowed(hall_dir)){
                    VescToSTM_g30_pushstart_command(false);
                    VescToSTM_timeout_reset();
                    break;
                }
				VescToSTM_g30_pushstart_command(val != 0.0f);
					if(val == 0.0f){ VescToSTM_timeout_reset(); break; }'''
assert old in x
x=x.replace(old,new)
p.write_text(x)

# The stock dashboard is forward-only. If the wheel is rolling backwards in
# Hall mode, coast until near zero before allowing forward torque.
p=root/"common_files/src/g30_dash_link.c"
x=p.read_text()
old='''        uint16_t torque=g30_dash_r2_scale(d->gas);
        if(!torque) return;
        VescToSTM_g30_pushstart_command(true);'''
new='''        uint16_t torque=g30_dash_r2_scale(d->gas);
        if(!torque) return;
        if(!VescToSTM_g30_hall_direction_allowed(1)){
            VescToSTM_g30_pushstart_command(false);
            d->coast_commands++;
            return;
        }
        VescToSTM_g30_pushstart_command(true);'''
assert old in x
x=x.replace(old,new)
p.write_text(x)

print("SESC Hall DevV0.1 second-pass hardening applied")


# Hall LUT plausibility: reject corrupt or geometrically impossible six-sector maps.
p=root/"common_files/src/VescToSTM.c"
x=p.read_text()
old='''bool VescToSTM_g30_hall_feedback_valid(void){
    /* HallDevV0.1: use the live GPIO state, not only the last captured state.
     * This also catches a Hall connector/power loss while the wheel is stopped. */
    uint8_t raw=HALL_read(&HALL_M1);
    if(raw==0u || raw==7u) return false;
    if(HALL_M1.lut[raw]==255u) return false;
    return HALL_M1.SensorIsReliable;
}'''
new='''static bool g30_hall_lut_valid(void){
    static const uint8_t ring[7]={1u,3u,2u,6u,4u,5u,1u};
    if(HALL_M1.lut[0]!=255u || HALL_M1.lut[7]!=255u) return false;
    int8_t direction=0;
    for(unsigned i=0;i<6u;i++){
        int16_t d=(int16_t)HALL_M1.lut[ring[i+1u]]-(int16_t)HALL_M1.lut[ring[i]];
        if(d>100) d-=255;
        else if(d< -100) d+=255;
        int16_t mag=d<0?-d:d;
        /* Ideal is 255/6 = 42.5 counts. Keep tolerance deliberately broad. */
        if(mag<25 || mag>65) return false;
        int8_t sign=d>0?1:-1;
        if(direction==0) direction=sign;
        else if(sign!=direction) return false;
    }
    return true;
}

bool VescToSTM_g30_hall_feedback_valid(void){
    /* HallDevV0.1: use the live GPIO state, not only the last captured state.
     * This also catches a Hall connector/power loss while the wheel is stopped. */
    if(!g30_hall_lut_valid()) return false;
    uint8_t raw=HALL_read(&HALL_M1);
    if(raw==0u || raw==7u) return false;
    if(HALL_M1.lut[raw]==255u) return false;
    return HALL_M1.SensorIsReliable;
}'''
assert old in x
p.write_text(x.replace(old,new))
print("SESC Hall DevV0.1 LUT plausibility guard applied")

print("SESC Hall DevV0.1 guards applied")
