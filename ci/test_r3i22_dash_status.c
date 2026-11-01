#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "g30_dash_proto.h"

static uint16_t checksum(const uint8_t *p, unsigned n) {
    uint16_t s=0;
    for(unsigned i=2;i<n-2;i++) s=(uint16_t)(s+p[i]);
    return (uint16_t)(s ^ 0xFFFFu);
}

static void one(const uint8_t status[6]) {
    uint8_t out[15]={0};
    assert(g30_dash_status_frame(status,out)==15u);
    assert(out[0]==0x5A && out[1]==0xA5 && out[2]==6u);
    assert(out[3]==0x20 && out[4]==0x21 && out[5]==0x64 && out[6]==0u);
    assert(memcmp(out+7,status,6)==0);
    uint16_t c=checksum(out,sizeof(out));
    assert(out[13]==(uint8_t)c && out[14]==(uint8_t)(c>>8));
}

int main(void) {
    const uint8_t sport_idle[6]={4,3,0,0,0,0};
    uint8_t out[15];
    static const uint8_t recorded[]={
        0x5A,0xA5,0x06,0x20,0x21,0x64,0x00,
        0x04,0x03,0x00,0x00,0x00,0x00,0x4D,0xFF
    };
    assert(g30_dash_status_frame(sport_idle,out)==sizeof(recorded));
    assert(memcmp(out,recorded,sizeof(recorded))==0);

    const uint8_t cases[][6]={
        {1,0,0,0,0,0},
        {2,100,0,0,25,0},
        {4,50,0,0,99,4},
        {0x84,100,0,0,255,0xFF},
        {0xC2,1,0,0,1,0x80},
        {0xFF,255,255,255,255,255}
    };
    for(unsigned i=0;i<sizeof(cases)/sizeof(cases[0]);i++) one(cases[i]);

    puts("R3I22 DASH STATUS FRAME: PASS");
    puts("layout=[mode][battery][light][beep][speed][fault], ESC 20->21 CMD64 ARG00 LEN6");
    return 0;
}
