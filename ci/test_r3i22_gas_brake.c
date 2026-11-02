#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include "g30_dash_drive_logic.h"

static void expect(bool cond, const char *msg) {
    if(!cond) { fprintf(stderr, "FAIL: %s\n", msg); exit(1); }
}

int main(void) {
    g30_dash_r2_control c = {0};
    g30_dash_r2_action a;

    expect(g30_dash_r2_scale(67u)==0u, "idle gas must be zero torque");
    expect(g30_dash_r2_scale(75u)==0u, "gas begin threshold must still be zero torque");
    expect(g30_dash_r2_scale(190u)==32768u, "full gas must map to full relative torque");
    expect(g30_dash_r2_scale(210u)==32768u, "valid high gas must clamp at full torque");

    a=g30_dash_r2_step(&c,0u,67u,34u,true,false,true);
    expect(a==G30_DASH_R2_NONE && !c.armed, "neutral start must not arm immediately");
    a=g30_dash_r2_step(&c,199u,67u,34u,true,false,true);
    expect(a==G30_DASH_R2_NONE && !c.armed, "neutral before 200ms must stay disarmed");
    a=g30_dash_r2_step(&c,200u,67u,34u,true,false,true);
    expect(a==G30_DASH_R2_NONE && c.armed, "neutral at 200ms must arm");

    a=g30_dash_r2_step(&c,201u,120u,34u,true,false,true);
    expect(a==G30_DASH_R2_DRIVE && c.driving, "armed half gas must request drive");
    a=g30_dash_r2_step(&c,220u,120u,34u,true,false,true);
    expect(a==G30_DASH_R2_NONE, "drive command must be rate-limited before 40ms");
    a=g30_dash_r2_step(&c,241u,120u,34u,true,false,true);
    expect(a==G30_DASH_R2_DRIVE, "drive command must refresh at 40ms");

    a=g30_dash_r2_step(&c,242u,190u,45u,true,false,true);
    expect(a==G30_DASH_R2_COAST && !c.driving && !c.armed && c.brake_override,
           "brake threshold must coast and disarm even at full gas");
    a=g30_dash_r2_step(&c,243u,190u,198u,true,false,true);
    expect(a==G30_DASH_R2_NONE && c.brake_override, "held brake must not spam coast commands");

    a=g30_dash_r2_step(&c,244u,190u,34u,true,false,true);
    expect(a==G30_DASH_R2_NONE && !c.armed, "brake release with gas held must remain disarmed");
    a=g30_dash_r2_step(&c,300u,67u,34u,true,false,true);
    expect(a==G30_DASH_R2_NONE && !c.armed, "neutral rearm starts after brake release");
    a=g30_dash_r2_step(&c,500u,67u,34u,true,false,true);
    expect(c.armed, "neutral after brake must re-arm after 200ms");

    a=g30_dash_r2_step(&c,501u,120u,34u,true,false,false);
    expect(a==G30_DASH_R2_NONE && !c.driving, "motor-not-ready must block drive");
    a=g30_dash_r2_step(&c,502u,120u,34u,true,false,true);
    expect(a==G30_DASH_R2_DRIVE && c.driving, "ready motor may drive after prior arm");

    a=g30_dash_r2_step(&c,503u,120u,34u,false,false,true);
    expect(a==G30_DASH_R2_COAST && !c.driving, "stale dashboard data must coast active drive");

    c=(g30_dash_r2_control){0};
    a=g30_dash_r2_step(&c,0u,211u,34u,true,false,true);
    expect(a==G30_DASH_R2_NONE && !c.armed && !c.driving, "gas > input max must be rejected");
    a=g30_dash_r2_step(&c,1u,67u,211u,true,false,true);
    expect(a==G30_DASH_R2_NONE && !c.armed && !c.driving, "brake > input max must be rejected");

    c=(g30_dash_r2_control){0};
    a=g30_dash_r2_step(&c,0u,67u,34u,true,false,true);
    a=g30_dash_r2_step(&c,200u,67u,34u,true,false,true);
    expect(c.armed, "precondition: armed before remote claim");
    a=g30_dash_r2_step(&c,201u,120u,34u,true,true,true);
    expect(a==G30_DASH_R2_NONE && !c.armed && !c.driving, "remote VESC claim must suppress dash drive");
    a=g30_dash_r2_step(&c,202u,120u,45u,true,true,true);
    expect(a==G30_DASH_R2_COAST && c.brake_override, "physical brake must coast remote VESC once");
    a=g30_dash_r2_step(&c,203u,120u,45u,true,true,true);
    expect(a==G30_DASH_R2_NONE, "held brake during remote claim must not repeat coast edge");

    printf("R3I22 GAS/BRAKE: assertions PASS\n");
    return 0;
}
