#!/usr/bin/env python3
from pathlib import Path
R=Path('SOURCE_KOXX3')

def rd(p): return (R/p).read_text()
def wr(p,s): (R/p).write_text(s)
def r1(s,old,new,label):
    n=s.count(old)
    if n!=1: raise RuntimeError(f'{label}: expected 1 anchor, got {n}')
    return s.replace(old,new,1)

p=Path('common_files/src/defines.h'); s=rd(p)
s=r1(s,'#define HW_NAME "SHUD4-STRICT-DRIVE-V3"','#define HW_NAME "SHUD4-STRICT-DRIVE-V4"','build id')
wr(p,s)

p=Path('common_files/src/VescToSTM.c'); s=rd(p)
s=r1(s,
'''bool VescToSTM_g30_sensorless_selected(void){\n#ifdef G30_POWERPATH_RESTORE_V1\n    return false;\n#else\n    return mc_conf.foc_sensor_mode == FOC_SENSOR_MODE_SENSORLESS;\n#endif\n}\n\nbool VescToSTM_g30_hall_selected(void){\n#ifdef G30_POWERPATH_RESTORE_V1\n    return true;\n#else\n    return mc_conf.foc_sensor_mode == FOC_SENSOR_MODE_HALL;\n#endif\n}''',
'''bool VescToSTM_g30_sensorless_selected(void){\n#if defined(G30_SHUD4_STRICT_DRIVETRAIN_V1)\n    return false;\n#elif defined(G30_POWERPATH_RESTORE_V1)\n    return false;\n#else\n    return mc_conf.foc_sensor_mode == FOC_SENSOR_MODE_SENSORLESS;\n#endif\n}\n\nbool VescToSTM_g30_hall_selected(void){\n#if defined(G30_SHUD4_STRICT_DRIVETRAIN_V1)\n    return true;\n#elif defined(G30_POWERPATH_RESTORE_V1)\n    return true;\n#else\n    return mc_conf.foc_sensor_mode == FOC_SENSOR_MODE_HALL;\n#endif\n}''','strict Hall selector')
wr(p,s)

p=Path('common_files/src/mc_tasks.c'); s=rd(p)
s=r1(s,
'''#ifdef G30P\n  /* R3G2: Hall implementation updates hElSpeedDpp, but does not populate\n   * InstantaneousElSpeedDpp in this MCSDK tree. Use the same valid Hall speed\n   * source that the FO76 observer already consumes. */\n  hElSpeedDpp = (VescToSTM_g30_sensorless_selected() && g30_fo76_sensorless_active())?g30_fo76_control_speed_dpp():SPD_GetElSpeedDpp(speedHandle);\n#else\n  hElSpeedDpp = SPD_GetInstElSpeedDpp(speedHandle);\n#endif\n#ifdef G30P\n  /* R3G: Hall is still the default. This fast selector can return the\n   * predicted observer angle only after an explicit, validated takeover. */\n  hElAngle = (int16_t)g30_fo76_control_angle(hElAngle, hElSpeedDpp);\n#endif''',
'''#ifdef G30P\n#ifdef G30_SHUD4_STRICT_DRIVETRAIN_V1\n  /* STRICT SHUD4: Hall is the sole electrical position/speed source. */\n  hElSpeedDpp = SPD_GetElSpeedDpp(speedHandle);\n#else\n  /* R3G2: Hall implementation updates hElSpeedDpp, but does not populate\n   * InstantaneousElSpeedDpp in this MCSDK tree. Use the same valid Hall speed\n   * source that the FO76 observer already consumes. */\n  hElSpeedDpp = (VescToSTM_g30_sensorless_selected() && g30_fo76_sensorless_active())?g30_fo76_control_speed_dpp():SPD_GetElSpeedDpp(speedHandle);\n#endif\n#else\n  hElSpeedDpp = SPD_GetInstElSpeedDpp(speedHandle);\n#endif\n#ifdef G30P\n#ifndef G30_SHUD4_STRICT_DRIVETRAIN_V1\n  /* R3G: Hall is still the default. This fast selector can return the\n   * predicted observer angle only after an explicit, validated takeover. */\n  hElAngle = (int16_t)g30_fo76_control_angle(hElAngle, hElSpeedDpp);\n#endif\n#endif''','fast Hall-only selector')

s=r1(s,
'''    uint16_t g30_old_ca=pwmcHandle[M1]->CntPhA;\n    uint16_t g30_old_cb=pwmcHandle[M1]->CntPhB;\n    uint16_t g30_old_cc=pwmcHandle[M1]->CntPhC;\n    uint8_t hall_guard=(uint8_t)VescToSTM_g30_hall_selected();''',
'''#ifndef G30_SHUD4_STRICT_DRIVETRAIN_V1\n    uint16_t g30_old_ca=pwmcHandle[M1]->CntPhA;\n    uint16_t g30_old_cb=pwmcHandle[M1]->CntPhB;\n    uint16_t g30_old_cc=pwmcHandle[M1]->CntPhC;\n#endif\n    uint8_t hall_guard=(uint8_t)VescToSTM_g30_hall_selected();''','old pwm vector guard')

s=r1(s,
'''    if(VescToSTM_g30_sensorless_selected()){\n      /* FO76 observes the voltage actually present during this current sample:\n       * the previous DRV126 PWM vector. This preserves the frozen 16-kHz\n       * observer model while the DRV126 current controller runs at 4 kHz. */\n      g30_fo76_shadow_step(Iab.a,Iab.b,HALL_M1._Super.hElAngle,\n                           pBusSensorM1->_Super.AvBusVoltage_d,\n                           g30_old_ca,g30_old_cb,g30_old_cc,\n                           PWM_Handle_M1.Half_PWMPeriod,\n                           (uint16_t)DEAD_TIME_COUNTS,\n                           HALL_M1._Super.hElSpeedDpp,\n                           (uint8_t)!PWM_Handle_M1._Super.PWM_off);\n    }''',
'''#ifndef G30_SHUD4_STRICT_DRIVETRAIN_V1\n    if(VescToSTM_g30_sensorless_selected()){\n      /* FO76 observer is excluded from STRICT SHUD4 runtime. */\n      g30_fo76_shadow_step(Iab.a,Iab.b,HALL_M1._Super.hElAngle,\n                           pBusSensorM1->_Super.AvBusVoltage_d,\n                           g30_old_ca,g30_old_cb,g30_old_cc,\n                           PWM_Handle_M1.Half_PWMPeriod,\n                           (uint16_t)DEAD_TIME_COUNTS,\n                           HALL_M1._Super.hElSpeedDpp,\n                           (uint8_t)!PWM_Handle_M1._Super.PWM_off);\n    }\n#endif''','observer call guard in DRV core')

s=r1(s,
'''  uint16_t g30_old_ca = pwmcHandle[M1]->CntPhA;\n  uint16_t g30_old_cb = pwmcHandle[M1]->CntPhB;\n  uint16_t g30_old_cc = pwmcHandle[M1]->CntPhC;\n  hCodeError = PWMC_SetPhaseVoltage(pwmcHandle[M1], Valphabeta);\n  g30_fo76_shadow_step(Iab.a, Iab.b, HALL_M1._Super.hElAngle,\n                       pBusSensorM1->_Super.AvBusVoltage_d,\n                       g30_old_ca, g30_old_cb, g30_old_cc,\n                       PWM_Handle_M1.Half_PWMPeriod,\n                       (uint16_t)DEAD_TIME_COUNTS,\n                       HALL_M1._Super.hElSpeedDpp,\n                       (uint8_t)!PWM_Handle_M1._Super.PWM_off);''',
'''#ifndef G30_SHUD4_STRICT_DRIVETRAIN_V1\n  uint16_t g30_old_ca = pwmcHandle[M1]->CntPhA;\n  uint16_t g30_old_cb = pwmcHandle[M1]->CntPhB;\n  uint16_t g30_old_cc = pwmcHandle[M1]->CntPhC;\n#endif\n  hCodeError = PWMC_SetPhaseVoltage(pwmcHandle[M1], Valphabeta);\n#ifndef G30_SHUD4_STRICT_DRIVETRAIN_V1\n  g30_fo76_shadow_step(Iab.a, Iab.b, HALL_M1._Super.hElAngle,\n                       pBusSensorM1->_Super.AvBusVoltage_d,\n                       g30_old_ca, g30_old_cb, g30_old_cc,\n                       PWM_Handle_M1.Half_PWMPeriod,\n                       (uint16_t)DEAD_TIME_COUNTS,\n                       HALL_M1._Super.hElSpeedDpp,\n                       (uint8_t)!PWM_Handle_M1._Super.PWM_off);\n#endif''','generic observer call guard')

s=r1(s,
'''    /* R3H: observer-only exit is Coast. Use the normal motor state machine\n     * stop path instead of switching the FOC angle back to Hall. */\n    if(g30_fo76_coast_requested())\n    {\n      (void)MCI_StopMotor( pMCI[M1] );\n      break;\n    }''',
'''#ifndef G30_SHUD4_STRICT_DRIVETRAIN_V1\n    /* R3H observer-only exit is not part of STRICT SHUD4. */\n    if(g30_fo76_coast_requested())\n    {\n      (void)MCI_StopMotor( pMCI[M1] );\n      break;\n    }\n#endif''','observer coast guard')

s=r1(s,
'''  /* R3I2 preserves an externally seeded sensorless trajectory through the\n   * intentional STOP->IDLE->START transition. All ordinary restarts still\n   * disarm observer takeover exactly as before. */\n  if(!g30_fo76_sensorless_active()) g30_fo76_request_takeover(0u);''',
'''#ifndef G30_SHUD4_STRICT_DRIVETRAIN_V1\n  /* R3I2 sensorless takeover cleanup is not part of STRICT SHUD4. */\n  if(!g30_fo76_sensorless_active()) g30_fo76_request_takeover(0u);\n#endif''','observer clear guard')
wr(p,s)

p=Path('common_files/src/stm32f10x_mc_it.c'); s=rd(p)
s=r1(s,
'''        uint32_t stamp=DWT->CYCCNT;\n        g30_fo76_capture_probe_t probe=g30_fo76_capture_probe();\n        g30_hall_trace_sample_t edge={''',
'''        uint32_t stamp=DWT->CYCCNT;\n#ifdef G30_SHUD4_STRICT_DRIVETRAIN_V1\n        g30_fo76_capture_probe_t probe={0};\n        probe.control=(uint16_t)HALL_M1._Super.hElAngle;\n        probe.observer=probe.control;\n        probe.control_dpp=HALL_M1._Super.hElSpeedDpp;\n        probe.coherent=1u;\n#else\n        g30_fo76_capture_probe_t probe=g30_fo76_capture_probe();\n#endif\n        g30_hall_trace_sample_t edge={''','hall trace observer-free')
wr(p,s)
print('SHUD4 STRICT V4 applied: Hall-only active runtime, FO76 excluded from FOC/drive path')
