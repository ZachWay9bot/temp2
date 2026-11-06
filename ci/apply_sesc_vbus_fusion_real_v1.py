#!/usr/bin/env python3
from pathlib import Path
root=Path("SOURCE_KOXX3")

p=root/"common_files/src/defines.h"
s=p.read_text()
old='#define HW_NAME "SESC-DRV126-POWERCORE6500-VBUS-FUSION-SIM-V1"'
new='#define HW_NAME "SESC-DRV126-POWERCORE6500-VBUS-FUSION-REAL-V1"'
assert old in s
p.write_text(s.replace(old,new,1))

# Extend the already heap-backed BMS state with freshness timestamps.
p=root/"common_files/src/task_LED.c"
s=p.read_text()
needle='''  uint32_t raw_total;
  uint32_t ok_total;
  uint32_t req_ms;'''
rep='''  uint32_t raw_total;
  uint32_t ok_total;
  uint32_t req_ms;
  uint32_t live_ok_ms;
  uint32_t cells_ok_ms;'''
assert needle in s
s=s.replace(needle,rep,1)

needle='''          BA(data_len)[sl]=BA(len);
          if(BA(ok)[sl]!=0xFFFFu) BA(ok)[sl]++;'''
rep='''          BA(data_len)[sl]=BA(len);
          if(sl==8u) BA(live_ok_ms)=HAL_GetTick();
          if(sl==10u) BA(cells_ok_ms)=HAL_GetTick();
          if(BA(ok)[sl]!=0xFFFFu) BA(ok)[sl]++;'''
assert needle in s
s=s.replace(needle,rep,1)

needle='''uint16_t g30_bms_audit_round(void){ return g30_bms_audit_state?BA(round):0u; }'''
rep=r'''uint16_t g30_bms_audit_round(void){ return g30_bms_audit_state?BA(round):0u; }

uint8_t g30_bms_fusion_data_valid(void){
  if(!g30_bms_audit_state) return 0u;
  if(BA(ok)[8u]==0u || BA(ok)[10u]==0u) return 0u;
  if(BA(data_len)[8u]<14u || BA(data_len)[10u]<20u) return 0u;
  return 1u;
}
uint32_t g30_bms_fusion_age_ms(void){
  uint32_t now,a,b;
  if(!g30_bms_fusion_data_valid()) return 0xffffffffu;
  now=HAL_GetTick();
  a=now-BA(live_ok_ms);
  b=now-BA(cells_ok_ms);
  return a>b?a:b;
}
uint32_t g30_bms_fusion_pack_mv(void){
  if(!g30_bms_fusion_data_valid()) return 0u;
  return 10u*(uint32_t)((uint16_t)BA(data)[8u][8u] | ((uint16_t)BA(data)[8u][9u]<<8));
}
uint32_t g30_bms_fusion_cell_sum_mv(void){
  uint8_t i; uint32_t sum=0u;
  if(!g30_bms_fusion_data_valid()) return 0u;
  for(i=0u;i<10u;i++) sum+=(uint16_t)BA(data)[10u][2u*i] | ((uint16_t)BA(data)[10u][2u*i+1u]<<8);
  return sum;
}
uint16_t g30_bms_fusion_cell_min_mv(void){
  uint8_t i; uint16_t m=0xffffu;
  if(!g30_bms_fusion_data_valid()) return 0u;
  for(i=0u;i<10u;i++){
    uint16_t v=(uint16_t)BA(data)[10u][2u*i] | ((uint16_t)BA(data)[10u][2u*i+1u]<<8);
    if(v<m)m=v;
  }
  return m;
}
uint16_t g30_bms_fusion_cell_max_mv(void){
  uint8_t i; uint16_t m=0u;
  if(!g30_bms_fusion_data_valid()) return 0u;
  for(i=0u;i<10u;i++){
    uint16_t v=(uint16_t)BA(data)[10u][2u*i] | ((uint16_t)BA(data)[10u][2u*i+1u]<<8);
    if(v>m)m=v;
  }
  return m;
}'''
s=s.replace(needle,rep,1)
p.write_text(s)

p=root/"common_files/src/task_LED.h"
s=p.read_text()
needle='''uint16_t g30_bms_audit_round(void);'''
rep='''uint16_t g30_bms_audit_round(void);
uint8_t g30_bms_fusion_data_valid(void);
uint32_t g30_bms_fusion_age_ms(void);
uint32_t g30_bms_fusion_pack_mv(void);
uint32_t g30_bms_fusion_cell_sum_mv(void);
uint16_t g30_bms_fusion_cell_min_mv(void);
uint16_t g30_bms_fusion_cell_max_mv(void);'''
assert needle in s
p.write_text(s.replace(needle,rep,1))

p=root/"common_files/src/terminal.c"
s=p.read_text()
marker='''    }else if (strcmp(argv[0], "g30_vbus_fusion_sim") == 0){'''
assert marker in s
block=r'''    }else if (strcmp(argv[0], "g30_vbus_fusion_real") == 0){
        uint32_t pa1_mv=(uint32_t)(VescToSTM_get_bus_voltage()*1000.0f+0.5f);
        uint8_t present=g30_bms_fusion_data_valid();
        uint32_t age=g30_bms_fusion_age_ms();
        uint32_t pack=g30_bms_fusion_pack_mv();
        uint32_t sum=g30_bms_fusion_cell_sum_mv();
        uint16_t cmin=g30_bms_fusion_cell_min_mv();
        uint16_t cmax=g30_bms_fusion_cell_max_mv();
        g30_vbus_fusion_result_t r=g30_vbus_fusion_eval(pa1_mv,pack,sum,cmin,cmax,age,present);
        uint32_t fused=(r.source==G30_VBUS_SRC_PA1)?r.pa1_mv:r.est_mv;
        commands_printf(phandle,
          "VBFUS_REAL pa1=%lu adc_avg=%u bms10=%lu cellsum=%lu cellmin=%u cellmax=%u age=%lu present=%u valid=%u src=%s fused=%lu low=%lu high=%lu sl_ok=%u",
          (unsigned long)pa1_mv,(unsigned)RealBusVoltageSensorParamsM1._Super.AvBusVoltage_d,
          (unsigned long)pack,(unsigned long)sum,(unsigned)cmin,(unsigned)cmax,
          (unsigned long)age,(unsigned)present,(unsigned)r.bms_valid,
          g30_vbus_fusion_source_name(r.source),(unsigned long)fused,
          (unsigned long)r.low_mv,(unsigned long)r.high_mv,(unsigned)r.sensorless_ok);
        commands_printf(phandle,
          "VBFUS_REAL policy observer_connected=0 preload_connected=0 powerstage_locked=1 Cpin_untouched no_bms_write");
        return;
'''
s=s.replace(marker,block+marker,1)
p.write_text(s)

print("VBUS FUSION REAL V1 applied: real BMS+PA1 fusion diagnostics; observer/preload still disconnected; powerstage locked")
