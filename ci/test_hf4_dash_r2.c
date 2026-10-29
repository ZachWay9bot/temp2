#include <assert.h>
#include <stdio.h>
#include "g30_dash_drive_logic.h"

static void zero(g30_dash_r2_control *c) {*c = (g30_dash_r2_control){0};}
static g30_dash_r2_action step(g30_dash_r2_control *c,unsigned t,unsigned g,unsigned b,int fresh,int remote,int motor){
 return g30_dash_r2_step(c,t,(uint8_t)g,(uint8_t)b,fresh,remote,motor);
}
int main(void) {
 g30_dash_r2_control c;
 zero(&c);
 assert(G30_DASH_R2_GAS_IDLE==67u && G30_DASH_R2_GAS_FULL==190u);
 assert(G30_DASH_R2_BRAKE_IDLE==34u);
 assert(g30_dash_r2_scale(67u)==0u);
 assert(g30_dash_r2_scale(75u)==0u);
 assert(g30_dash_r2_scale(190u)==32768u);
 assert(g30_dash_r2_scale(120u)>0 && g30_dash_r2_scale(120u)<32768u);
 assert(step(&c,0,190,34,1,0,1)==G30_DASH_R2_NONE);
 assert(step(&c,250,190,34,1,0,1)==G30_DASH_R2_NONE);
 assert(step(&c,300,67,34,1,0,1)==G30_DASH_R2_NONE);
 assert(step(&c,501,67,34,1,0,1)==G30_DASH_R2_NONE);
 assert(c.armed);
 assert(step(&c,502,120,34,1,0,1)==G30_DASH_R2_DRIVE);
 assert(step(&c,520,120,34,1,0,1)==G30_DASH_R2_NONE);
 assert(step(&c,542,120,34,1,0,1)==G30_DASH_R2_DRIVE);
 assert(step(&c,560,67,34,1,0,1)==G30_DASH_R2_COAST);
 assert(step(&c,561,67,34,1,0,1)==G30_DASH_R2_NONE);
 assert(step(&c,602,190,34,1,0,1)==G30_DASH_R2_DRIVE);
 assert(step(&c,620,79,197,1,0,1)==G30_DASH_R2_COAST);
 assert(!c.armed && c.brake_override);
 assert(step(&c,640,79,197,1,0,1)==G30_DASH_R2_NONE);
 assert(step(&c,641,190,34,1,0,1)==G30_DASH_R2_NONE);
 assert(step(&c,660,67,34,1,0,1)==G30_DASH_R2_NONE);
 assert(step(&c,860,67,34,1,0,1)==G30_DASH_R2_NONE);
 assert(step(&c,861,190,34,1,0,1)==G30_DASH_R2_DRIVE);
 assert(step(&c,880,190,34,0,0,1)==G30_DASH_R2_COAST);
 assert(!c.armed);
 assert(step(&c,900,67,34,1,0,1)==G30_DASH_R2_NONE);
 assert(step(&c,1101,67,34,1,0,1)==G30_DASH_R2_NONE);
 assert(step(&c,1102,190,34,1,0,1)==G30_DASH_R2_DRIVE);
 assert(step(&c,1120,255,34,1,0,1)==G30_DASH_R2_COAST);
 zero(&c); step(&c,0,67,34,1,0,1);step(&c,201,67,34,1,0,1);
 assert(step(&c,202,190,34,1,0,1)==G30_DASH_R2_DRIVE);
 g30_dash_r2_remote_claim(&c);
 assert(step(&c,230,190,34,1,1,1)==G30_DASH_R2_NONE);
 assert(step(&c,240,79,197,1,1,1)==G30_DASH_R2_COAST);
 assert(step(&c,241,79,197,1,1,1)==G30_DASH_R2_NONE);
 assert(step(&c,242,67,34,1,1,1)==G30_DASH_R2_NONE);
 assert(step(&c,260,190,34,1,0,1)==G30_DASH_R2_NONE);
 zero(&c);step(&c,0,67,34,1,0,1);step(&c,201,67,34,1,0,1);
 assert(step(&c,202,190,34,1,0,0)==G30_DASH_R2_NONE);
 assert(step(&c,203,190,34,1,0,1)==G30_DASH_R2_DRIVE);
 assert(step(&c,204,190,34,1,0,0)==G30_DASH_R2_COAST);
 puts("HF4 DASH R2: assertions PASS");
 return 0;
}
