#ifndef G30_DASH_PROTO_H
#define G30_DASH_PROTO_H
#include <stdint.h>
#include <string.h>
#define G30_DASH_MAX_PAYLOAD 56u
typedef struct {
    uint8_t state, index, len, src, dst, cmd, arg, lo;
    uint16_t sum;
    uint8_t payload[G30_DASH_MAX_PAYLOAD];
    uint32_t last_ms;
} g30_dash_parser;
/* Returns 1 for a checksum-valid packet, -1 for a bad checksum/length,
 * and 0 for an incomplete packet. The caller decides source/destination. */
static inline int g30_dash_feed(g30_dash_parser *p, uint8_t b, uint32_t ms) {
    if (p->state && (uint32_t)(ms-p->last_ms)>10u) p->state=0;
    p->last_ms=ms;
    switch(p->state) {
    case 0: if(b==0x5Au) p->state=1; break;
    case 1: p->state=b==0xA5u?2u:(b==0x5Au?1u:0u); break;
    case 2:
        if(b>G30_DASH_MAX_PAYLOAD){p->state=0; return -1;}
        p->len=b; p->sum=b; p->index=0; p->state=3; break;
    case 3: p->src=b; p->sum+=b; p->state=4; break;
    case 4: p->dst=b; p->sum+=b; p->state=5; break;
    case 5: p->cmd=b; p->sum+=b; p->state=6; break;
    case 6: p->arg=b; p->sum+=b; p->state=p->len?7u:8u; break;
    case 7:
        p->payload[p->index++]=b; p->sum+=b;
        if(p->index==p->len) p->state=8;
        break;
    case 8: p->lo=b; p->state=9; break;
    case 9: {
        uint16_t wire=(uint16_t)p->lo|((uint16_t)b<<8);
        uint16_t expected=(uint16_t)(p->sum^0xFFFFu);
        p->state=0;
        return wire==expected?1:-1;
    }
    default: p->state=0; break;
    }
    return 0;
}
/* Only native dashboard CMD64 requests a status reply. CMD65 is input only.
 * This classification has no motor side effects. */
static inline unsigned g30_dash_input_kind(const g30_dash_parser *p) {
    if(p->src!=0x21u || p->dst!=0x20u || p->arg!=0u || p->len<3u) return 0;
    return p->cmd==0x64u?64u:(p->cmd==0x65u?65u:0u);
}
static inline unsigned g30_dash_status_frame(const uint8_t status[6], uint8_t out[15]) {
    out[0]=0x5A;out[1]=0xA5;out[2]=6;out[3]=0x20;out[4]=0x21;out[5]=0x64;out[6]=0;
    memcpy(out+7,status,6);
    uint16_t sum=0;
    for(unsigned i=2;i<13;i++) sum+=out[i];
    sum^=0xFFFFu;out[13]=(uint8_t)sum;out[14]=(uint8_t)(sum>>8);
    return 15;
}
#endif
