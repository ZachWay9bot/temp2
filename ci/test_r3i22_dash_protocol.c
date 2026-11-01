#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>

#include "g30_dash_proto.h"
#include "g30_dash_drive_logic.h"

typedef struct {
    g30_dash_parser parser;
    g30_dash_r2_control control;
    uint8_t gas, brake, seen;
    uint32_t last_input_ms;
    uint32_t valid, bad, cmd64, cmd65, esc64;
    uint32_t drive, coast;
} sim_t;

static unsigned make_dash_frame(uint8_t cmd, uint8_t gas, uint8_t brake, uint8_t *out) {
    const uint8_t len = (cmd == 0x64u) ? 7u : 5u;
    out[0]=0x5A; out[1]=0xA5; out[2]=len;
    out[3]=0x21; out[4]=0x20; out[5]=cmd; out[6]=0x00;
    out[7]=(cmd == 0x64u) ? 0x06u : 0x04u;
    out[8]=gas;
    out[9]=brake;
    out[10]=0x02u;
    out[11]=0x00u;
    if(cmd == 0x64u) {
        out[12]=0x17u;
        out[13]=0x01u;
    }
    unsigned end = 7u + len;
    uint16_t sum=0;
    for(unsigned i=2;i<end;i++) sum += out[i];
    sum ^= 0xFFFFu;
    out[end]=(uint8_t)sum;
    out[end+1u]=(uint8_t)(sum>>8);
    return end+2u;
}

static void accept_result(sim_t *s, int r, uint32_t now) {
    if(r < 0) { s->bad++; return; }
    if(r != 1) return;
    s->valid++;
    unsigned kind=g30_dash_input_kind(&s->parser);
    if(!kind) return;
    s->gas=s->parser.payload[1];
    s->brake=s->parser.payload[2];
    s->seen=1u;
    s->last_input_ms=now;
    if(kind==64u) { s->cmd64++; s->esc64++; }
    else if(kind==65u) s->cmd65++;
}

static void feed_bytes(sim_t *s, const uint8_t *data, unsigned n, uint32_t now) {
    for(unsigned i=0;i<n;i++)
        accept_result(s,g30_dash_feed(&s->parser,data[i],now),now);
}

static void frame(sim_t *s, uint8_t cmd, uint8_t gas, uint8_t brake, uint32_t now) {
    uint8_t b[20];
    unsigned n=make_dash_frame(cmd,gas,brake,b);
    feed_bytes(s,b,n,now);
}

static g30_dash_r2_action control(sim_t *s, uint32_t now, bool motor_ok) {
    bool fresh=s->seen && (uint32_t)(now-s->last_input_ms)<=G30_DASH_R2_STALE_MS;
    g30_dash_r2_action a=g30_dash_r2_step(&s->control,now,s->gas,s->brake,
                                          fresh,false,motor_ok);
    if(a==G30_DASH_R2_DRIVE) s->drive++;
    if(a==G30_DASH_R2_COAST) s->coast++;
    return a;
}

static void test_recorded_bus_ratio(void) {
    sim_t s={0};
    uint32_t t=0;
    /* Reproduce the observed 20 s class distribution exactly:
     * DASH65=410, DASH64=103, ESC64=103, bad_crc=0. */
    for(unsigned cycle=0;cycle<102;cycle++) {
        for(unsigned j=0;j<4;j++) { frame(&s,0x65,67,34,t); control(&s,t,true); t+=39; }
        frame(&s,0x64,67,34,t); control(&s,t,true); t+=39;
    }
    frame(&s,0x65,67,34,t); control(&s,t,true); t+=39;
    frame(&s,0x65,67,34,t); control(&s,t,true); t+=39;
    frame(&s,0x64,67,34,t); control(&s,t,true);

    assert(s.valid==513u);
    assert(s.cmd65==410u);
    assert(s.cmd64==103u);
    assert(s.esc64==103u);
    assert(s.bad==0u);
    assert(s.drive==0u && s.coast==0u);
    assert(s.control.armed==1u);
}

static void test_startup_needs_neutral(void) {
    sim_t s={0};
    for(uint32_t t=0;t<=150;t+=50) {
        frame(&s,0x65,190,34,t);
        assert(control(&s,t,true)==G30_DASH_R2_NONE);
        assert(!s.control.armed);
    }
    frame(&s,0x65,67,34,200); assert(control(&s,200,true)==G30_DASH_R2_NONE);
    frame(&s,0x65,67,34,300); assert(control(&s,300,true)==G30_DASH_R2_NONE);
    frame(&s,0x65,67,34,401); assert(control(&s,401,true)==G30_DASH_R2_NONE);
    assert(s.control.armed);
    frame(&s,0x65,190,34,402);
    assert(control(&s,402,true)==G30_DASH_R2_DRIVE);
}

static void arm_and_drive(sim_t *s, uint32_t base) {
    frame(s,0x65,67,34,base);
    assert(control(s,base,true)==G30_DASH_R2_NONE);
    frame(s,0x65,67,34,base+201);
    assert(control(s,base+201,true)==G30_DASH_R2_NONE);
    assert(s->control.armed);
    frame(s,0x65,190,34,base+202);
    assert(control(s,base+202,true)==G30_DASH_R2_DRIVE);
}

static void test_brake_override_and_rearm(void) {
    sim_t s={0};
    arm_and_drive(&s,0);
    frame(&s,0x65,190,197,220);
    assert(control(&s,220,true)==G30_DASH_R2_COAST);
    assert(!s.control.armed && s.control.brake_override);
    frame(&s,0x65,190,197,240);
    assert(control(&s,240,true)==G30_DASH_R2_NONE);
    frame(&s,0x65,190,34,260);
    assert(control(&s,260,true)==G30_DASH_R2_NONE);
    frame(&s,0x65,67,34,300);
    assert(control(&s,300,true)==G30_DASH_R2_NONE);
    frame(&s,0x65,67,34,501);
    assert(control(&s,501,true)==G30_DASH_R2_NONE);
    frame(&s,0x65,190,34,502);
    assert(control(&s,502,true)==G30_DASH_R2_DRIVE);
}

static void test_stale_and_invalid_force_coast(void) {
    sim_t s={0};
    arm_and_drive(&s,0);
    assert(control(&s,453,true)==G30_DASH_R2_COAST); /* 251 ms stale */
    assert(!s.control.armed);

    memset(&s,0,sizeof(s));
    arm_and_drive(&s,1000);
    frame(&s,0x65,255,34,1203);
    assert(control(&s,1203,true)==G30_DASH_R2_COAST);
    assert(!s.control.armed);
}

static void test_threshold_edges(void) {
    sim_t s={0};
    frame(&s,0x65,67,34,0); control(&s,0,true);
    frame(&s,0x65,67,34,201); control(&s,201,true);
    assert(s.control.armed);

    frame(&s,0x65,75,34,202);
    assert(control(&s,202,true)==G30_DASH_R2_NONE);
    frame(&s,0x65,76,34,203);
    assert(control(&s,203,true)==G30_DASH_R2_DRIVE);

    frame(&s,0x65,76,44,210);
    assert(control(&s,210,true)==G30_DASH_R2_NONE);
    frame(&s,0x65,76,45,211);
    assert(control(&s,211,true)==G30_DASH_R2_COAST);
    assert(s.control.brake_override);
}

static void test_motor_not_ready_never_torques(void) {
    sim_t s={0};
    frame(&s,0x65,67,34,0); control(&s,0,false);
    frame(&s,0x65,67,34,201); control(&s,201,false);
    assert(s.control.armed);
    frame(&s,0x65,190,34,202);
    assert(control(&s,202,false)==G30_DASH_R2_NONE);
    assert(s.drive==0u);
    assert(!s.control.driving);
}

static void test_crc_corruption_and_recovery(void) {
    uint8_t good[20];
    unsigned n=make_dash_frame(0x64,70,34,good);
    unsigned corruptions=0;
    for(unsigned pos=2;pos<n;pos++) {
        for(unsigned bit=0;bit<8;bit++) {
            sim_t s={0};
            uint8_t b[20]; memcpy(b,good,n);
            b[pos]^=(uint8_t)(1u<<bit);
            feed_bytes(&s,b,n,0);
            assert(s.valid==0u);
            frame(&s,0x64,70,34,20);
            assert(s.valid==1u && s.cmd64==1u && s.esc64==1u);
            corruptions++;
        }
    }
    assert(corruptions==(n-2u)*8u);
}

static void test_partial_timeout_and_noise(void) {
    sim_t s={0};
    uint8_t b[20];
    unsigned n=make_dash_frame(0x65,67,34,b);
    uint8_t noise[]={0x00,0xFF,0x5A,0x12,0x5A};
    feed_bytes(&s,noise,sizeof(noise),0);
    feed_bytes(&s,b,7,1);
    /* >10 ms gap discards the partial frame. */
    feed_bytes(&s,b+7,n-7,20);
    assert(s.valid==0u);
    frame(&s,0x65,67,34,21);
    assert(s.valid==1u && s.cmd65==1u && s.esc64==0u);
}

static void test_status_reply_exact(void) {
    static const uint8_t recorded_esc64[]={
        0x5A,0xA5,0x06,0x20,0x21,0x64,0x00,0x04,0x03,0x00,0x00,0x00,0x00,0x4D,0xFF
    };
    uint8_t status[6]={4,3,0,0,0,0}, out[15];
    assert(g30_dash_status_frame(status,out)==sizeof(recorded_esc64));
    assert(memcmp(out,recorded_esc64,sizeof(out))==0);
}

int main(void) {
    test_recorded_bus_ratio();
    test_startup_needs_neutral();
    test_brake_override_and_rearm();
    test_stale_and_invalid_force_coast();
    test_threshold_edges();
    test_motor_not_ready_never_torques();
    test_crc_corruption_and_recovery();
    test_partial_timeout_and_noise();
    test_status_reply_exact();
    puts("R3I22 DASH PROTOCOL SIM: PASS");
    puts("capture ratio 410xCMD65 / 103xCMD64 / 103xESC64 preserved");
    puts("startup-neutral, brake-coast, stale, invalid-input, threshold, CRC and resync checks PASS");
    return 0;
}
