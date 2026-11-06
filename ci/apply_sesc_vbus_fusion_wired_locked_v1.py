#!/usr/bin/env python3
from pathlib import Path
root=Path("SOURCE_KOXX3")

# Identity
p=root/"common_files/src/defines.h"
s=p.read_text()
old='#define HW_NAME "SESC-DRV126-POWERCORE6500-VBUS-FUSION-SIM-V1"'
new='#define HW_NAME "SESC-DRV126-POWERCORE6500-VBUS-FUSION-WIRED-LOCKED-V1"'
assert old in s
p.write_text(s.replace(old,new,1))

# -------------------------------------------------------------------------
# BMS runtime cache: keep the first complete identity sweep, then alternate
# only 0x30 live and 0x40 cells so both inputs stay fresh enough for fusion.
# Cache lives in the already heap-allocated BMS state, not static RAM.
# -------------------------------------------------------------------------
p=root/"common_files/src/task_LED.h"
s=p.read_text()
anchor='uint16_t g30_bms_audit_round(void);\n'
assert anchor in s
add=r'''
typedef struct {
  uint32_t pack_mv;
  uint32_t cell_sum_mv;
  uint32_t est_mv;
  uint32_t low_mv;
  uint32_t high_mv;
  uint32_t age_ms;
  uint16_t cell_min_mv;
  uint16_t cell_max_mv;
  uint8_t present;
  uint8_t plausible;
} g30_bms_fusion_snapshot_t;
uint8_t g30_bms_fusion_snapshot(g30_bms_fusion_snapshot_t *out);
'''
s=s.replace(anchor,anchor+add,1)
p.write_text(s)

p=root/"common_files/src/task_LED.c"
s=p.read_text()
state_anchor='''  uint16_t crc_bad;
  uint16_t unexpected;
  uint16_t sum;
  uint16_t round;
'''
assert state_anchor in s
state_new='''  uint16_t crc_bad;
  uint16_t unexpected;
  uint16_t sum;
  uint16_t round;

  /* VBUS_FUSION runtime cache. Written only by task_LED/BMS parser.
   * Sequence counter lets the FOC IRQ read a coherent snapshot lock-free. */
  volatile uint32_t fusion_seq;
  uint32_t fusion_live_ms;
  uint32_t fusion_cells_ms;
  uint32_t fusion_pack_mv;
  uint32_t fusion_cell_sum_mv;
  uint32_t fusion_est_mv;
  uint32_t fusion_low_mv;
  uint32_t fusion_high_mv;
  uint16_t fusion_cell_min_mv;
  uint16_t fusion_cell_max_mv;
  uint8_t fusion_pack_ok;
  uint8_t fusion_cells_ok;
'''
s=s.replace(state_anchor,state_new,1)

round_anchor='uint16_t g30_bms_audit_round(void){ return g30_bms_audit_state?BA(round):0u; }\n'
assert round_anchor in s
snapshot=r'''
uint8_t g30_bms_fusion_snapshot(g30_bms_fusion_snapshot_t *out){
  uint32_t s1,s2,live_ms,cells_ms,now,age_live,age_cells;
  uint8_t tries;
  if(!out) return 0u;
  memset(out,0,sizeof(*out));
  if(!g30_bms_audit_state) return 0u;
  for(tries=0u;tries<3u;tries++){
    s1=BA(fusion_seq);
    if(s1&1u) continue;
    __asm volatile("" ::: "memory");
    out->pack_mv=BA(fusion_pack_mv);
    out->cell_sum_mv=BA(fusion_cell_sum_mv);
    out->est_mv=BA(fusion_est_mv);
    out->low_mv=BA(fusion_low_mv);
    out->high_mv=BA(fusion_high_mv);
    out->cell_min_mv=BA(fusion_cell_min_mv);
    out->cell_max_mv=BA(fusion_cell_max_mv);
    live_ms=BA(fusion_live_ms);
    cells_ms=BA(fusion_cells_ms);
    out->plausible=(uint8_t)(BA(fusion_pack_ok)&&BA(fusion_cells_ok)&&
      (out->pack_mv>out->cell_sum_mv?out->pack_mv-out->cell_sum_mv:out->cell_sum_mv-out->pack_mv)<=500u);
    __asm volatile("" ::: "memory");
    s2=BA(fusion_seq);
    if(s1==s2 && !(s2&1u)){
      now=HAL_GetTick();
      age_live=live_ms?(now-live_ms):0xFFFFFFFFu;
      age_cells=cells_ms?(now-cells_ms):0xFFFFFFFFu;
      out->age_ms=age_live>age_cells?age_live:age_cells;
      out->present=(uint8_t)(live_ms!=0u && cells_ms!=0u);
      return out->present;
    }
  }
  return 0u;
}

static void g30_bms_fusion_publish(uint8_t sl){
  uint8_t i;
  BA(fusion_seq)++;
  __asm volatile("" ::: "memory");
  if(sl==8u && BA(data_len)[sl]>=10u){
    uint32_t pack10=(uint32_t)BA(data)[sl][8] | ((uint32_t)BA(data)[sl][9]<<8);
    BA(fusion_pack_mv)=pack10*10u;
    BA(fusion_pack_ok)=(uint8_t)(BA(fusion_pack_mv)>=25000u && BA(fusion_pack_mv)<=43500u);
    BA(fusion_live_ms)=HAL_GetTick();
  }else if(sl==10u && BA(data_len)[sl]>=20u){
    uint32_t sum=0u;
    uint16_t mn=0xFFFFu,mx=0u;
    for(i=0u;i<10u;i++){
      uint16_t cv=(uint16_t)BA(data)[sl][2u*i] | ((uint16_t)BA(data)[sl][2u*i+1u]<<8);
      sum+=(uint32_t)cv;
      if(cv<mn) mn=cv;
      if(cv>mx) mx=cv;
    }
    BA(fusion_cell_sum_mv)=sum;
    BA(fusion_cell_min_mv)=mn;
    BA(fusion_cell_max_mv)=mx;
    BA(fusion_cells_ok)=(uint8_t)(mn>=2500u && mx<=4500u && mx>=mn &&
      sum>=25000u && sum<=43500u);
    BA(fusion_cells_ms)=HAL_GetTick();
  }
  if(BA(fusion_pack_ok)&&BA(fusion_cells_ok)){
    BA(fusion_est_mv)=BA(fusion_pack_mv)+((BA(fusion_cell_sum_mv)*2u+2u)/5u);
    BA(fusion_low_mv)=BA(fusion_pack_mv)+4u*(uint32_t)BA(fusion_cell_min_mv);
    BA(fusion_high_mv)=BA(fusion_pack_mv)+4u*(uint32_t)BA(fusion_cell_max_mv);
  }
  __asm volatile("" ::: "memory");
  BA(fusion_seq)++;
}
'''
s=s.replace(round_anchor,round_anchor+snapshot,1)

copy_anchor='''          BA(data_len)[sl]=BA(len);
          if(BA(ok)[sl]!=0xFFFFu) BA(ok)[sl]++;
'''
assert copy_anchor in s
s=s.replace(copy_anchor,'''          BA(data_len)[sl]=BA(len);
          g30_bms_fusion_publish(sl);
          if(BA(ok)[sl]!=0xFFFFu) BA(ok)[sl]++;
''',1)

sched_old='''    BA(slot)++;
    if(BA(slot)>=G30_BMS_AUDIT_SLOTS){
      BA(slot)=0u;
      if(BA(round)!=0xFFFFu) BA(round)++;
    }
    BA(phase)=1u;
'''
assert sched_old in s
sched_new='''    if(BA(round)==0u){
      BA(slot)++;
      if(BA(slot)>=G30_BMS_AUDIT_SLOTS){
        /* One full identity/diagnostic sweep is enough. Runtime then polls
         * live 0x30 and cells 0x40 alternately for <500 ms freshness. */
        BA(slot)=8u;
        if(BA(round)!=0xFFFFu) BA(round)++;
      }
    }else{
      if(sl==8u){
        BA(slot)=10u;
      }else{
        BA(slot)=8u;
        if(BA(round)!=0xFFFFu) BA(round)++;
      }
    }
    BA(phase)=1u;
'''
s=s.replace(sched_old,sched_new,1)
p.write_text(s)

# -------------------------------------------------------------------------
# Fusion API: keep pure evaluator for SIM/host tests, add runtime source.
# -------------------------------------------------------------------------
p=root/"common_files/src/g30_vbus_fusion_impl.inc"
s=p.read_text()
s=s.replace('((uint64_t)bms_cell_sum_mv*2u + 2u)/5u','(bms_cell_sum_mv*2u + 2u)/5u')
p.write_text(s)

p=root/"common_files/src/g30_vbus_fusion.h"
s=p.read_text()
anchor='const char *g30_vbus_fusion_source_name(uint8_t source);\n'
assert anchor in s
s=s.replace(anchor,anchor+'''g30_vbus_fusion_result_t g30_vbus_fusion_runtime_result(void);
uint16_t g30_vbus_fusion_runtime_mv(void);
uint8_t g30_vbus_fusion_runtime_sensorless_ok(void);
''',1)
p.write_text(s)

# Move the single external implementation from terminal.c to mc_tasks.c.
p=root/"common_files/src/terminal.c"
s=p.read_text()
s=s.replace('#include "g30_vbus_fusion_impl.inc"\n','',1)
marker='''    }else if (strcmp(argv[0], "g30_vbus_fusion_sim") == 0){'''
assert marker in s
wired=r'''    }else if (strcmp(argv[0], "g30_vbus_fusion_wired") == 0){
        g30_vbus_fusion_result_t r=g30_vbus_fusion_runtime_result();
        uint32_t fused=(r.source==G30_VBUS_SRC_PA1)?r.pa1_mv:
                       (r.source==G30_VBUS_SRC_BMS_EST)?r.est_mv:0u;
        commands_printf(phandle,"VBFUS_RT pa1=%lu src=%s fused=%lu sl_ok=%u",
          (unsigned long)r.pa1_mv,g30_vbus_fusion_source_name(r.source),
          (unsigned long)fused,(unsigned)r.sensorless_ok);
        commands_printf(phandle,"VBFUS_RT_BMS pack=%lu sum=%lu age=%lu valid=%u",
          (unsigned long)r.bms_pack_mv,(unsigned long)r.bms_cell_sum_mv,
          (unsigned long)r.bms_age_ms,(unsigned)r.bms_valid);
        commands_printf(phandle,"VBFUS_RT_WIRING observer_connected=1 preload_connected=1 powerstage_locked=1");
        return;
'''
s=s.replace(marker,wired+marker,1)
s=s.replace("VBFUS_WIRING observer_connected=0 powerstage_locked=1",
            "VBFUS_SIM_WIRING runtime_observer_connected=1 sim_only=1 powerstage_locked=1")
p.write_text(s)

p=root/"common_files/src/mc_tasks.c"
s=p.read_text()
inc_anchor='#include "g30_hall_trace.h"\n'
assert inc_anchor in s
s=s.replace(inc_anchor,inc_anchor+'#include "g30_vbus_fusion.h"\n#include "g30_vbus_fusion_impl.inc"\n#include "task_LED.h"\n',1)

# Runtime helper after global handles, before FOC hot path. The expensive 14/10
# division is already precomputed in task_LED; hot path only reads cached data.
insert_anchor='''MCT_Handle_t *pMCT[NBR_OF_MOTORS] = {&MCT[M1]};
'''
if insert_anchor not in s:
    # actual formatting differs; use a stable nearby symbol after global section
    insert_anchor='''MCT_Handle_t MCT[NBR_OF_MOTORS];
'''
assert insert_anchor in s
runtime=r'''
#ifdef G30P
g30_vbus_fusion_result_t g30_vbus_fusion_runtime_result(void){
  g30_vbus_fusion_result_t r={0};
  g30_bms_fusion_snapshot_t bs;
  uint32_t q16=(uint32_t)(65536000.0f/BATTERY_VOLTAGE_GAIN+0.5f);
  uint32_t adc=(uint32_t)pBusSensorM1->_Super.AvBusVoltage_d;
  r.pa1_mv=(adc*q16)>>16;
  if(g30_bms_fusion_snapshot(&bs)){
    r.bms_pack_mv=bs.pack_mv;
    r.bms_cell_sum_mv=bs.cell_sum_mv;
    r.est_mv=bs.est_mv;
    r.low_mv=bs.low_mv;
    r.high_mv=bs.high_mv;
    r.bms_age_ms=bs.age_ms;
    r.bms_valid=(uint8_t)(bs.present&&bs.plausible&&bs.age_ms<=G30_VBUS_BMS_MAX_AGE_MS);
    if(r.bms_valid){
      uint32_t d=(r.pa1_mv>r.est_mv)?(r.pa1_mv-r.est_mv):(r.est_mv-r.pa1_mv);
      r.series_match=(uint8_t)(d<=1500u);
    }
  }
  if(r.pa1_mv<=G30_VBUS_PA1_TRUST_MAX_MV){
    r.source=G30_VBUS_SRC_PA1;
    r.sensorless_ok=1u;
    if(!r.bms_valid){ r.low_mv=r.pa1_mv; r.high_mv=r.pa1_mv; }
  }else if(r.bms_valid){
    r.source=G30_VBUS_SRC_BMS_EST;
    r.sensorless_ok=1u;
  }else{
    r.source=G30_VBUS_SRC_INVALID;
    r.sensorless_ok=0u;
  }
  return r;
}

uint16_t g30_vbus_fusion_runtime_mv(void){
  g30_vbus_fusion_result_t r=g30_vbus_fusion_runtime_result();
  uint32_t mv=(r.source==G30_VBUS_SRC_PA1)?r.pa1_mv:
              (r.source==G30_VBUS_SRC_BMS_EST)?r.est_mv:0u;
  return (uint16_t)(mv>65535u?65535u:mv);
}
uint8_t g30_vbus_fusion_runtime_sensorless_ok(void){
  return g30_vbus_fusion_runtime_result().sensorless_ok;
}
#endif
'''
s=s.replace(insert_anchor,insert_anchor+runtime,1)

# Wire both FO76 call sites to fused millivolts instead of saturated ADC counts.
s=s.replace('''g30_fo76_shadow_step(Iab.a,Iab.b,HALL_M1._Super.hElAngle,
                           pBusSensorM1->_Super.AvBusVoltage_d,''',
'''g30_fo76_shadow_step(Iab.a,Iab.b,HALL_M1._Super.hElAngle,
                           g30_vbus_fusion_runtime_mv(),''',1)
s=s.replace('''g30_fo76_shadow_step(Iab.a, Iab.b, HALL_M1._Super.hElAngle,
                       pBusSensorM1->_Super.AvBusVoltage_d,''',
'''g30_fo76_shadow_step(Iab.a, Iab.b, HALL_M1._Super.hElAngle,
                       g30_vbus_fusion_runtime_mv(),''',1)
p.write_text(s)

# FO76 now consumes physical mV directly.
p=root/"common_files/src/g30_fo76_shadow.h"
s=p.read_text()
s=s.replace('''void g30_fo76_shadow_step(int16_t ia, int16_t ib, int16_t hall_angle,
                          uint16_t vbus_adc, uint16_t ccr_a, uint16_t ccr_b,''',
'''void g30_fo76_shadow_step(int16_t ia, int16_t ib, int16_t hall_angle,
                          uint16_t vbus_mv, uint16_t ccr_a, uint16_t ccr_b,''',1)
p.write_text(s)

p=root/"common_files/src/g30_fo76_shadow.c"
s=p.read_text()
old='''void g30_fo76_shadow_step(int16_t ia_counts,int16_t ib_counts,int16_t hall,
                          uint16_t vbus_adc,uint16_t ca,uint16_t cb,uint16_t cc,uint16_t period,
'''
new='''void g30_fo76_shadow_step(int16_t ia_counts,int16_t ib_counts,int16_t hall,
                          uint16_t vbus_mv_in,uint16_t ca,uint16_t cb,uint16_t cc,uint16_t period,
'''
assert old in s
s=s.replace(old,new,1)
old_line='''    uint32_t vbus_mv=((uint32_t)vbus_adc * vbus_mv_per_count_q16)>>16;
'''
assert old_line in s
s=s.replace(old_line,'''    uint32_t vbus_mv=(uint32_t)vbus_mv_in;
''',1)
p.write_text(s)

# Startup preload consumes the exact same fused source and fails closed.
p=root/"common_files/src/VescToSTM.c"
s=p.read_text()
inc='#include "g30_vbus_fusion.h"\n'
anchor='#include "g30_hall_trace.h"\n'
assert anchor in s
s=s.replace(anchor,anchor+inc,1)
old='''    float bus_v=VescToSTM_get_bus_voltage();
    uint16_t bus_mv=(bus_v>=0.0f && bus_v<=65.535f)?(uint16_t)(bus_v*1000.0f+0.5f):0u;
    g30_r3i_preload_result_t initial=g30_r3i_preload_calculate(speed,lambda,bus_mv);
'''
assert old in s
s=s.replace(old,'''    g30_vbus_fusion_result_t vfr=g30_vbus_fusion_runtime_result();
    if(!vfr.sensorless_ok) return;
    uint32_t fused_mv=(vfr.source==G30_VBUS_SRC_PA1)?vfr.pa1_mv:vfr.est_mv;
    uint16_t bus_mv=(uint16_t)(fused_mv>65535u?65535u:fused_mv);
    g30_r3i_preload_result_t initial=g30_r3i_preload_calculate(speed,lambda,bus_mv);
''',1)
p.write_text(s)

print("VBUS FUSION WIRED LOCKED V1 applied: fast BMS runtime cache, FO76 mV source, preload source, hard powerstage lock retained")
