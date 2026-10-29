#include "g30_dash_proto.h"
#include <assert.h>
#include <stdio.h>

static const uint8_t dash65[]={0x5A,0xA5,0x05,0x21,0x20,0x65,0x00,0x04,0x45,0x22,0x02,0x00,0xE7,0xFE};
static const uint8_t dash64[]={0x5A,0xA5,0x07,0x21,0x20,0x64,0x00,0x06,0x46,0x22,0x02,0x00,0x17,0x01,0xCB,0xFE};
static const uint8_t esc64[]={0x5A,0xA5,0x06,0x20,0x21,0x64,0x00,0x04,0x03,0,0,0,0,0x4D,0xFF};
static int feed(g30_dash_parser *p,const uint8_t *data,unsigned n,uint32_t ms) {
    int accepted=0;
    for(unsigned i=0;i<n;i++) if(g30_dash_feed(p,data[i],ms)==1) accepted++;
    return accepted;
}
int main(void) {
    g30_dash_parser p={0};
    assert(feed(&p,dash65,sizeof(dash65),0)==1);
    assert(g30_dash_input_kind(&p)==65 && p.payload[1]==69 && p.payload[2]==34);
    assert(feed(&p,dash64,sizeof(dash64),1)==1);
    assert(g30_dash_input_kind(&p)==64 && p.payload[1]==70 && p.payload[5]==0x17 && p.payload[6]==1);
    /* The actual observed motor-fault-triggering raw values remain raw data. */
    assert(p.payload[1]==70);
    assert(feed(&p,esc64,sizeof(esc64),2)==1 && g30_dash_input_kind(&p)==0);
    uint8_t status[]={4,3,0,0,0,0},out[15];
    assert(g30_dash_status_frame(status,out)==sizeof(esc64));
    assert(memcmp(out,esc64,sizeof(out))==0);
    /* Every one-bit corruption in the checksummed body or checksum is rejected. */
    unsigned cases=0;
    for(unsigned i=2;i<sizeof(dash64);i++) for(unsigned bit=0;bit<8;bit++) {
        uint8_t damaged[sizeof(dash64)];memcpy(damaged,dash64,sizeof(damaged));damaged[i]^=(uint8_t)(1u<<bit);
        memset(&p,0,sizeof(p));
        assert(feed(&p,damaged,sizeof(damaged),0)==0);
        assert(feed(&p,dash64,sizeof(dash64),50)==1);cases++;
    }
    /* Noise, an overlapping header, partial frames and a time gap resynchronize. */
    memset(&p,0,sizeof(p));
    uint8_t noise[]={0x00,0x55,0xAA,0x5A,0x5A};feed(&p,noise,sizeof(noise),0);
    assert(feed(&p,dash65+1,sizeof(dash65)-1,1)==1);
    feed(&p,dash64,8,2);
    assert(feed(&p,dash65,sizeof(dash65),20)==1);
    /* Unsolicited source/destination/argument combinations cannot request TX. */
    p.src=0x3E;assert(g30_dash_input_kind(&p)==0);
    p.src=0x21;p.dst=0x21;assert(g30_dash_input_kind(&p)==0);
    p.dst=0x20;p.arg=1;assert(g30_dash_input_kind(&p)==0);
    p.arg=0;p.cmd=0x61;assert(g30_dash_input_kind(&p)==0);
    /* A full-sized valid payload is accepted without an out-of-bounds access. */
    uint8_t large[65]={0x5A,0xA5,56,0x21,0x20,0x64,0};
    for(unsigned i=0;i<56;i++) large[7+i]=(uint8_t)i;
    uint16_t sum=0;for(unsigned i=2;i<63;i++) sum+=large[i];sum^=0xFFFFu;
    large[63]=(uint8_t)sum;large[64]=(uint8_t)(sum>>8);
    memset(&p,0,sizeof(p));assert(feed(&p,large,sizeof(large),30)==1);
    assert(p.payload[55]==55);
    printf("PASS: recorded DASH64/65, exact ESC64 reply, %u single-bit corruptions, stream recovery, routing, max payload\n",cases);
    return 0;
}
