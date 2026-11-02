#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include "g30_dash_drive_logic.h"

static void expect(bool c,const char *m){
    if(!c){fprintf(stderr,"FAIL: %s\n",m);exit(1);}
}

int main(void){
    uint16_t half=g30_dash_r2_scale(121u);
    uint16_t full=g30_dash_r2_scale(195u);
    expect(half>=13100u && half<=13110u,"measured half throttle must map to ~40%");
    expect(full==32768u,"measured full throttle must map to full torque");
    expect(g30_dash_r3i23_startup_limit(half,0u)==half,"half throttle unchanged at start");
    expect(g30_dash_r3i23_startup_limit(full,0u)==13107u,"full throttle capped to 40% at start");
    expect(g30_dash_r3i23_startup_limit(full,100u)==18022u,"full throttle 55% at 100ms");
    expect(g30_dash_r3i23_startup_limit(full,200u)==22937u,"full throttle 70% at 200ms");
    expect(g30_dash_r3i23_startup_limit(full,300u)==27852u,"full throttle 85% at 300ms");
    expect(g30_dash_r3i23_startup_limit(full,400u)==32768u,"full throttle released at 400ms");
    expect(g30_dash_r3i23_startup_limit(full,800u)==32768u,"normal full throttle unchanged after startup");
    expect(g30_dash_r3i23_startup_limit(0u,0u)==0u,"zero remains zero");
    printf("R3I23 STARTUP RAMP: PASS half=%u full=%u cap0=%u cap100=%u cap200=%u cap300=%u cap400=%u\n",
        half,full,
        g30_dash_r3i23_startup_limit(full,0u),
        g30_dash_r3i23_startup_limit(full,100u),
        g30_dash_r3i23_startup_limit(full,200u),
        g30_dash_r3i23_startup_limit(full,300u),
        g30_dash_r3i23_startup_limit(full,400u));
    return 0;
}
