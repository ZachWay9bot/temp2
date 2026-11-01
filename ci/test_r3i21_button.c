#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#define GPIO_PIN_SET 1u
#define PWR_BTN_Pin 14u
#define PWR_BTN_GPIO_Port 0u
typedef enum { NO_PRESS, SINGLE_PRESS, LONG_PRESS, DOUBLE_PRESS, VERY_LONG_PRESS } eButtonEvent;
static uint32_t mock_ms;
static uint8_t mock_btn;
uint32_t HAL_GetTick(void) { return mock_ms; }
uint8_t HAL_GPIO_ReadPin(int port, int pin) { (void)port; (void)pin; return mock_btn; }

uint8_t buttonState(void) {
    static uint8_t initialized, stable, candidate;
    static uint32_t candidate_since;
    uint32_t now = HAL_GetTick();
    uint8_t raw = (HAL_GPIO_ReadPin(PWR_BTN_GPIO_Port, PWR_BTN_Pin) == GPIO_PIN_SET);
    if(!initialized) { initialized=1u; stable=candidate=raw; candidate_since=now; }
    if(raw != candidate) { candidate=raw; candidate_since=now; }
    if(candidate != stable && (uint32_t)(now-candidate_since) >= 30u) stable=candidate;
    return stable;
}
eButtonEvent getButtonEvent(void) {
    static uint8_t pressed, pending;
    static uint32_t pressed_at, released_at;
    uint32_t now=HAL_GetTick();
    uint8_t down=buttonState();
    if(down && !pressed) {
        pressed=1u;
        pressed_at=now;
        if(pending==1u && (uint32_t)(now-released_at)<=250u) pending=2u;
    } else if(!down && pressed) {
        pressed=0u;
        uint32_t held_ms=(uint32_t)(now-pressed_at);
        if(held_ms>=2500u) { pending=0u; return LONG_PRESS; }
        if(held_ms>=30u) {
            if(pending==2u) { pending=0u; return DOUBLE_PRESS; }
            pending=1u;
            released_at=now;
        } else if(pending==2u) {
            pending=1u;
        }
    }
    if(!pressed && pending==1u && (uint32_t)(now-released_at)>250u) {
        pending=0u;
        return SINGLE_PRESS;
    }
    return NO_PRESS;
}
static unsigned n_single,n_double,n_long,n_very;
static void tick_until(uint32_t end,uint8_t button) {
    mock_btn=button;
    while(mock_ms<end) {
        eButtonEvent ev=getButtonEvent();
        if(ev==SINGLE_PRESS)n_single++;
        if(ev==DOUBLE_PRESS)n_double++;
        if(ev==LONG_PRESS)n_long++;
        if(ev==VERY_LONG_PRESS)n_very++;
        mock_ms++;
    }
}
static void fail_if(bool cond,const char *why) {
    if(cond) { fprintf(stderr,"FAIL: %s\n",why); exit(1); }
}
int main(int argc,char **argv) {
    if(argc!=2) return 2;
    tick_until(200,0);
    if(!strcmp(argv[1],"single150")) {
        tick_until(350,1); tick_until(700,0);
        fail_if(n_single!=1||n_double||n_long||n_very,"150ms single");
    } else if(!strcmp(argv[1],"single950")) {
        tick_until(1150,1); tick_until(1500,0);
        fail_if(n_single!=1||n_double||n_long||n_very,"950ms single");
    } else if(!strcmp(argv[1],"double_long2")) {
        tick_until(320,1); tick_until(400,0); tick_until(500,1); tick_until(1300,0);
        fail_if(n_single||n_double!=1||n_long||n_very,"double with 800ms second press");
    } else if(!strcmp(argv[1],"double_bounce2")) {
        tick_until(320,1); tick_until(400,0); tick_until(410,1); tick_until(800,0);
        fail_if(n_single!=1||n_double||n_long||n_very,"bounced second press preserves first");
    } else if(!strcmp(argv[1],"long")) {
        tick_until(3100,1); tick_until(3450,0);
        fail_if(n_single||n_double||n_long!=1||n_very,"2.9s long press");
    } else if(!strcmp(argv[1],"verylong")) {
        tick_until(6100,1); tick_until(6550,0);
        fail_if(n_single||n_double||n_long!=1||n_very,"5.9s hold emits one long");
    } else if(!strcmp(argv[1],"bounce")) {
        tick_until(205,1); tick_until(600,0);
        fail_if(n_single||n_double||n_long||n_very,"5ms bounce");
    } else return 2;
    printf("PASS %-15s single=%u double=%u long=%u very=%u\n",argv[1],n_single,n_double,n_long,n_very);
    return 0;
}
