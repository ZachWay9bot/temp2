from pathlib import Path

ROOT=Path("SOURCE_KOXX3")
SRC=ROOT/"common_files/src"

def one(path, old, new, label):
    p=path
    s=p.read_text()
    n=s.count(old)
    if n!=1:
        raise SystemExit(f"{label}: expected one anchor, got {n}")
    p.write_text(s.replace(old,new,1))

one(SRC/"defines.h",
    '#define HW_NAME "G30D-FO76-PUSHSTART-R3I2"',
    '#define HW_NAME "G30D-FO76-PUSHSTART-R3I3"',
    "build id")

# The stock SmartESC RCM table has only two entries. On G30 those are already
# consumed by the real temperature sensor and the real bus-voltage sensor.
# R3I needs three more registered ADC1 regular channels for BEMF A/B/C.
p=SRC/"regular_conversion_manager.c"; s=p.read_text()
old='#define RCM_MAX_CONV  2\n'
new='''#ifdef G30P
#define RCM_MAX_CONV  5
#else
#define RCM_MAX_CONV  2
#endif
'''
if old not in s: raise SystemExit("RCM_MAX_CONV anchor missing")
p.write_text(s.replace(old,new,1))

# Tiny read-only diagnostics so a failed precheck tells us whether registration
# itself failed. No extra persistent buffers are allocated.
p=SRC/"g30_r3i_pushstart.h"; s=p.read_text()
old='''uint8_t g30_r3i_start_pending(void);
void g30_r3i_start_consumed(void);
uint32_t g30_r3i_active_age_ms(void);
'''
new='''uint8_t g30_r3i_start_pending(void);
void g30_r3i_start_consumed(void);
uint8_t g30_r3i_adc_ready(void);
uint8_t g30_r3i_adc_handle_a(void);
uint8_t g30_r3i_adc_handle_b(void);
uint8_t g30_r3i_adc_handle_c(void);
uint32_t g30_r3i_active_age_ms(void);
'''
if old not in s: raise SystemExit("pushstart diagnostic header anchor missing")
p.write_text(s.replace(old,new,1))

p=SRC/"g30_r3i_pushstart.c"; s=p.read_text()
old='''uint8_t g30_r3i_start_pending(void){return start_request;}
void g30_r3i_start_consumed(void){start_request=0u;}
'''
new='''uint8_t g30_r3i_start_pending(void){return start_request;}
void g30_r3i_start_consumed(void){start_request=0u;}
uint8_t g30_r3i_adc_ready(void){return init_done;}
uint8_t g30_r3i_adc_handle_a(void){return ha;}
uint8_t g30_r3i_adc_handle_b(void){return hb;}
uint8_t g30_r3i_adc_handle_c(void){return hc;}
'''
if old not in s: raise SystemExit("pushstart diagnostic implementation anchor missing")
p.write_text(s.replace(old,new,1))

p=SRC/"terminal.c"; s=p.read_text()
old='''        commands_printf(phandle,"mcstate=%u pwm_off=%u start_pending=%u",
            (unsigned)STM_GetState(&STM[M1]),(unsigned)PWM_Handle_M1._Super.PWM_off,
            (unsigned)g30_r3i_start_pending());
'''
new='''        commands_printf(phandle,"mcstate=%u pwm_off=%u start_pending=%u adc_ready=%u handles=%u,%u,%u",
            (unsigned)STM_GetState(&STM[M1]),(unsigned)PWM_Handle_M1._Super.PWM_off,
            (unsigned)g30_r3i_start_pending(),(unsigned)g30_r3i_adc_ready(),
            (unsigned)g30_r3i_adc_handle_a(),(unsigned)g30_r3i_adc_handle_b(),
            (unsigned)g30_r3i_adc_handle_c());
'''
if old not in s: raise SystemExit("terminal R3I status anchor missing")
s=s.replace(old,new,1)
s=s.replace('FO76_R3I2 pushstart_sensorless=1','FO76_R3I3 pushstart_sensorless=1',1)
p.write_text(s)

print("R3I3 transform applied")
