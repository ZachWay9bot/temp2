#include <assert.h>
#include <stdint.h>
#include <stdio.h>

enum {
    M365_MODE_DRIVE=0,
    M365_MODE_SLOW=2,
    M365_MODE_SPORT=4,
    M365_MODE_CHARGE=8,
    M365_MODE_OFF=16,
    M365_MODE_LOCK=32,
    M365_MODE_MPH=64,
    M365_MODE_TEMP=128
};

static uint8_t set_speed_mode(uint8_t mode, uint8_t speed) {
    mode &= 0xF8u;
    mode |= speed;
    return mode;
}

static uint8_t double_press_next(uint8_t mode) {
    switch(mode & 0x07u) {
    case M365_MODE_DRIVE: return set_speed_mode(mode,M365_MODE_SPORT);
    case M365_MODE_SPORT: return set_speed_mode(mode,M365_MODE_SLOW);
    case M365_MODE_SLOW:  return set_speed_mode(mode,M365_MODE_DRIVE);
    default: return mode;
    }
}

int main(void) {
    static const uint8_t uppers[]={
        0,
        M365_MODE_TEMP,
        M365_MODE_MPH,
        M365_MODE_LOCK,
        M365_MODE_CHARGE,
        M365_MODE_OFF,
        (uint8_t)(M365_MODE_TEMP|M365_MODE_MPH),
        0xF8u
    };
    for(unsigned i=0;i<sizeof(uppers);i++) {
        uint8_t u=uppers[i]&0xF8u;
        uint8_t a=double_press_next((uint8_t)(u|M365_MODE_DRIVE));
        uint8_t b=double_press_next((uint8_t)(u|M365_MODE_SPORT));
        uint8_t c=double_press_next((uint8_t)(u|M365_MODE_SLOW));
        assert((a&0x07u)==M365_MODE_SPORT && (a&0xF8u)==u);
        assert((b&0x07u)==M365_MODE_SLOW  && (b&0xF8u)==u);
        assert((c&0x07u)==M365_MODE_DRIVE && (c&0xF8u)==u);
    }
    puts("R3I22 MODE BUTTON: PASS upper status bits preserved");
    return 0;
}
