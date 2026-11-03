#include <assert.h>
#include <stdio.h>
#include "g30_bms_logic.h"
int main(void){
 g30_bms_control c={0}; uint8_t f[10];
 const uint8_t id[]={0x5a,0xa5,1,0x20,0x22,1,0x10,0x10,0x9b,0xff};
 const uint8_t status[]={0x5a,0xa5,1,0x20,0x22,1,0x30,12,0x7f,0xff};
 assert(g30_bms_next_read(&c,0,f)); assert(!memcmp(f,id,10));
 assert(!g30_bms_next_read(&c,104,f)); assert(g30_bms_next_read(&c,105,f));
 g30_dash_parser p={0}; for(unsigned i=0;i<10;i++) assert(g30_dash_feed(&p,f[i],105)==(i==9?1:0));
 assert(!g30_bms_accept(&c,&p,105));
 p.src=0x22;p.dst=0x20;p.cmd=4;p.arg=0x10;p.len=16;
 assert(g30_bms_accept(&c,&p,106));assert(c.identity_seen);
 assert(g30_bms_next_read(&c,210,f));assert(!memcmp(f,status,10));
 p.arg=0x30;p.len=11;assert(!g30_bms_accept(&c,&p,211));
 p.len=12;p.src=0x21;assert(!g30_bms_accept(&c,&p,211));
 p.src=0x22;p.payload[0]=0x34;assert(g30_bms_accept(&c,&p,211));
 assert(c.status[0]==0x34);assert(g30_bms_status_fresh(&c,1211));assert(!g30_bms_status_fresh(&c,1212));
 c.last_tx_ms=0xfffffff0u;assert(!g30_bms_next_read(&c,20,f));assert(g30_bms_next_read(&c,100,f));
 memset(&p,0,sizeof(p));f[8]^=1;for(unsigned i=0;i<10;i++){int r=g30_dash_feed(&p,f[i],100);if(i==9)assert(r==-1);}
 puts("R3I30 BMS: golden requests, parser CRC, reply ownership/length, freshness, retries, tick wrap PASS");
}
