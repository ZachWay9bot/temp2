#!/usr/bin/env python3
from pathlib import Path
root=Path("SOURCE_KOXX3")

# Identity
p=root/"common_files/src/defines.h"
s=p.read_text()
old='#define HW_NAME "SESC-DRV126-POWERCORE6500-VBUS-FUSION-WIRED-LOCKED-V1"'
new='#define HW_NAME "SESC-DRV126-POWERCORE6500-VBUS-FUSION-WIRED-LOCKED-V2"'
assert old in s
p.write_text(s.replace(old,new,1))

# Fusion result gains separate cell-age telemetry.
p=root/"common_files/src/g30_vbus_fusion.h"
s=p.read_text()
s=s.replace('''  uint32_t bms_age_ms;
  uint8_t source;''','''  uint32_t bms_age_ms;
  uint32_t bms_cells_age_ms;
  uint8_t source;''',1)
p.write_text(s)

# Pure evaluator now uses the live BMS pack voltage for the 14/10 estimate.
p=root/"common_files/src/g30_vbus_fusion_impl.inc"
s=p.read_text()
old='''    r.est_mv=bms_pack_mv + (uint32_t)((bms_cell_sum_mv*2u + 2u)/5u);'''
assert old in s
s=s.replace(old,'''    r.est_mv=(uint32_t)((bms_pack_mv*14u + 5u)/10u);''',1)
p.write_text(s)

# Snapshot exposes independent live/cell ages; runtime scheduler becomes
# 0x30,0x30,0x40 at ~200ms/request. This keeps live voltage fresher while
# reducing traffic and allowing the slower cell block to act as plausibility.
p=root/"common_files/src/task_LED.h"
s=p.read_text()
s=s.replace('''  uint32_t age_ms;
  uint16_t cell_min_mv;''','''  uint32_t age_ms;
  uint32_t live_age_ms;
  uint32_t cells_age_ms;
  uint16_t cell_min_mv;''',1)
p.write_text(s)

p=root/"common_files/src/task_LED.c"
s=p.read_text()
s=s.replace('''  uint8_t fusion_pack_ok;
  uint8_t fusion_cells_ok;
  uint8_t rd;''','''  uint8_t fusion_pack_ok;
  uint8_t fusion_cells_ok;
  uint8_t fusion_poll_phase;
  uint8_t rd;''',1)

s=s.replace('''      out->age_ms=age_live>age_cells?age_live:age_cells;
      out->present=(uint8_t)(live_ms!=0u && cells_ms!=0u);''','''      out->live_age_ms=age_live;
      out->cells_age_ms=age_cells;
      out->age_ms=age_live>age_cells?age_live:age_cells;
      out->present=(uint8_t)(live_ms!=0u && cells_ms!=0u);''',1)

s=s.replace('''    BA(fusion_est_mv)=BA(fusion_pack_mv)+((BA(fusion_cell_sum_mv)*2u+2u)/5u);''',
            '''    BA(fusion_est_mv)=(BA(fusion_pack_mv)*14u+5u)/10u;''',1)

s=s.replace('''    BA(wait_ticks)=8u; /* total response budget about 90 ms */''',
            '''    BA(wait_ticks)=18u; /* allow late stock-BMS response; ~200 ms request cadence */''',1)

old_sched='''      if(sl==8u){
        BA(slot)=10u;
      }else{
        BA(slot)=8u;
        if(BA(round)!=0xFFFFu) BA(round)++;
      }'''
new_sched='''      if(sl==8u){
        if(BA(fusion_poll_phase)==0u){
          BA(fusion_poll_phase)=1u;
          BA(slot)=8u;
        }else{
          BA(fusion_poll_phase)=2u;
          BA(slot)=10u;
        }
      }else{
        BA(fusion_poll_phase)=0u;
        BA(slot)=8u;
        if(BA(round)!=0xFFFFu) BA(round)++;
      }'''
assert old_sched in s
s=s.replace(old_sched,new_sched,1)
p.write_text(s)

# Runtime validity: live voltage <=500ms, cell plausibility <=1500ms.
p=root/"common_files/src/mc_tasks.c"
s=p.read_text()
old='''    r.bms_age_ms=bs.age_ms;
    r.bms_valid=(uint8_t)(bs.present&&bs.plausible&&bs.age_ms<=G30_VBUS_BMS_MAX_AGE_MS);'''
new='''    r.bms_age_ms=bs.live_age_ms;
    r.bms_cells_age_ms=bs.cells_age_ms;
    r.bms_valid=(uint8_t)(bs.present&&bs.plausible&&
      bs.live_age_ms<=G30_VBUS_BMS_MAX_AGE_MS && bs.cells_age_ms<=1500u);'''
assert old in s
s=s.replace(old,new,1)
p.write_text(s)

# Short terminal telemetry, safe for 128-byte print buffer.
p=root/"common_files/src/terminal.c"
s=p.read_text()
old='''        commands_printf(phandle,"VBFUS_RT_BMS pack=%lu sum=%lu age=%lu valid=%u",
          (unsigned long)r.bms_pack_mv,(unsigned long)r.bms_cell_sum_mv,
          (unsigned long)r.bms_age_ms,(unsigned)r.bms_valid);'''
new='''        commands_printf(phandle,"VBFUS_RT_BMS pack=%lu sum=%lu age=%lu cage=%lu valid=%u",
          (unsigned long)r.bms_pack_mv,(unsigned long)r.bms_cell_sum_mv,
          (unsigned long)r.bms_age_ms,(unsigned long)r.bms_cells_age_ms,
          (unsigned)r.bms_valid);'''
assert old in s
s=s.replace(old,new,1)
s=s.replace('''VBFUS_RT_WIRING observer_connected=1 preload_connected=1 powerstage_locked=1''',
            '''VBFUS_RT_WIRING observer_connected=1 preload_connected=1 powerstage_locked=1 policy=pack14over10''',1)
p.write_text(s)

print("VBUS FUSION WIRED LOCKED V2 applied: live-pack 14/10 estimate, 30/30/40 scheduler, split freshness, power lock retained")
