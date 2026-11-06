#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include "g30_vbus_fusion.h"

static void ck(int ok,const char *msg){ if(!ok){ fprintf(stderr,"FAIL %s\n",msg); exit(2);} }

int main(void){
  g30_vbus_fusion_result_t r;
  uint32_t v;
  r=g30_vbus_fusion_eval(27000,0,0,0,0,9999,0);
  ck(r.source==G30_VBUS_SRC_PA1 && r.sensorless_ok==1,"27V PSU PA1");
  r=g30_vbus_fusion_eval(38200,38200,38210,3809,3832,100,1);
  ck(r.source==G30_VBUS_SRC_PA1 && r.bms_valid==1,"10S crosscheck");
  r=g30_vbus_fusion_eval(47220,38200,38210,3809,3832,100,1);
  ck(r.source==G30_VBUS_SRC_BMS_EST && r.sensorless_ok==1,"14S estimate selected");
  ck(r.est_mv>=53480 && r.est_mv<=53490,"14S estimate math");
  ck(r.low_mv==38200+4*3809 && r.high_mv==38200+4*3832,"bounds");
  r=g30_vbus_fusion_eval(47220,42000,42000,4180,4220,100,1);
  ck(r.est_mv==58800,"full 14S 58.8V");
  r=g30_vbus_fusion_eval(47220,38200,38210,3809,3832,501,1);
  ck(r.source==G30_VBUS_SRC_INVALID && r.sensorless_ok==0,"stale fail closed");
  r=g30_vbus_fusion_eval(47220,38200,38210,1800,3832,100,1);
  ck(r.source==G30_VBUS_SRC_INVALID && r.sensorless_ok==0,"bad cell fail closed");
  r=g30_vbus_fusion_eval(44800,32000,32000,3180,3220,100,1);
  ck(r.source==G30_VBUS_SRC_PA1,"low total trusts PA1");

  /* Exhaustive fixed-ratio sweep for plausible same-cell 10S packs. */
  for(v=25000;v<=43000;v+=25){
    uint16_t cell=(uint16_t)(v/10u);
    r=g30_vbus_fusion_eval(47220,v,v,cell,cell,100,1);
    ck(r.source==G30_VBUS_SRC_BMS_EST,"sweep source");
    ck(r.est_mv==(v + (2u*v+2u)/5u),"sweep estimate");
  }
  puts("VBFUS_HOST_SCENARIOS=PASS");
  puts("VBFUS_HOST_RATIO_SWEEP=PASS");
  puts("VBFUS_HOST_FAIL_CLOSED=PASS");
  return 0;
}
