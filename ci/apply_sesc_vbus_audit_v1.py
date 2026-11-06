#!/usr/bin/env python3
from pathlib import Path

root=Path("SOURCE_KOXX3")

# Build identity. Keep the already validated BMS/PowerLock layer intact and add
# only stack-local Vbus diagnostics. No motor path, observer math or ADC setup is
# modified by this audit build.
p=root/"common_files/src/defines.h"
s=p.read_text()
old='#define HW_NAME "SESC-DRV126-POWERCORE6500-BMS-FINAL-READ-V1"'
new='#define HW_NAME "SESC-DRV126-POWERCORE6500-VBUS-AUDIT-V1"'
assert old in s
p.write_text(s.replace(old,new,1))

p=root/"common_files/src/terminal.c"
s=p.read_text()
marker='''    }else if (strcmp(argv[0], "g30_bmsphy") == 0){'''
assert marker in s

block=r'''    }else if (strcmp(argv[0], "g30_powerlock") == 0){
        commands_printf(phandle,
          "POWERLOCK enabled=1 bdtr=%08lX ccer=%08lX moe=%u ch123=%u pwm_off=%u",
          (unsigned long)TIM1->BDTR,(unsigned long)TIM1->CCER,
          (unsigned)((TIM1->BDTR & TIM_BDTR_MOE)?1u:0u),
          (unsigned)((TIM1->CCER & 0x0555u)?1u:0u),
          (unsigned)PWM_Handle_M1._Super.PWM_off);
        return;
    }else if (strcmp(argv[0], "g30_vbus_audit") == 0){
        uint16_t latest=RealBusVoltageSensorParamsM1._Super.LatestConv;
        uint16_t avg=RealBusVoltageSensorParamsM1._Super.AvBusVoltage_d;
        uint32_t gain_x1000=(uint32_t)(BATTERY_VOLTAGE_GAIN*1000.0f+0.5f);
        uint32_t fullscale_u16_mv=(uint32_t)(65535.0f/BATTERY_VOLTAGE_GAIN*1000.0f+0.5f);
        uint32_t fullscale_adc12_left_mv=(uint32_t)(65520.0f/BATTERY_VOLTAGE_GAIN*1000.0f+0.5f);
        uint32_t vbus_mv=(uint32_t)(VescToSTM_get_bus_voltage()*1000.0f+0.5f);
        uint32_t fo76_q16=(uint32_t)(65536000.0f/BATTERY_VOLTAGE_GAIN+0.5f);
        uint32_t fo76_mv=((uint32_t)avg*fo76_q16)>>16;
        uint32_t headroom_counts=(uint32_t)65535u-(uint32_t)avg;
        uint32_t headroom_mv=fullscale_u16_mv>vbus_mv?fullscale_u16_mv-vbus_mv:0u;
        float ov_raw=mc_conf.l_max_vin*BATTERY_VOLTAGE_GAIN;
        float uv_raw=mc_conf.l_min_vin*BATTERY_VOLTAGE_GAIN;
        uint8_t ov_clipped=(uint8_t)(ov_raw>65535.0f);
        uint8_t uv_clipped=(uint8_t)(uv_raw>65535.0f);
        uint8_t near_rail=(uint8_t)(avg>=65000u || latest>=65000u);
        commands_printf(phandle,
          "VBAUDIT vbus_mv=%lu adc_latest=%u adc_avg=%u adc_left_align=%u adc_cr2=%08lX",
          (unsigned long)vbus_mv,(unsigned)latest,(unsigned)avg,
          (unsigned)((ADC1->CR2 & ADC_CR2_ALIGN)?1u:0u),(unsigned long)ADC1->CR2);
        commands_printf(phandle,
          "VBAUDIT scale_x1000=%lu fullscale_u16_mv=%lu fullscale_adc12_left_mv=%lu headroom_counts=%lu headroom_mv=%lu near_rail=%u",
          (unsigned long)gain_x1000,(unsigned long)fullscale_u16_mv,
          (unsigned long)fullscale_adc12_left_mv,(unsigned long)headroom_counts,
          (unsigned long)headroom_mv,(unsigned)near_rail);
        commands_printf(phandle,
          "VBAUDIT limits_req_mv=%ld..%ld threshold_counts=%u..%u uv_clipped=%u ov_clipped=%u",
          (long)(mc_conf.l_min_vin*1000.0f),(long)(mc_conf.l_max_vin*1000.0f),
          (unsigned)RealBusVoltageSensorParamsM1.UnderVoltageThreshold,
          (unsigned)RealBusVoltageSensorParamsM1.OverVoltageThreshold,
          (unsigned)uv_clipped,(unsigned)ov_clipped);
        commands_printf(phandle,
          "VBAUDIT battery_cut_mv=%ld..%ld battery_cut_counts=%lu..%lu",
          (long)(mc_conf.l_battery_cut_start*1000.0f),
          (long)(mc_conf.l_battery_cut_end*1000.0f),
          (unsigned long)(mc_conf.l_battery_cut_start*BATTERY_VOLTAGE_GAIN+0.5f),
          (unsigned long)(mc_conf.l_battery_cut_end*BATTERY_VOLTAGE_GAIN+0.5f));
        commands_printf(phandle,
          "VBAUDIT fo76_scale_q16=%lu fo76_from_avg_mv=%lu observer_vbus_source=PA1_AVG preload_vbus_source=PA1_AVG",
          (unsigned long)fo76_q16,(unsigned long)fo76_mv);
        commands_printf(phandle,
          "VBAUDIT hall_inner_vbus=0 sensorless_voltage_model_vbus=1 sensorless_preload_vbus=1 ov_above_adc_ceiling_detectable=0");
        commands_printf(phandle,
          "VBAUDIT reference_nominal_divider=14 nominal_3V3_fullscale_mv=46200 note=reference_only_not_runtime_calibration");
        return;
'''
s=s.replace(marker,block+marker,1)
p.write_text(s)
print("VBUS AUDIT V1 applied: diagnostics only; powerstage lock retained; no motor/observer/ADC behavior changed")
