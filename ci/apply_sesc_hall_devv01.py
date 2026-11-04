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

print("SESC Hall DevV0.1 guards applied")
