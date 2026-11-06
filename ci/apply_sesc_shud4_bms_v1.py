from pathlib import Path

root = Path('SOURCE_KOXX3')

# -----------------------------------------------------------------------------
# Identity: layer only on the already-proven HALL14S V1 source.
# -----------------------------------------------------------------------------
p = root / 'common_files/src/defines.h'
s = p.read_text()
old = '#define HW_NAME "SESC-DRV126-POWERCORE6500-HALL14S-V1"\n#define G30_HALL14S_V1 1'
new = '#define HW_NAME "SESC-DRV126-P6500-HALL14S-SHUD4BMS-V1"\n#define G30_HALL14S_V1 1\n#define G30_SHUD4_BMS_V1 1'
assert old in s
p.write_text(s.replace(old, new, 1))

# -----------------------------------------------------------------------------
# SHUD4 limits. Defaults are documentary/fresh-config values; the runtime force
# in conf_general_setup_mc() is intentional so an older persisted VESC config
# cannot silently retain 30 A phase / 15-20 A input after an app-only flash.
# -----------------------------------------------------------------------------
p = root / 'common_files/inc/mcconf_default.h'
s = p.read_text()
s = s.replace('#define MCCONF_L_CURRENT_MAX\t\t\t30.0\t// Current limit in Amperes (Upper)',
              '#define MCCONF_L_CURRENT_MAX\t\t\t55.0\t// SHUD4 phase current limit (Upper)')
s = s.replace('#define MCCONF_L_CURRENT_MIN\t\t\t-30.0\t// Current limit in Amperes (Lower)',
              '#define MCCONF_L_CURRENT_MIN\t\t\t-55.0\t// SHUD4 phase current limit (Lower)')
s = s.replace('#define MCCONF_L_IN_CURRENT_MAX\t\t\t20.0\t// Input current limit in Amperes (Upper)',
              '#define MCCONF_L_IN_CURRENT_MAX\t\t\t39.0\t// SHUD4 battery current limit (Upper)')
p.write_text(s)

p = root / 'common_files/src/conf_general.c'
s = p.read_text()
needle = 'void conf_general_setup_mc(mc_configuration *mcconf) {\n\n\tconf_general_setup_f_sw(mcconf->foc_f_sw);'
insert = '''void conf_general_setup_mc(mc_configuration *mcconf) {

#ifdef G30_SHUD4_BMS_V1
    /* SHUD4 proven power values. Runtime-authoritative on G30 so persisted
     * VESC settings cannot leave the old 30 A / 15-20 A limits active.
     * Negative phase limit must match: physical forward is negative Iq on
     * this confirmed G30D wiring. Battery regen remains coast-only elsewhere. */
    mcconf->l_current_max = 55.0f;
    mcconf->l_current_min = -55.0f;
    mcconf->l_in_current_max = 39.0f;
#endif

\tconf_general_setup_f_sw(mcconf->foc_f_sw);'''
assert needle in s
p.write_text(s.replace(needle, insert, 1))

# -----------------------------------------------------------------------------
# SHUD4 direct-power curve. Exact reconstructed delta:
#   normalize = clamp(raw-55, 0, 120)
#   target ~= current_limit * normalize^2 / 110^2
# The final phase-current clamp is already authoritative in the motor path, so
# Q15 relative command is saturated at 1.0 after the SHUD over-range region.
# -----------------------------------------------------------------------------
p = root / 'common_files/src/g30_dash_drive_logic.h'
s = p.read_text()
old = '''static inline uint16_t g30_dash_r2_scale(uint8_t gas) {
    if(gas <= G30_DASH_R2_GAS_BEGIN) return 0u;
    if(gas >= G30_DASH_R2_GAS_FULL) return 32768u;
    return (uint16_t)(((uint32_t)(gas-G30_DASH_R2_GAS_BEGIN)*32768u) /
                 (G30_DASH_R2_GAS_FULL-G30_DASH_R2_GAS_BEGIN));
}'''
new = '''static inline uint16_t g30_dash_r2_scale(uint8_t gas) {
    /* SHUD4 DPC: raw_norm=clamp(raw-55,0,120), quadratic coefficient=110.
     * Reconstructed binary formula is raw_norm^2 / 110^2. */
    int32_t n=(int32_t)gas-55;
    if(n<0) n=0;
    if(n>120) n=120;
    uint32_t q15=((uint32_t)n*(uint32_t)n*32768u)/(110u*110u);
    if(q15>32768u) q15=32768u;
    return (uint16_t)q15;
}'''
assert old in s
p.write_text(s.replace(old, new, 1))

# -----------------------------------------------------------------------------
# Minimal stock-style BMS heartbeat on USART3, outside FOC/PWM.
# Proven stock/SHUD protocol: 5A A5 LEN SRC DST CMD ARG DATA CHECK_LO CHECK_HI,
# ESC=0x20, BMS=0x22, read cmd=0x01, reply cmd=0x04.
# Startup reads 0x10, runtime reads 0x30 at ~105 ms nominal cadence.
# No write command, no VBUS fusion, no motor/power gate.
# State is heap allocated because HALL14S has almost no static SRAM headroom.
# -----------------------------------------------------------------------------
p = root / 'common_files/src/task_LED.c'
s = p.read_text()
s = s.replace('#include "VescToSTM.h"\n', '#include "VescToSTM.h"\n#include <string.h>\n')
marker = 'extern stm_state VescToSTM_mode;\n'
bms = r'''

#ifdef G30_SHUD4_BMS_V1
#define G30_BMS_RX_N 64u
#define G30_BMS_MAX_DATA 32u
#define G30_BMS_PERIOD_MS 105u
#define G30_BMS_REPLY_TIMEOUT_MS 80u
#define G30_BMS_PRESENT_MS 500u

typedef struct {
    uint8_t rx[G30_BMS_RX_N];
    uint8_t parse_data[G30_BMS_MAX_DATA];
    uint32_t tx_count, ok_count, timeout_count, raw_count;
    uint32_t req_ms, last_ok_ms, next_tx_ms;
    uint16_t crc_bad, unexpected;
    uint16_t status, remaining, soc, pack10;
    int16_t current;
    uint8_t serial[16];
    uint8_t serial_len, live_len;
    uint8_t rd, dma_started, awaiting, startup_sent;
    uint8_t ps, len, pi, src, dst, cmd, arg, crc_lo;
    uint16_t sum;
} g30_bms_stock_state_t;

/* Only one static word is consumed; the UART/parser buffer lives in heap. */
static g30_bms_stock_state_t *g30_bms;

static uint16_t g30_bms_cksum(const uint8_t *p,uint8_t n){
    uint16_t sum=0u; uint8_t i;
    for(i=0u;i<n;i++) sum=(uint16_t)(sum+p[i]);
    return (uint16_t)(~sum);
}

static void g30_bms_build_read(uint8_t reg,uint8_t ask,uint8_t out[10]){
    uint16_t ck;
    out[0]=0x5Au; out[1]=0xA5u; out[2]=0x01u;
    out[3]=0x20u; out[4]=0x22u; out[5]=0x01u;
    out[6]=reg; out[7]=ask;
    ck=g30_bms_cksum(&out[2],6u);
    out[8]=(uint8_t)(ck&0xFFu); out[9]=(uint8_t)(ck>>8);
}

static void g30_bms_accept_reply(void){
    uint8_t n;
    if(!g30_bms) return;
    if(g30_bms->src!=0x22u || g30_bms->dst!=0x20u || g30_bms->cmd!=0x04u){
        if(g30_bms->unexpected!=0xFFFFu) g30_bms->unexpected++;
        return;
    }
    n=g30_bms->len;
    if(g30_bms->arg==0x10u){
        if(n>sizeof(g30_bms->serial)) n=sizeof(g30_bms->serial);
        memcpy(g30_bms->serial,g30_bms->parse_data,n);
        g30_bms->serial_len=n;
    }else if(g30_bms->arg==0x30u){
        g30_bms->live_len=n;
        if(n>=10u){
            g30_bms->status=(uint16_t)g30_bms->parse_data[0] | ((uint16_t)g30_bms->parse_data[1]<<8);
            g30_bms->remaining=(uint16_t)g30_bms->parse_data[2] | ((uint16_t)g30_bms->parse_data[3]<<8);
            g30_bms->soc=(uint16_t)g30_bms->parse_data[4] | ((uint16_t)g30_bms->parse_data[5]<<8);
            g30_bms->current=(int16_t)((uint16_t)g30_bms->parse_data[6] | ((uint16_t)g30_bms->parse_data[7]<<8));
            g30_bms->pack10=(uint16_t)g30_bms->parse_data[8] | ((uint16_t)g30_bms->parse_data[9]<<8);
        }
    }
    g30_bms->ok_count++;
    g30_bms->last_ok_ms=HAL_GetTick();
    g30_bms->awaiting=0u;
}

static void g30_bms_parse_byte(uint8_t b){
    uint16_t expected,got;
    if(!g30_bms) return;
    switch(g30_bms->ps){
    default:
    case 0: if(b==0x5Au) g30_bms->ps=1u; break;
    case 1: g30_bms->ps=(b==0xA5u)?2u:((b==0x5Au)?1u:0u); break;
    case 2:
        g30_bms->len=b; g30_bms->sum=b; g30_bms->pi=0u;
        g30_bms->ps=(b<=G30_BMS_MAX_DATA)?3u:0u; break;
    case 3: g30_bms->src=b; g30_bms->sum=(uint16_t)(g30_bms->sum+b); g30_bms->ps=4u; break;
    case 4: g30_bms->dst=b; g30_bms->sum=(uint16_t)(g30_bms->sum+b); g30_bms->ps=5u; break;
    case 5: g30_bms->cmd=b; g30_bms->sum=(uint16_t)(g30_bms->sum+b); g30_bms->ps=6u; break;
    case 6: g30_bms->arg=b; g30_bms->sum=(uint16_t)(g30_bms->sum+b); g30_bms->ps=g30_bms->len?7u:8u; break;
    case 7:
        if(g30_bms->pi<G30_BMS_MAX_DATA) g30_bms->parse_data[g30_bms->pi]=b;
        g30_bms->sum=(uint16_t)(g30_bms->sum+b);
        g30_bms->pi++;
        if(g30_bms->pi>=g30_bms->len) g30_bms->ps=8u;
        break;
    case 8: g30_bms->crc_lo=b; g30_bms->ps=9u; break;
    case 9:
        expected=(uint16_t)(~g30_bms->sum);
        got=(uint16_t)g30_bms->crc_lo|((uint16_t)b<<8);
        if(got==expected) g30_bms_accept_reply();
        else if(g30_bms->crc_bad!=0xFFFFu) g30_bms->crc_bad++;
        g30_bms->ps=0u;
        break;
    }
}

static uint8_t g30_bms_start_rx(void){
    if(!g30_bms) return 0u;
    (void)HAL_UART_DMAStop(&huart3);
    huart3.Init.BaudRate=115200u;
    huart3.Init.WordLength=UART_WORDLENGTH_8B;
    huart3.Init.StopBits=UART_STOPBITS_1;
    huart3.Init.Parity=UART_PARITY_NONE;
    huart3.Init.Mode=UART_MODE_TX_RX;
    huart3.Init.HwFlowCtl=UART_HWCONTROL_NONE;
    huart3.Init.OverSampling=UART_OVERSAMPLING_16;
    if(HAL_UART_Init(&huart3)!=HAL_OK) return 0u;
    memset(g30_bms->rx,0,sizeof(g30_bms->rx));
    g30_bms->rd=0u; g30_bms->ps=0u;
    if(HAL_UART_Receive_DMA(&huart3,g30_bms->rx,G30_BMS_RX_N)!=HAL_OK) return 0u;
    __HAL_DMA_DISABLE_IT(huart3.hdmarx,DMA_IT_HT|DMA_IT_TC|DMA_IT_TE);
    CLEAR_BIT(huart3.Instance->CR1,USART_CR1_PEIE);
    CLEAR_BIT(huart3.Instance->CR3,USART_CR3_EIE);
    g30_bms->dma_started=1u;
    g30_bms->next_tx_ms=HAL_GetTick()+20u;
    return 1u;
}

static HAL_StatusTypeDef g30_bms_tx(const uint8_t *fr,uint16_t n){
    /* Blocking UART TX is task-context only. 10 bytes @115200 ~=0.87 ms.
     * Interrupts, including the 16-kHz motor ISR, remain enabled. */
    return HAL_UART_Transmit(&huart3,(uint8_t*)fr,n,5u);
}

static void g30_bms_drain_dma(void){
    uint16_t left; uint8_t wr;
    if(!g30_bms || !g30_bms->dma_started || !huart3.hdmarx) return;
    left=(uint16_t)huart3.hdmarx->Instance->CNDTR;
    wr=(uint8_t)(G30_BMS_RX_N-((left<=G30_BMS_RX_N)?left:G30_BMS_RX_N));
    while(g30_bms->rd!=wr){
        uint8_t b=g30_bms->rx[g30_bms->rd];
        g30_bms->raw_count++;
        g30_bms_parse_byte(b);
        g30_bms->rd++;
        if(g30_bms->rd>=G30_BMS_RX_N) g30_bms->rd=0u;
    }
}

static void g30_bms_service_10ms(void){
    uint32_t now; uint8_t fr[10],reg,ask;
    if(!g30_bms){
        g30_bms=(g30_bms_stock_state_t*)pvPortMalloc(sizeof(*g30_bms));
        if(!g30_bms) return;
        memset(g30_bms,0,sizeof(*g30_bms));
    }
    if(!g30_bms->dma_started){ (void)g30_bms_start_rx(); return; }
    g30_bms_drain_dma();
    now=HAL_GetTick();
    if(g30_bms->awaiting && (uint32_t)(now-g30_bms->req_ms)>=G30_BMS_REPLY_TIMEOUT_MS){
        g30_bms->timeout_count++;
        g30_bms->awaiting=0u;
    }
    if((int32_t)(now-g30_bms->next_tx_ms)<0) return;
    /* Exact SHUD/stock startup discovery then regular status heartbeat. */
    if(!g30_bms->startup_sent){ reg=0x10u; ask=0x10u; g30_bms->startup_sent=1u; }
    else { reg=0x30u; ask=0x0Cu; }
    g30_bms_build_read(reg,ask,fr);
    if(g30_bms_tx(fr,sizeof(fr))==HAL_OK){
        g30_bms->tx_count++;
        g30_bms->req_ms=now;
        g30_bms->awaiting=1u;
    }
    g30_bms->next_tx_ms=now+G30_BMS_PERIOD_MS;
}

uint8_t g30_bms_stock_present(void){
    uint32_t age;
    if(!g30_bms || !g30_bms->last_ok_ms || !g30_bms->live_len) return 0u;
    age=HAL_GetTick()-g30_bms->last_ok_ms;
    return (uint8_t)(age<=G30_BMS_PRESENT_MS);
}
uint32_t g30_bms_stock_tx(void){ return g30_bms?g30_bms->tx_count:0u; }
uint32_t g30_bms_stock_ok(void){ return g30_bms?g30_bms->ok_count:0u; }
uint32_t g30_bms_stock_timeout(void){ return g30_bms?g30_bms->timeout_count:0u; }
uint16_t g30_bms_stock_crc_bad(void){ return g30_bms?g30_bms->crc_bad:0u; }
uint32_t g30_bms_stock_age_ms(void){ return (g30_bms&&g30_bms->last_ok_ms)?HAL_GetTick()-g30_bms->last_ok_ms:0xFFFFFFFFu; }
uint16_t g30_bms_stock_pack10(void){ return g30_bms?g30_bms->pack10:0u; }
uint16_t g30_bms_stock_soc(void){ return g30_bms?g30_bms->soc:0u; }
int16_t g30_bms_stock_current(void){ return g30_bms?g30_bms->current:0; }
uint8_t g30_bms_stock_live_len(void){ return g30_bms?g30_bms->live_len:0u; }
uint8_t g30_bms_stock_serial_len(void){ return g30_bms?g30_bms->serial_len:0u; }
#endif
'''
assert marker in s
s = s.replace(marker, marker + bms, 1)
needle = '\n\t\tvTaskDelay(MS_TO_TICKS(10));\n'
replace = '''
#ifdef G30_SHUD4_BMS_V1
        g30_bms_service_10ms();
#endif
\t\tvTaskDelay(MS_TO_TICKS(10));
'''
assert needle in s
p.write_text(s.replace(needle, replace, 1))

# Terminal diagnostics; no BMS write commands are exposed.
p = root / 'common_files/src/terminal.c'
s = p.read_text()
needle = '''\t}else if (strcmp(argv[0], "limits") == 0){'''
block = '''\t}else if (strcmp(argv[0], "g30_bms") == 0){
#ifdef G30_SHUD4_BMS_V1
        extern uint8_t g30_bms_stock_present(void);
        extern uint32_t g30_bms_stock_tx(void),g30_bms_stock_ok(void),g30_bms_stock_timeout(void),g30_bms_stock_age_ms(void);
        extern uint16_t g30_bms_stock_crc_bad(void),g30_bms_stock_pack10(void),g30_bms_stock_soc(void);
        extern int16_t g30_bms_stock_current(void);
        extern uint8_t g30_bms_stock_live_len(void),g30_bms_stock_serial_len(void);
        commands_printf(phandle,
          "BMS stockhb present=%u tx=%lu ok=%lu timeout=%lu crc_bad=%u age_ms=%lu serial_len=%u live30_len=%u pack10=%u soc=%u current=%d",
          (unsigned)g30_bms_stock_present(),(unsigned long)g30_bms_stock_tx(),
          (unsigned long)g30_bms_stock_ok(),(unsigned long)g30_bms_stock_timeout(),
          (unsigned)g30_bms_stock_crc_bad(),(unsigned long)g30_bms_stock_age_ms(),
          (unsigned)g30_bms_stock_serial_len(),(unsigned)g30_bms_stock_live_len(),
          (unsigned)g30_bms_stock_pack10(),(unsigned)g30_bms_stock_soc(),(int)g30_bms_stock_current());
#else
        commands_printf(phandle,"BMS stock heartbeat not compiled");
#endif
'''
assert needle in s
p.write_text(s.replace(needle, block + needle, 1))

print('SHUD4+BMS V1 applied: 55A phase, 39A battery, quadratic DPC/110, stock USART3 read heartbeat; fast FOC untouched')
