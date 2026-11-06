#!/usr/bin/env python3
from pathlib import Path
root=Path("SOURCE_KOXX3")

# Build identity only; VBUS_FUSION_SIM_V1 does NOT feed the observer or motor
# control. It validates the exact fusion decision logic with the powerstage hard
# locked.
p=root/"common_files/src/defines.h"
s=p.read_text()
old='#define HW_NAME "SESC-DRV126-POWERCORE6500-VBUS-AUDIT-V1"'
new='#define HW_NAME "SESC-DRV126-POWERCORE6500-VBUS-FUSION-SIM-V1"'
assert old in s
p.write_text(s.replace(old,new,1))

h=r'''#ifndef G30_VBUS_FUSION_H
#define G30_VBUS_FUSION_H
#include <stdint.h>

#define G30_VBUS_PA1_TRUST_MAX_MV 45000u
#define G30_VBUS_BMS_MAX_AGE_MS   500u

enum {
  G30_VBUS_SRC_INVALID=0u,
  G30_VBUS_SRC_PA1=1u,
  G30_VBUS_SRC_BMS_EST=2u
};

typedef struct {
  uint32_t pa1_mv;
  uint32_t bms_pack_mv;
  uint32_t bms_cell_sum_mv;
  uint32_t est_mv;
  uint32_t low_mv;
  uint32_t high_mv;
  uint32_t bms_age_ms;
  uint8_t source;
  uint8_t bms_valid;
  uint8_t sensorless_ok;
  uint8_t series_match;
} g30_vbus_fusion_result_t;

g30_vbus_fusion_result_t g30_vbus_fusion_eval(uint32_t pa1_mv,
                                               uint32_t bms_pack_mv,
                                               uint32_t bms_cell_sum_mv,
                                               uint16_t cell_min_mv,
                                               uint16_t cell_max_mv,
                                               uint32_t bms_age_ms,
                                               uint8_t bms_present);
const char *g30_vbus_fusion_source_name(uint8_t source);
#endif
'''
c=r'''#include "g30_vbus_fusion.h"

static uint32_t g30_absdiff_u32(uint32_t a,uint32_t b){ return a>b?a-b:b-a; }

const char *g30_vbus_fusion_source_name(uint8_t source){
  if(source==G30_VBUS_SRC_PA1) return "PA1";
  if(source==G30_VBUS_SRC_BMS_EST) return "BMS_EST";
  return "INVALID";
}

g30_vbus_fusion_result_t g30_vbus_fusion_eval(uint32_t pa1_mv,
                                               uint32_t bms_pack_mv,
                                               uint32_t bms_cell_sum_mv,
                                               uint16_t cell_min_mv,
                                               uint16_t cell_max_mv,
                                               uint32_t bms_age_ms,
                                               uint8_t bms_present){
  g30_vbus_fusion_result_t r={0};
  uint8_t cells_ok=0u,pack_ok=0u,fresh=0u,sum_ok=0u;
  r.pa1_mv=pa1_mv; r.bms_pack_mv=bms_pack_mv;
  r.bms_cell_sum_mv=bms_cell_sum_mv; r.bms_age_ms=bms_age_ms;

  fresh=(uint8_t)(bms_present && bms_age_ms<=G30_VBUS_BMS_MAX_AGE_MS);
  pack_ok=(uint8_t)(bms_pack_mv>=25000u && bms_pack_mv<=43500u);
  cells_ok=(uint8_t)(cell_min_mv>=2500u && cell_max_mv<=4500u &&
                     cell_max_mv>=cell_min_mv &&
                     bms_cell_sum_mv>=25000u && bms_cell_sum_mv<=43500u);
  sum_ok=(uint8_t)(g30_absdiff_u32(bms_pack_mv,bms_cell_sum_mv)<=500u);
  r.bms_valid=(uint8_t)(fresh && pack_ok && cells_ok && sum_ok);

  if(r.bms_valid){
    /* 10S stock pack + identical-cell 4S series extension.
     * Added 4S estimate = 4/10 of the measured ten-cell sum. */
    r.est_mv=bms_pack_mv + (uint32_t)(((uint64_t)bms_cell_sum_mv*2u + 2u)/5u);
    r.low_mv=bms_pack_mv + 4u*(uint32_t)cell_min_mv;
    r.high_mv=bms_pack_mv + 4u*(uint32_t)cell_max_mv;
    r.series_match=(uint8_t)(g30_absdiff_u32(pa1_mv,r.est_mv)<=1500u);
  }

  if(pa1_mv<=G30_VBUS_PA1_TRUST_MAX_MV){
    r.source=G30_VBUS_SRC_PA1;
    r.sensorless_ok=1u;
    if(!r.bms_valid){ r.low_mv=pa1_mv; r.high_mv=pa1_mv; }
    return r;
  }

  if(r.bms_valid){
    r.source=G30_VBUS_SRC_BMS_EST;
    r.sensorless_ok=1u;
    return r;
  }

  /* PA1 is beyond the trusted range and there is no fresh plausible BMS
   * estimate. Hall/PowerCore may ignore this result, but sensorless must not. */
  r.source=G30_VBUS_SRC_INVALID;
  r.sensorless_ok=0u;
  r.est_mv=pa1_mv;
  r.low_mv=pa1_mv;
  r.high_mv=pa1_mv;
  return r;
}
'''
(root/"common_files/src/g30_vbus_fusion.h").write_text(h)
(root/"common_files/src/g30_vbus_fusion_impl.inc").write_text(c)

p=root/"common_files/src/terminal.c"
s=p.read_text()
# include alongside local source headers
inc='#include "g30_vbus_fusion.h"\n'
if inc not in s:
    idx=s.find('#include "')
    assert idx>=0
    s=s[:idx]+inc+s[idx:]

marker='''    }else if (strcmp(argv[0], "g30_powerlock") == 0){'''
assert marker in s
block=r'''    }else if (strcmp(argv[0], "g30_vbus_fusion_sim") == 0){
        static const uint32_t sc[][7]={
          /* pa1, bmsPack, cellSum, min, max, age, present */
          {27000u,0u,0u,0u,0u,9999u,0u},
          {38200u,38200u,38210u,3809u,3832u,100u,1u},
          {47220u,38200u,38210u,3809u,3832u,100u,1u},
          {47220u,42000u,42000u,4180u,4220u,100u,1u},
          {47220u,38200u,38210u,3809u,3832u,800u,1u},
          {47220u,38200u,38210u,1800u,3832u,100u,1u},
          {44800u,32000u,32000u,3180u,3220u,100u,1u},
          {45100u,32200u,32200u,3200u,3240u,100u,1u}
        };
        unsigned i;
        for(i=0u;i<(unsigned)(sizeof(sc)/sizeof(sc[0]));i++){
          g30_vbus_fusion_result_t r=g30_vbus_fusion_eval(
            sc[i][0],sc[i][1],sc[i][2],(uint16_t)sc[i][3],(uint16_t)sc[i][4],sc[i][5],(uint8_t)sc[i][6]);
          commands_printf(phandle,
            "VBFUS_SIM i=%u pa1=%lu bms10=%lu cellsum=%lu age=%lu present=%lu valid=%u src=%s fused=%lu low=%lu high=%lu sl_ok=%u series_match=%u",
            i,(unsigned long)r.pa1_mv,(unsigned long)r.bms_pack_mv,
            (unsigned long)r.bms_cell_sum_mv,(unsigned long)r.bms_age_ms,
            (unsigned long)sc[i][6],(unsigned)r.bms_valid,
            g30_vbus_fusion_source_name(r.source),
            (unsigned long)((r.source==G30_VBUS_SRC_PA1)?r.pa1_mv:r.est_mv),
            (unsigned long)r.low_mv,(unsigned long)r.high_mv,
            (unsigned)r.sensorless_ok,(unsigned)r.series_match);
        }
        commands_printf(phandle,
          "VBFUS_SIM policy pa1_trust_max=%u bms_max_age=%u ratio=10S_plus_4S_identical_cells observer_connected=0 powerstage_locked=1",
          (unsigned)G30_VBUS_PA1_TRUST_MAX_MV,(unsigned)G30_VBUS_BMS_MAX_AGE_MS);
        return;
'''
s=s.replace(marker,block+marker,1)
p.write_text(s)

print("VBUS FUSION SIM V1 applied: pure fusion evaluator + terminal scenarios; observer remains disconnected; powerstage lock retained")

# CI trigger after included-implementation fix
