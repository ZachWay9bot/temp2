#!/usr/bin/env python3
from pathlib import Path

root=Path("SOURCE_KOXX3")

# Build ID
p=root/"common_files/src/defines.h"
s=p.read_text()
old='#define HW_NAME "SESC-DRV126-POWERCORE6500-BMSTEL-V2"'
new='#define HW_NAME "SESC-DRV126-POWERCORE6500-BMS-FULL-AUDIT-V1"'
assert old in s
p.write_text(s.replace(old,new,1))

# Header API
p=root/"common_files/src/task_LED.h"
s=p.read_text()
start=s.index("/* G30 BMSTEL V2:")
end=s.index("\n\n\n\n#endif", start)
rep='''/* G30 BMS FULL AUDIT V1: read-only USART3 auto-probe. */
uint16_t g30_bms_probe_round(void);
uint8_t g30_bms_probe_slot(void);
uint32_t g30_bms_probe_baud(uint8_t slot);
uint8_t g30_bms_probe_reg(uint8_t slot);
uint8_t g30_bms_probe_ask(uint8_t slot);
uint16_t g30_bms_probe_tx(uint8_t slot);
uint16_t g30_bms_probe_raw(uint8_t slot);
uint16_t g30_bms_probe_valid(uint8_t slot);
uint16_t g30_bms_probe_raw_total(void);
uint16_t g30_bms_probe_valid_total(void);
uint16_t g30_bms_probe_crc_bad(void);
uint8_t g30_bms_probe_last_src(void);
uint8_t g30_bms_probe_last_dst(void);
uint8_t g30_bms_probe_last_cmd(void);
uint8_t g30_bms_probe_last_arg(void);
uint8_t g30_bms_probe_last_len(void);
uint8_t g30_bms_probe_raw_last_byte(uint8_t back);
'''
s=s[:start]+rep+s[end:]
p.write_text(s)

# Replace complete BMSTEL block inside existing low-priority LED task.
p=root/"common_files/src/task_LED.c"
s=p.read_text()
start=s.index("/* -------------------------------------------------------------------------\n * G30 BMSTEL V2")
end=s.index("void prv_LED_blink(uint32_t speed){", start)
block=r'''/* -------------------------------------------------------------------------
 * G30 BMS FULL AUDIT V1
 *
 * Read-only automatic probe of the stock G30 BMS UART. No BMS writes, no
 * motor commands, no C/CHRG_MOD manipulation.
 *
 * Probe matrix:
 *   115200 and 76800 baud
 *   READ registers 0x10,0x17,0x30,0x34,0x40
 *   source 0x20 (ESC), destination 0x22 (BMS), command 0x01 (READ)
 *
 * Every raw RX byte is counted before parsing. Checksum-valid frames from
 * source 0x22 to destination 0x20 are counted independently of response CMD,
 * so protocol variants cannot disappear merely because a parser expectation
 * was too strict.
 *
 * Uses the existing 10 ms LED task and existing USART3 circular RX DMA. No
 * extra FreeRTOS task and no DMA IRQ load are introduced.
 * ------------------------------------------------------------------------- */

#define G30_BMS_RX_N 32u
#define G30_BMS_PROBE_SLOTS 10u
#define G30_BMS_PROBE_PER_BAUD 5u

static const uint8_t g30_bms_probe_regs[G30_BMS_PROBE_PER_BAUD]={0x10u,0x17u,0x30u,0x34u,0x40u};
static const uint8_t g30_bms_probe_asks[G30_BMS_PROBE_PER_BAUD]={16u,2u,12u,2u,20u};

typedef struct {
    uint16_t tx_by[G30_BMS_PROBE_SLOTS];
    uint16_t raw_by[G30_BMS_PROBE_SLOTS];
    uint16_t valid_by[G30_BMS_PROBE_SLOTS];
    uint16_t raw_total;
    uint16_t valid_total;
    uint16_t crc_bad;
    uint16_t sum;
    uint16_t round;
    uint8_t raw_last[8];
    uint8_t raw_last_i;
    uint8_t rx_dma[G30_BMS_RX_N];
    uint8_t rd;
    uint8_t dma_started;
    uint8_t slot;
    uint8_t phase;
    uint8_t wait_ticks;
    uint8_t sends;
    uint8_t ps;
    uint8_t len;
    uint8_t pi;
    uint8_t src;
    uint8_t dst;
    uint8_t cmd;
    uint8_t arg;
    uint8_t crc_lo;
    uint8_t last_src;
    uint8_t last_dst;
    uint8_t last_cmd;
    uint8_t last_arg;
    uint8_t last_len;
} g30_bms_probe_state_t;

static g30_bms_probe_state_t *g30_bms_probe_state;

#define BP(s) (g30_bms_probe_state->s)

static uint32_t g30_bms_probe_baud_i(uint8_t slot){
    return (slot<G30_BMS_PROBE_PER_BAUD)?115200u:76800u;
}
static uint8_t g30_bms_probe_local(uint8_t slot){
    return (uint8_t)(slot%G30_BMS_PROBE_PER_BAUD);
}

uint16_t g30_bms_probe_round(void){ return g30_bms_probe_state?BP(round):0u; }
uint8_t g30_bms_probe_slot(void){ return g30_bms_probe_state?BP(slot):0u; }
uint32_t g30_bms_probe_baud(uint8_t slot){ return (slot<G30_BMS_PROBE_SLOTS)?g30_bms_probe_baud_i(slot):0u; }
uint8_t g30_bms_probe_reg(uint8_t slot){
    return (slot<G30_BMS_PROBE_SLOTS)?g30_bms_probe_regs[g30_bms_probe_local(slot)]:0u;
}
uint8_t g30_bms_probe_ask(uint8_t slot){
    return (slot<G30_BMS_PROBE_SLOTS)?g30_bms_probe_asks[g30_bms_probe_local(slot)]:0u;
}
uint16_t g30_bms_probe_tx(uint8_t slot){ return (g30_bms_probe_state && slot<G30_BMS_PROBE_SLOTS)?BP(tx_by)[slot]:0u; }
uint16_t g30_bms_probe_raw(uint8_t slot){ return (g30_bms_probe_state && slot<G30_BMS_PROBE_SLOTS)?BP(raw_by)[slot]:0u; }
uint16_t g30_bms_probe_valid(uint8_t slot){ return (g30_bms_probe_state && slot<G30_BMS_PROBE_SLOTS)?BP(valid_by)[slot]:0u; }
uint16_t g30_bms_probe_raw_total(void){ return g30_bms_probe_state?BP(raw_total):0u; }
uint16_t g30_bms_probe_valid_total(void){ return g30_bms_probe_state?BP(valid_total):0u; }
uint16_t g30_bms_probe_crc_bad(void){ return g30_bms_probe_state?BP(crc_bad):0u; }
uint8_t g30_bms_probe_last_src(void){ return g30_bms_probe_state?BP(last_src):0u; }
uint8_t g30_bms_probe_last_dst(void){ return g30_bms_probe_state?BP(last_dst):0u; }
uint8_t g30_bms_probe_last_cmd(void){ return g30_bms_probe_state?BP(last_cmd):0u; }
uint8_t g30_bms_probe_last_arg(void){ return g30_bms_probe_state?BP(last_arg):0u; }
uint8_t g30_bms_probe_last_len(void){ return g30_bms_probe_state?BP(last_len):0u; }
uint8_t g30_bms_probe_raw_last_byte(uint8_t back){
    if(!g30_bms_probe_state || back>=8u || BP(raw_total)==0u) return 0u;
    return BP(raw_last)[(uint8_t)((BP(raw_last_i)+7u-back)&7u)];
}

static void g30_bms_probe_parse_byte(uint8_t b){
    switch(BP(ps)){
    default:
    case 0:
        if(b==0x5au) BP(ps)=1u;
        break;
    case 1:
        if(b==0xa5u) BP(ps)=2u;
        else BP(ps)=(b==0x5au)?1u:0u;
        break;
    case 2:
        BP(len)=b;
        if(BP(len)>32u){ BP(ps)=0u; break; }
        BP(sum)=b; BP(pi)=0u; BP(ps)=3u;
        break;
    case 3:
        BP(src)=b; BP(sum)=(uint16_t)(BP(sum)+b); BP(ps)=4u;
        break;
    case 4:
        BP(dst)=b; BP(sum)=(uint16_t)(BP(sum)+b); BP(ps)=5u;
        break;
    case 5:
        BP(cmd)=b; BP(sum)=(uint16_t)(BP(sum)+b); BP(ps)=6u;
        break;
    case 6:
        BP(arg)=b; BP(sum)=(uint16_t)(BP(sum)+b); BP(ps)=BP(len)?7u:8u;
        break;
    case 7:
        BP(sum)=(uint16_t)(BP(sum)+b);
        BP(pi)++;
        if(BP(pi)>=BP(len)) BP(ps)=8u;
        break;
    case 8:
        BP(crc_lo)=b; BP(ps)=9u;
        break;
    case 9: {
        uint16_t expected=(uint16_t)(~BP(sum));
        uint16_t got=(uint16_t)BP(crc_lo)|((uint16_t)b<<8);
        if(got==expected){
            if(BP(src)==0x22u && BP(dst)==0x20u){
                uint8_t slot=BP(slot);
                if(BP(valid_total)!=0xffffu) BP(valid_total)++;
                if(BP(valid_by)[slot]!=0xffffu) BP(valid_by)[slot]++;
                BP(last_src)=BP(src); BP(last_dst)=BP(dst); BP(last_cmd)=BP(cmd);
                BP(last_arg)=BP(arg); BP(last_len)=BP(len);
            }
        }else{
            if(BP(crc_bad)!=0xffffu) BP(crc_bad)++;
        }
        BP(ps)=0u;
        break;
    }
    }
}

static uint8_t g30_bms_probe_start_rx(uint32_t baud){
    if(BP(dma_started)){
        (void)HAL_UART_DMAStop(&huart3);
        BP(dma_started)=0u;
    }
    huart3.Init.BaudRate=baud;
    if(HAL_UART_Init(&huart3)!=HAL_OK) return 0u;
    memset(BP(rx_dma),0,sizeof(BP(rx_dma)));
    BP(rd)=0u; BP(ps)=0u;
    if(HAL_UART_Receive_DMA(&huart3,BP(rx_dma),G30_BMS_RX_N)!=HAL_OK) return 0u;
    __HAL_DMA_DISABLE_IT(huart3.hdmarx,DMA_IT_HT|DMA_IT_TC|DMA_IT_TE);
    CLEAR_BIT(huart3.Instance->CR1,USART_CR1_PEIE);
    CLEAR_BIT(huart3.Instance->CR3,USART_CR3_EIE);
    BP(dma_started)=1u;
    return 1u;
}

static void g30_bms_probe_build_read(uint8_t reg,uint8_t ask,uint8_t out[10]){
    uint16_t sum,ck;
    out[0]=0x5au; out[1]=0xa5u; out[2]=0x01u; out[3]=0x20u; out[4]=0x22u;
    out[5]=0x01u; out[6]=reg; out[7]=ask;
    sum=(uint16_t)(out[2]+out[3]+out[4]+out[5]+out[6]+out[7]);
    ck=(uint16_t)(~sum);
    out[8]=(uint8_t)(ck&0xffu); out[9]=(uint8_t)(ck>>8);
}

static void g30_bms_service_10ms(void){
    if(!g30_bms_probe_state){
        g30_bms_probe_state=(g30_bms_probe_state_t*)pvPortMalloc(sizeof(*g30_bms_probe_state));
        if(!g30_bms_probe_state) return;
        memset(g30_bms_probe_state,0,sizeof(*g30_bms_probe_state));
    }

    if(BP(dma_started)){
        uint16_t left=(uint16_t)huart3.hdmarx->Instance->CNDTR;
        uint8_t wr=(uint8_t)(G30_BMS_RX_N-((left<=G30_BMS_RX_N)?left:G30_BMS_RX_N));
        while(BP(rd)!=wr){
            uint8_t rb=BP(rx_dma)[BP(rd)];
            uint8_t slot=BP(slot);
            BP(raw_last)[BP(raw_last_i)]=rb;
            BP(raw_last_i)=(uint8_t)((BP(raw_last_i)+1u)&7u);
            if(BP(raw_total)!=0xffffu) BP(raw_total)++;
            if(BP(raw_by)[slot]!=0xffffu) BP(raw_by)[slot]++;
            g30_bms_probe_parse_byte(rb);
            BP(rd)++;
            if(BP(rd)>=G30_BMS_RX_N) BP(rd)=0u;
        }
    }

    if(BP(wait_ticks)){
        BP(wait_ticks)--;
        return;
    }

    if(BP(phase)==0u){
        if(g30_bms_probe_start_rx(g30_bms_probe_baud_i(BP(slot)))){
            BP(sends)=0u;
            BP(wait_ticks)=5u; /* 50 ms settle after baud switch */
            BP(phase)=1u;
        }
        return;
    }

    if(BP(phase)==1u){
        uint8_t fr[10];
        uint8_t local=g30_bms_probe_local(BP(slot));
        g30_bms_probe_build_read(g30_bms_probe_regs[local],g30_bms_probe_asks[local],fr);
        if(HAL_UART_Transmit(&huart3,fr,sizeof(fr),5u)==HAL_OK){
            if(BP(tx_by)[BP(slot)]!=0xffffu) BP(tx_by)[BP(slot)]++;
        }
        BP(sends)++;
        BP(wait_ticks)=12u; /* 120 ms response window / stock-like cadence */
        if(BP(sends)>=3u) BP(phase)=2u;
        return;
    }

    /* Final response window elapsed. Move to next matrix entry. */
    BP(slot)++;
    if(BP(slot)>=G30_BMS_PROBE_SLOTS){
        BP(slot)=0u;
        if(BP(round)!=0xffffu) BP(round)++;
    }
    BP(phase)=0u;
}

#undef BP

'''
s=s[:start]+block+s[end:]
p.write_text(s)

# Terminal diagnostics
p=root/"common_files/src/terminal.c"
s=p.read_text()
start=s.index('    }else if (strcmp(argv[0], "g30_bms") == 0){')
end=s.index('    }else if (strcmp(argv[0], "g30_hall") == 0){', start)
rep=r'''    }else if (strcmp(argv[0], "g30_bms") == 0 || strcmp(argv[0], "g30_bms_probe") == 0){
        uint8_t i;
        commands_printf(phandle,
            "BMSPROBE round=%u slot=%u baud=%lu reg=%02X ask=%u rawTotal=%u validTotal=%u crcBad=%u last=%02X/%02X/%02X/%02X len=%u",
            (unsigned)g30_bms_probe_round(),(unsigned)g30_bms_probe_slot(),
            (unsigned long)g30_bms_probe_baud(g30_bms_probe_slot()),
            (unsigned)g30_bms_probe_reg(g30_bms_probe_slot()),
            (unsigned)g30_bms_probe_ask(g30_bms_probe_slot()),
            (unsigned)g30_bms_probe_raw_total(),(unsigned)g30_bms_probe_valid_total(),
            (unsigned)g30_bms_probe_crc_bad(),
            (unsigned)g30_bms_probe_last_src(),(unsigned)g30_bms_probe_last_dst(),
            (unsigned)g30_bms_probe_last_cmd(),(unsigned)g30_bms_probe_last_arg(),
            (unsigned)g30_bms_probe_last_len());
        commands_printf(phandle,
            "BMSPROBE rawLast=%02X%02X%02X%02X%02X%02X%02X%02X observer_source=ADC protection_source=ADC writes=0 Cpin=untouched",
            (unsigned)g30_bms_probe_raw_last_byte(7),(unsigned)g30_bms_probe_raw_last_byte(6),
            (unsigned)g30_bms_probe_raw_last_byte(5),(unsigned)g30_bms_probe_raw_last_byte(4),
            (unsigned)g30_bms_probe_raw_last_byte(3),(unsigned)g30_bms_probe_raw_last_byte(2),
            (unsigned)g30_bms_probe_raw_last_byte(1),(unsigned)g30_bms_probe_raw_last_byte(0));
        for(i=0u;i<10u;i++){
            commands_printf(phandle,
                "BP i=%u baud=%lu reg=%02X ask=%u tx=%u raw=%u valid=%u",
                (unsigned)i,(unsigned long)g30_bms_probe_baud(i),
                (unsigned)g30_bms_probe_reg(i),(unsigned)g30_bms_probe_ask(i),
                (unsigned)g30_bms_probe_tx(i),(unsigned)g30_bms_probe_raw(i),
                (unsigned)g30_bms_probe_valid(i));
        }
        return;
'''
s=s[:start]+rep+s[end:]
p.write_text(s)

print("SESC POWERCORE6500 BMS FULL AUDIT V1 applied: GPIO pad sampler + USART3/DMA register diagnostics")


# BMS PHY V1: sample PB10/PB11 in the 16 kHz HF task without reconfiguring pins.
p=root/"common_files/src/mc_tasks.c"
s=p.read_text()
needle="__weak uint8_t TSK_HighFrequencyTask(void)"
assert needle in s
defs=r'''
/* G30 BMS FULL AUDIT V1: passive MCU-pad activity sampler.
 * Runs at the existing 16 kHz HF cadence. PB10=USART3_TX, PB11=USART3_RX.
 * No GPIO mode changes, no EXTI, no DMA changes here. */
static volatile uint32_t g30_bmsphy_samples_v=0u;
static volatile uint32_t g30_bmsphy_pb10_low_v=0u;
static volatile uint32_t g30_bmsphy_pb11_low_v=0u;
static volatile uint32_t g30_bmsphy_pb10_edges_v=0u;
static volatile uint32_t g30_bmsphy_pb11_edges_v=0u;
static volatile uint8_t g30_bmsphy_prev_v=0xffu;

static inline void g30_bmsphy_hf_sample(void){
  uint32_t idr=GPIOB->IDR;
  uint8_t now=(uint8_t)((idr>>10)&3u);
  uint8_t prev=g30_bmsphy_prev_v;
  g30_bmsphy_samples_v++;
  if((now&1u)==0u) g30_bmsphy_pb10_low_v++;
  if((now&2u)==0u) g30_bmsphy_pb11_low_v++;
  if(prev!=0xffu){
    uint8_t d=(uint8_t)(now^prev);
    if(d&1u) g30_bmsphy_pb10_edges_v++;
    if(d&2u) g30_bmsphy_pb11_edges_v++;
  }
  g30_bmsphy_prev_v=now;
}
uint32_t g30_bmsphy_samples(void){ return g30_bmsphy_samples_v; }
uint32_t g30_bmsphy_pb10_low(void){ return g30_bmsphy_pb10_low_v; }
uint32_t g30_bmsphy_pb11_low(void){ return g30_bmsphy_pb11_low_v; }
uint32_t g30_bmsphy_pb10_edges(void){ return g30_bmsphy_pb10_edges_v; }
uint32_t g30_bmsphy_pb11_edges(void){ return g30_bmsphy_pb11_edges_v; }

'''
s=s.replace(needle,defs+needle,1)
needle2="__weak uint8_t TSK_HighFrequencyTask(void)\n{"
assert needle2 in s
s=s.replace(needle2,needle2+"\n  g30_bmsphy_hf_sample();",1)
p.write_text(s)

# Terminal read-only PHY diagnostics.
p=root/"common_files/src/terminal.c"
s=p.read_text()
marker='    }else if (strcmp(argv[0], "g30_bms") == 0 || strcmp(argv[0], "g30_bms_probe") == 0){'
assert marker in s
phy=r'''    }else if (strcmp(argv[0], "g30_bmsphy") == 0){
        extern UART_HandleTypeDef huart3;
        extern uint32_t g30_bmsphy_samples(void);
        extern uint32_t g30_bmsphy_pb10_low(void);
        extern uint32_t g30_bmsphy_pb11_low(void);
        extern uint32_t g30_bmsphy_pb10_edges(void);
        extern uint32_t g30_bmsphy_pb11_edges(void);
        uint32_t idr=GPIOB->IDR;
        commands_printf(phandle,
          "BMSPHY samples=%lu pb10_low=%lu pb10_edges=%lu pb11_low=%lu pb11_edges=%lu idr10=%u idr11=%u",
          (unsigned long)g30_bmsphy_samples(),
          (unsigned long)g30_bmsphy_pb10_low(),
          (unsigned long)g30_bmsphy_pb10_edges(),
          (unsigned long)g30_bmsphy_pb11_low(),
          (unsigned long)g30_bmsphy_pb11_edges(),
          (unsigned)((idr>>10)&1u),(unsigned)((idr>>11)&1u));
        commands_printf(phandle,
          "BMSPHY GPIOB_CRH=%08lX IDR=%08lX ODR=%08lX AFIO_MAPR=%08lX RCC_APB1ENR=%08lX RCC_APB2ENR=%08lX RCC_AHBENR=%08lX",
          (unsigned long)GPIOB->CRH,(unsigned long)GPIOB->IDR,(unsigned long)GPIOB->ODR,
          (unsigned long)AFIO->MAPR,(unsigned long)RCC->APB1ENR,
          (unsigned long)RCC->APB2ENR,(unsigned long)RCC->AHBENR);
        commands_printf(phandle,
          "BMSPHY USART3_SR=%08lX BRR=%08lX CR1=%08lX CR2=%08lX CR3=%08lX",
          (unsigned long)huart3.Instance->SR,(unsigned long)huart3.Instance->BRR,
          (unsigned long)huart3.Instance->CR1,(unsigned long)huart3.Instance->CR2,
          (unsigned long)huart3.Instance->CR3);
        if(huart3.hdmarx){
          commands_printf(phandle,
            "BMSPHY RXDMA_CCR=%08lX CNDTR=%lu CPAR=%08lX CMAR=%08lX",
            (unsigned long)huart3.hdmarx->Instance->CCR,
            (unsigned long)huart3.hdmarx->Instance->CNDTR,
            (unsigned long)huart3.hdmarx->Instance->CPAR,
            (unsigned long)huart3.hdmarx->Instance->CMAR);
        }
        commands_printf(phandle,"BMSPHY note=passive_gpio_sample_16k no_pin_reconfig no_exti no_bms_write");
        return;
'''
s=s.replace(marker,phy+marker,1)
p.write_text(s)


# Strengthen PHY probe: sample PB10 during the final UART shift and PB11 in a
# 15 ms post-request window. This does not depend on the motor HF task running.
p=root/"common_files/src/task_LED.c"
q=p.read_text()
needle='''    uint16_t crc_bad;
    uint16_t sum;'''
rep='''    uint16_t crc_bad;
    uint16_t sum;
    uint32_t phy_tx_low;
    uint32_t phy_tx_edges;
    uint32_t phy_rx_low;
    uint32_t phy_rx_edges;
    uint8_t phy_tx_prev;
    uint8_t phy_rx_prev;'''
assert needle in q
q=q.replace(needle,rep,1)

needle='''static void g30_bms_service_10ms(void){'''
helper=r'''
uint32_t g30_bmsphy_txwin_low(void){ return g30_bms_probe_state?BP(phy_tx_low):0u; }
uint32_t g30_bmsphy_txwin_edges(void){ return g30_bms_probe_state?BP(phy_tx_edges):0u; }
uint32_t g30_bmsphy_rxwin_low(void){ return g30_bms_probe_state?BP(phy_rx_low):0u; }
uint32_t g30_bmsphy_rxwin_edges(void){ return g30_bms_probe_state?BP(phy_rx_edges):0u; }

static HAL_StatusTypeDef g30_bmsphy_tx_frame(const uint8_t *fr,uint16_t n){
    uint16_t i;
    uint32_t t0;
    if(!fr || !n) return HAL_ERROR;
    for(i=0u;i<n;i++){
        t0=HAL_GetTick();
        while((huart3.Instance->SR & USART_SR_TXE)==0u){
            if((HAL_GetTick()-t0)>5u) return HAL_TIMEOUT;
        }
        huart3.Instance->DR=fr[i];
    }
    /* Writing the last DR clears TC. While the final queued byte(s) leave the
     * peripheral, sample the actual PB10 pad through GPIO IDR. */
    t0=HAL_GetTick();
    BP(phy_tx_prev)=(uint8_t)((GPIOB->IDR>>10)&1u);
    while((huart3.Instance->SR & USART_SR_TC)==0u){
        uint8_t v=(uint8_t)((GPIOB->IDR>>10)&1u);
        if(v==0u) BP(phy_tx_low)++;
        if(v!=BP(phy_tx_prev)) BP(phy_tx_edges)++;
        BP(phy_tx_prev)=v;
        if((HAL_GetTick()-t0)>5u) return HAL_TIMEOUT;
    }
    return HAL_OK;
}

static void g30_bmsphy_sample_rx_window(uint32_t ms){
    uint32_t t0=HAL_GetTick();
    BP(phy_rx_prev)=(uint8_t)((GPIOB->IDR>>11)&1u);
    while((HAL_GetTick()-t0)<ms){
        uint8_t v=(uint8_t)((GPIOB->IDR>>11)&1u);
        if(v==0u) BP(phy_rx_low)++;
        if(v!=BP(phy_rx_prev)) BP(phy_rx_edges)++;
        BP(phy_rx_prev)=v;
    }
}

static void g30_bms_service_10ms(void){'''
assert needle in q
q=q.replace(needle,helper,1)

old='''        if(HAL_UART_Transmit(&huart3,fr,sizeof(fr),5u)==HAL_OK){
            if(BP(tx_by)[BP(slot)]!=0xffffu) BP(tx_by)[BP(slot)]++;
        }'''
new='''        if(g30_bmsphy_tx_frame(fr,sizeof(fr))==HAL_OK){
            if(BP(tx_by)[BP(slot)]!=0xffffu) BP(tx_by)[BP(slot)]++;
        }
        g30_bmsphy_sample_rx_window(15u);'''
assert old in q
q=q.replace(old,new,1)
p.write_text(q)

# Add the independent TX/RX sampling-window counters to terminal diagnostics.
p=root/"common_files/src/terminal.c"
q=p.read_text()
needle='''        extern uint32_t g30_bmsphy_pb11_edges(void);
        uint32_t idr=GPIOB->IDR;'''
rep='''        extern uint32_t g30_bmsphy_pb11_edges(void);
        extern uint32_t g30_bmsphy_txwin_low(void);
        extern uint32_t g30_bmsphy_txwin_edges(void);
        extern uint32_t g30_bmsphy_rxwin_low(void);
        extern uint32_t g30_bmsphy_rxwin_edges(void);
        uint32_t idr=GPIOB->IDR;'''
assert needle in q
q=q.replace(needle,rep,1)
needle='''        commands_printf(phandle,
          "BMSPHY GPIOB_CRH=%08lX IDR=%08lX ODR=%08lX AFIO_MAPR=%08lX RCC_APB1ENR=%08lX RCC_APB2ENR=%08lX RCC_AHBENR=%08lX",'''
rep='''        commands_printf(phandle,
          "BMSPHY TXWIN_low=%lu TXWIN_edges=%lu RXWIN_low=%lu RXWIN_edges=%lu",
          (unsigned long)g30_bmsphy_txwin_low(),(unsigned long)g30_bmsphy_txwin_edges(),
          (unsigned long)g30_bmsphy_rxwin_low(),(unsigned long)g30_bmsphy_rxwin_edges());
        commands_printf(phandle,
          "BMSPHY GPIOB_CRH=%08lX IDR=%08lX ODR=%08lX AFIO_MAPR=%08lX RCC_APB1ENR=%08lX RCC_APB2ENR=%08lX RCC_AHBENR=%08lX",'''
assert needle in q
q=q.replace(needle,rep,1)
p.write_text(q)


# Exact Stock DRV126 USART3 GPIO electrical mode:
#   PB11 = floating input
#   PB10 = AF push-pull, 50 MHz
# Stock DRV126 raw disassembly @0x08006B50:
#   PB11 pin 0x0800 mode 0x04 (GPIO_Mode_IN_FLOATING)
#   PB10 pin 0x0400 speed 3 / mode 0x18 (GPIO_Speed_50MHz + GPIO_Mode_AF_PP)
p=root/"g30p/Src/stm32f1xx_hal_msp.c"
s=p.read_text()
needle='''    GPIO_InitStruct.Pin = UART3_TX_Pin;
    GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(UART3_TX_GPIO_Port, &GPIO_InitStruct);

    GPIO_InitStruct.Pin = UART3_RX_Pin;
    GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(UART3_RX_GPIO_Port, &GPIO_InitStruct);
'''
rep='''    GPIO_InitStruct.Pin = UART3_TX_Pin;
    GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(UART3_TX_GPIO_Port, &GPIO_InitStruct);

    GPIO_InitStruct.Pin = UART3_RX_Pin;
    GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(UART3_RX_GPIO_Port, &GPIO_InitStruct);
'''
assert needle in s
s=s.replace(needle,rep,1)
p.write_text(s)
print("BMS FULL AUDIT V1: PB10 AF-PP 50MHz, PB11 floating input, matching Stock DRV126 electrical mode")


# -------------------------------------------------------------------------
# BMS FULL AUDIT V1
#
# Goal: allow connecting the actual G30 battery (DC+/DC- + BMS connector)
# solely to test BMS UART while the motor power stage is hardware-locked off.
#
# Important:
# - Current-offset polarization is still allowed because CH1/2/3 are explicitly
#   disabled during that MCSDK routine, so no phase gate output can be driven.
# - Any normal SwitchOnPWM attempt with phase channels enabled is rejected.
# - TurnOnLowSides is rejected unconditionally.
# - MOE is cleared on every rejected start.
# - No change to BMS writes/C pin (still read-only / untouched).
# -------------------------------------------------------------------------

p=root/"common_files/src/defines.h"
s=p.read_text()
anchor='#define HW_NAME "SESC-DRV126-POWERCORE6500-BMS-FULL-AUDIT-V1"'
assert anchor in s
s=s.replace(anchor,anchor+'\n#define G30_BMS_BATTERY_SAFE_POWERLOCK 1',1)
p.write_text(s)

p=root/"common_files/MotorControl/MCSDK/MCLib/F1xx/Src/r3_2_f1xx_pwm_curr_fdbk.c"
s=p.read_text()

# Hard block boot-cap low-side turn-on.
needle='''__weak void R3_2_TurnOnLowSides( PWMC_Handle_t * pHdl )
{
  PWMC_R3_2_Handle_t * pHandle = (PWMC_R3_2_Handle_t *) pHdl;
  TIM_TypeDef* TIMx = pHandle->pParams_str->TIMx;
'''
rep='''__weak void R3_2_TurnOnLowSides( PWMC_Handle_t * pHdl )
{
  PWMC_R3_2_Handle_t * pHandle = (PWMC_R3_2_Handle_t *) pHdl;
  TIM_TypeDef* TIMx = pHandle->pParams_str->TIMx;
#ifdef G30_BMS_BATTERY_SAFE_POWERLOCK
  pHdl->PWM_off = true;
  pHandle->_Super.TurnOnLowSidesAction = false;
  LL_TIM_DisableAllOutputs(TIMx);
  if ((pHandle->pParams_str->LowSideOutputs) == ES_GPIO)
  {
    LL_GPIO_ResetOutputPin(pHandle->pParams_str->pwm_en_u_port, pHandle->pParams_str->pwm_en_u_pin);
    LL_GPIO_ResetOutputPin(pHandle->pParams_str->pwm_en_v_port, pHandle->pParams_str->pwm_en_v_pin);
    LL_GPIO_ResetOutputPin(pHandle->pParams_str->pwm_en_w_port, pHandle->pParams_str->pwm_en_w_pin);
  }
  return;
#endif
'''
assert needle in s
s=s.replace(needle,rep,1)

# Allow only the MCSDK offset-polarization calls where CH1/2/3 are disabled.
# Any normal motor-start path has CH1/2/3 enabled and is hard-blocked here.
needle='''__weak void R3_2_SwitchOnPWM( PWMC_Handle_t * pHdl )
{  

  PWMC_R3_2_Handle_t * pHandle = (PWMC_R3_2_Handle_t *) pHdl;
  TIM_TypeDef* TIMx = pHandle->pParams_str->TIMx;
  pHdl->PWM_off = false;
'''
rep='''__weak void R3_2_SwitchOnPWM( PWMC_Handle_t * pHdl )
{  

  PWMC_R3_2_Handle_t * pHandle = (PWMC_R3_2_Handle_t *) pHdl;
  TIM_TypeDef* TIMx = pHandle->pParams_str->TIMx;
#ifdef G30_BMS_BATTERY_SAFE_POWERLOCK
  if (LL_TIM_CC_IsEnabledChannel(TIMx,TIMxCCER_MASK_CH123) != 0u)
  {
    pHdl->PWM_off = true;
    pHandle->_Super.TurnOnLowSidesAction = false;
    LL_TIM_DisableAllOutputs(TIMx);
    if ((pHandle->pParams_str->LowSideOutputs) == ES_GPIO)
    {
      LL_GPIO_ResetOutputPin(pHandle->pParams_str->pwm_en_u_port, pHandle->pParams_str->pwm_en_u_pin);
      LL_GPIO_ResetOutputPin(pHandle->pParams_str->pwm_en_v_port, pHandle->pParams_str->pwm_en_v_pin);
      LL_GPIO_ResetOutputPin(pHandle->pParams_str->pwm_en_w_port, pHandle->pParams_str->pwm_en_w_pin);
    }
    return;
  }
#endif
  pHdl->PWM_off = false;
'''
assert needle in s
s=s.replace(needle,rep,1)
p.write_text(s)

# Diagnostic proof: expose MOE and channel enable state.
p=root/"common_files/src/terminal.c"
s=p.read_text()
needle='''        commands_printf(phandle,"BMSPHY note=passive_gpio_sample_16k no_pin_reconfig no_exti no_bms_write");
        return;
'''
rep='''        commands_printf(phandle,
          "BMSPOWERLOCK enabled=1 bdtr=%08lX ccer=%08lX moe=%u ch123=%u pwm_off=%u",
          (unsigned long)TIM1->BDTR,(unsigned long)TIM1->CCER,
          (unsigned)((TIM1->BDTR & TIM_BDTR_MOE)?1u:0u),
          (unsigned)((TIM1->CCER & 0x0555u)?1u:0u),
          (unsigned)PWM_Handle_M1._Super.PWM_off);
        commands_printf(phandle,"BMSPHY note=passive_gpio_sample_16k no_pin_reconfig no_exti no_bms_write powerstage_locked");
        return;
'''
assert needle in s
s=s.replace(needle,rep,1)
p.write_text(s)

print("BMS FULL AUDIT V1: normal PWM/low-side starts hard-blocked; BMS UART remains read-only")


# -------------------------------------------------------------------------
# BMS FULL AUDIT V1
#
# Replaces the old baud/register probe with a fixed 115200 read-only audit
# over all known G30 BMS registers relevant to identity, capacity, live state,
# balancing, health, cells, config straps and activation data.
# Power stage remains hard-locked by the parent BATTERY SAFE layer.
# -------------------------------------------------------------------------

p=root/"common_files/src/task_LED.h"
s=p.read_text()
start=s.index("/* G30 BMS FULL AUDIT V1:")
end=s.index("\n\n\n\n#endif", start)
rep='''/* G30 BMS FULL AUDIT V1: read-only 115200 audit API. */
uint8_t g30_bms_audit_slot_count(void);
uint8_t g30_bms_audit_reg(uint8_t slot);
uint8_t g30_bms_audit_ask(uint8_t slot);
uint16_t g30_bms_audit_tx(uint8_t slot);
uint16_t g30_bms_audit_ok(uint8_t slot);
uint16_t g30_bms_audit_timeout(uint8_t slot);
uint16_t g30_bms_audit_last_latency(uint8_t slot);
uint16_t g30_bms_audit_min_latency(uint8_t slot);
uint16_t g30_bms_audit_max_latency(uint8_t slot);
uint8_t g30_bms_audit_last_len(uint8_t slot);
uint8_t g30_bms_audit_byte(uint8_t slot,uint8_t idx);
uint32_t g30_bms_audit_raw_total(void);
uint32_t g30_bms_audit_ok_total(void);
uint16_t g30_bms_audit_crc_bad(void);
uint16_t g30_bms_audit_unexpected(void);
uint16_t g30_bms_audit_round(void);
'''
s=s[:start]+rep+s[end:]
p.write_text(s)

p=root/"common_files/src/task_LED.c"
s=p.read_text()
start=s.index("/* -------------------------------------------------------------------------\n * G30 BMS FULL AUDIT V1")
end=s.index("void prv_LED_blink(uint32_t speed){", start)
block=r'''/* -------------------------------------------------------------------------
 * G30 BMS FULL AUDIT V1
 *
 * Fixed 115200 8N1, read-only, source ESC 0x20 -> BMS 0x22.
 * No writes. No C/CHRG_MOD. No motor commands.
 *
 * Known register set (ARG is a 16-bit-word index, request length is bytes):
 *   00 magic, 10 serial, 17 fw, 18 factory capacity, 19 actual capacity,
 *   1B full charge cycles, 1C charge count, 20 manufacture date,
 *   30..36 live status block, 3B health, 40..49 cell voltages,
 *   51 config straps, 70 activation/UID copy.
 * Duplicate individual reads of 31..36 cross-check the live 0x30 block.
 * ------------------------------------------------------------------------- */

#define G30_BMS_AUDIT_RX_N 64u
#define G30_BMS_AUDIT_SLOTS 19u
#define G30_BMS_AUDIT_MAX_DATA 20u

static const uint8_t g30_bms_audit_regs[G30_BMS_AUDIT_SLOTS]={
  0x00u,0x10u,0x17u,0x18u,0x19u,0x1Bu,0x1Cu,0x20u,0x30u,0x3Bu,
  0x40u,0x51u,0x70u,0x31u,0x32u,0x33u,0x34u,0x35u,0x36u
};
static const uint8_t g30_bms_audit_asks[G30_BMS_AUDIT_SLOTS]={
  2u,14u,2u,2u,2u,2u,2u,2u,14u,2u,20u,2u,12u,2u,2u,2u,2u,2u,2u
};

typedef struct {
  uint16_t tx[G30_BMS_AUDIT_SLOTS];
  uint16_t ok[G30_BMS_AUDIT_SLOTS];
  uint16_t timeout[G30_BMS_AUDIT_SLOTS];
  uint16_t lat_last[G30_BMS_AUDIT_SLOTS];
  uint16_t lat_min[G30_BMS_AUDIT_SLOTS];
  uint16_t lat_max[G30_BMS_AUDIT_SLOTS];
  uint8_t data[G30_BMS_AUDIT_SLOTS][G30_BMS_AUDIT_MAX_DATA];
  uint8_t data_len[G30_BMS_AUDIT_SLOTS];
  uint8_t rx_dma[G30_BMS_AUDIT_RX_N];
  uint8_t parse_data[32];
  uint32_t raw_total;
  uint32_t ok_total;
  uint32_t req_ms;
  uint16_t crc_bad;
  uint16_t unexpected;
  uint16_t sum;
  uint16_t round;
  uint8_t rd;
  uint8_t dma_started;
  uint8_t slot;
  uint8_t phase;
  uint8_t wait_ticks;
  uint8_t got_this;
  uint8_t ps;
  uint8_t len;
  uint8_t pi;
  uint8_t src;
  uint8_t dst;
  uint8_t cmd;
  uint8_t arg;
  uint8_t crc_lo;

  uint32_t phy_tx_low;
  uint32_t phy_tx_edges;
  uint32_t phy_rx_low;
  uint32_t phy_rx_edges;
  uint8_t phy_tx_prev;
  uint8_t phy_rx_prev;
} g30_bms_audit_state_t;

static g30_bms_audit_state_t *g30_bms_audit_state;
#define BA(s) (g30_bms_audit_state->s)

uint8_t g30_bms_audit_slot_count(void){ return G30_BMS_AUDIT_SLOTS; }
uint8_t g30_bms_audit_reg(uint8_t slot){ return slot<G30_BMS_AUDIT_SLOTS?g30_bms_audit_regs[slot]:0u; }
uint8_t g30_bms_audit_ask(uint8_t slot){ return slot<G30_BMS_AUDIT_SLOTS?g30_bms_audit_asks[slot]:0u; }
uint16_t g30_bms_audit_tx(uint8_t slot){ return (g30_bms_audit_state&&slot<G30_BMS_AUDIT_SLOTS)?BA(tx)[slot]:0u; }
uint16_t g30_bms_audit_ok(uint8_t slot){ return (g30_bms_audit_state&&slot<G30_BMS_AUDIT_SLOTS)?BA(ok)[slot]:0u; }
uint16_t g30_bms_audit_timeout(uint8_t slot){ return (g30_bms_audit_state&&slot<G30_BMS_AUDIT_SLOTS)?BA(timeout)[slot]:0u; }
uint16_t g30_bms_audit_last_latency(uint8_t slot){ return (g30_bms_audit_state&&slot<G30_BMS_AUDIT_SLOTS)?BA(lat_last)[slot]:0u; }
uint16_t g30_bms_audit_min_latency(uint8_t slot){ return (g30_bms_audit_state&&slot<G30_BMS_AUDIT_SLOTS)?BA(lat_min)[slot]:0u; }
uint16_t g30_bms_audit_max_latency(uint8_t slot){ return (g30_bms_audit_state&&slot<G30_BMS_AUDIT_SLOTS)?BA(lat_max)[slot]:0u; }
uint8_t g30_bms_audit_last_len(uint8_t slot){ return (g30_bms_audit_state&&slot<G30_BMS_AUDIT_SLOTS)?BA(data_len)[slot]:0u; }
uint8_t g30_bms_audit_byte(uint8_t slot,uint8_t idx){
  if(!g30_bms_audit_state||slot>=G30_BMS_AUDIT_SLOTS||idx>=G30_BMS_AUDIT_MAX_DATA) return 0u;
  return BA(data)[slot][idx];
}
uint32_t g30_bms_audit_raw_total(void){ return g30_bms_audit_state?BA(raw_total):0u; }
uint32_t g30_bms_audit_ok_total(void){ return g30_bms_audit_state?BA(ok_total):0u; }
uint16_t g30_bms_audit_crc_bad(void){ return g30_bms_audit_state?BA(crc_bad):0u; }
uint16_t g30_bms_audit_unexpected(void){ return g30_bms_audit_state?BA(unexpected):0u; }
uint16_t g30_bms_audit_round(void){ return g30_bms_audit_state?BA(round):0u; }

/* Compatibility with PHY terminal code retained from V1/V2. */
uint32_t g30_bmsphy_txwin_low(void){ return g30_bms_audit_state?BA(phy_tx_low):0u; }
uint32_t g30_bmsphy_txwin_edges(void){ return g30_bms_audit_state?BA(phy_tx_edges):0u; }
uint32_t g30_bmsphy_rxwin_low(void){ return g30_bms_audit_state?BA(phy_rx_low):0u; }
uint32_t g30_bmsphy_rxwin_edges(void){ return g30_bms_audit_state?BA(phy_rx_edges):0u; }

static uint16_t g30_bms_audit_u16(uint8_t slot,uint8_t off){
  return (uint16_t)g30_bms_audit_byte(slot,off) |
         ((uint16_t)g30_bms_audit_byte(slot,(uint8_t)(off+1u))<<8);
}

static int8_t g30_bms_find_slot(uint8_t arg){
  uint8_t i;
  for(i=0u;i<G30_BMS_AUDIT_SLOTS;i++) if(g30_bms_audit_regs[i]==arg) return (int8_t)i;
  return -1;
}

static void g30_bms_audit_parse_byte(uint8_t b){
  switch(BA(ps)){
  default:
  case 0: if(b==0x5Au) BA(ps)=1u; break;
  case 1: if(b==0xA5u) BA(ps)=2u; else BA(ps)=(b==0x5Au)?1u:0u; break;
  case 2:
    BA(len)=b;
    if(BA(len)>32u){ BA(ps)=0u; break; }
    BA(sum)=b; BA(pi)=0u; BA(ps)=3u; break;
  case 3: BA(src)=b; BA(sum)=(uint16_t)(BA(sum)+b); BA(ps)=4u; break;
  case 4: BA(dst)=b; BA(sum)=(uint16_t)(BA(sum)+b); BA(ps)=5u; break;
  case 5: BA(cmd)=b; BA(sum)=(uint16_t)(BA(sum)+b); BA(ps)=6u; break;
  case 6: BA(arg)=b; BA(sum)=(uint16_t)(BA(sum)+b); BA(ps)=BA(len)?7u:8u; break;
  case 7:
    if(BA(pi)<sizeof(BA(parse_data))) BA(parse_data)[BA(pi)]=b;
    BA(sum)=(uint16_t)(BA(sum)+b);
    BA(pi)++;
    if(BA(pi)>=BA(len)) BA(ps)=8u;
    break;
  case 8: BA(crc_lo)=b; BA(ps)=9u; break;
  case 9: {
    uint16_t expected=(uint16_t)(~BA(sum));
    uint16_t got=(uint16_t)BA(crc_lo)|((uint16_t)b<<8);
    if(got==expected){
      if(BA(src)==0x22u && BA(dst)==0x20u && BA(cmd)==0x04u){
        int8_t fs=g30_bms_find_slot(BA(arg));
        if(fs>=0){
          uint8_t sl=(uint8_t)fs;
          uint8_t n=BA(len)>G30_BMS_AUDIT_MAX_DATA?G30_BMS_AUDIT_MAX_DATA:BA(len);
          uint8_t i;
          for(i=0u;i<n;i++) BA(data)[sl][i]=BA(parse_data)[i];
          BA(data_len)[sl]=BA(len);
          if(BA(ok)[sl]!=0xFFFFu) BA(ok)[sl]++;
          BA(ok_total)++;
          if(sl==BA(slot)){
            uint32_t d=HAL_GetTick()-BA(req_ms);
            uint16_t lat=(uint16_t)(d>65535u?65535u:d);
            BA(lat_last)[sl]=lat;
            if(BA(lat_min)[sl]==0u || lat<BA(lat_min)[sl]) BA(lat_min)[sl]=lat;
            if(lat>BA(lat_max)[sl]) BA(lat_max)[sl]=lat;
            BA(got_this)=1u;
          }
        } else {
          if(BA(unexpected)!=0xFFFFu) BA(unexpected)++;
        }
      } else {
        if(BA(unexpected)!=0xFFFFu) BA(unexpected)++;
      }
    } else {
      if(BA(crc_bad)!=0xFFFFu) BA(crc_bad)++;
    }
    BA(ps)=0u;
    break;
  }}
}

static uint8_t g30_bms_audit_start_rx(void){
  if(BA(dma_started)){
    (void)HAL_UART_DMAStop(&huart3);
    BA(dma_started)=0u;
  }
  huart3.Init.BaudRate=115200u;
  if(HAL_UART_Init(&huart3)!=HAL_OK) return 0u;
  memset(BA(rx_dma),0,sizeof(BA(rx_dma)));
  BA(rd)=0u; BA(ps)=0u;
  if(HAL_UART_Receive_DMA(&huart3,BA(rx_dma),G30_BMS_AUDIT_RX_N)!=HAL_OK) return 0u;
  __HAL_DMA_DISABLE_IT(huart3.hdmarx,DMA_IT_HT|DMA_IT_TC|DMA_IT_TE);
  CLEAR_BIT(huart3.Instance->CR1,USART_CR1_PEIE);
  CLEAR_BIT(huart3.Instance->CR3,USART_CR3_EIE);
  BA(dma_started)=1u;
  return 1u;
}

static void g30_bms_audit_build_read(uint8_t reg,uint8_t ask,uint8_t out[10]){
  uint16_t sum,ck;
  out[0]=0x5Au; out[1]=0xA5u; out[2]=0x01u; out[3]=0x20u; out[4]=0x22u;
  out[5]=0x01u; out[6]=reg; out[7]=ask;
  sum=(uint16_t)(out[2]+out[3]+out[4]+out[5]+out[6]+out[7]);
  ck=(uint16_t)(~sum);
  out[8]=(uint8_t)(ck&0xFFu); out[9]=(uint8_t)(ck>>8);
}

static HAL_StatusTypeDef g30_bms_audit_tx_frame(const uint8_t *fr,uint16_t n){
  uint16_t i; uint32_t t0;
  if(!fr||!n) return HAL_ERROR;
  for(i=0u;i<n;i++){
    t0=HAL_GetTick();
    while((huart3.Instance->SR & USART_SR_TXE)==0u){
      if((HAL_GetTick()-t0)>5u) return HAL_TIMEOUT;
    }
    huart3.Instance->DR=fr[i];
  }
  t0=HAL_GetTick();
  BA(phy_tx_prev)=(uint8_t)((GPIOB->IDR>>10)&1u);
  while((huart3.Instance->SR & USART_SR_TC)==0u){
    uint8_t v=(uint8_t)((GPIOB->IDR>>10)&1u);
    if(v==0u) BA(phy_tx_low)++;
    if(v!=BA(phy_tx_prev)) BA(phy_tx_edges)++;
    BA(phy_tx_prev)=v;
    if((HAL_GetTick()-t0)>5u) return HAL_TIMEOUT;
  }
  return HAL_OK;
}

static void g30_bms_audit_rx_window(uint32_t ms){
  uint32_t t0=HAL_GetTick();
  BA(phy_rx_prev)=(uint8_t)((GPIOB->IDR>>11)&1u);
  while((HAL_GetTick()-t0)<ms){
    uint8_t v=(uint8_t)((GPIOB->IDR>>11)&1u);
    if(v==0u) BA(phy_rx_low)++;
    if(v!=BA(phy_rx_prev)) BA(phy_rx_edges)++;
    BA(phy_rx_prev)=v;
  }
}

static void g30_bms_service_10ms(void){
  if(!g30_bms_audit_state){
    g30_bms_audit_state=(g30_bms_audit_state_t*)pvPortMalloc(sizeof(*g30_bms_audit_state));
    if(!g30_bms_audit_state) return;
    memset(g30_bms_audit_state,0,sizeof(*g30_bms_audit_state));
  }

  if(!BA(dma_started)){
    if(g30_bms_audit_start_rx()){
      BA(wait_ticks)=5u;
      BA(phase)=1u;
    }
    return;
  }

  {
    uint16_t left=(uint16_t)huart3.hdmarx->Instance->CNDTR;
    uint8_t wr=(uint8_t)(G30_BMS_AUDIT_RX_N-((left<=G30_BMS_AUDIT_RX_N)?left:G30_BMS_AUDIT_RX_N));
    while(BA(rd)!=wr){
      uint8_t rb=BA(rx_dma)[BA(rd)];
      BA(raw_total)++;
      g30_bms_audit_parse_byte(rb);
      BA(rd)++;
      if(BA(rd)>=G30_BMS_AUDIT_RX_N) BA(rd)=0u;
    }
  }

  if(BA(wait_ticks)){
    BA(wait_ticks)--;
    return;
  }

  if(BA(phase)==1u){
    uint8_t fr[10];
    uint8_t sl=BA(slot);
    g30_bms_audit_build_read(g30_bms_audit_regs[sl],g30_bms_audit_asks[sl],fr);
    BA(got_this)=0u;
    BA(req_ms)=HAL_GetTick();
    if(g30_bms_audit_tx_frame(fr,sizeof(fr))==HAL_OK){
      if(BA(tx)[sl]!=0xFFFFu) BA(tx)[sl]++;
    }
    g30_bms_audit_rx_window(12u);
    BA(wait_ticks)=8u; /* total response budget about 90 ms */
    BA(phase)=2u;
    return;
  }

  if(BA(phase)==2u){
    uint8_t sl=BA(slot);
    if(!BA(got_this) && BA(timeout)[sl]!=0xFFFFu) BA(timeout)[sl]++;
    BA(slot)++;
    if(BA(slot)>=G30_BMS_AUDIT_SLOTS){
      BA(slot)=0u;
      if(BA(round)!=0xFFFFu) BA(round)++;
    }
    BA(phase)=1u;
  }
}

#undef BA

'''
s=s[:start]+block+s[end:]
p.write_text(s)

# Replace old probe terminal command with decoded audit output + detailed slots.
p=root/"common_files/src/terminal.c"
s=p.read_text()
start=s.index('    }else if (strcmp(argv[0], "g30_bms") == 0 || strcmp(argv[0], "g30_bms_probe") == 0){')
end=s.index('    }else if (strcmp(argv[0], "g30_hall") == 0){', start)
rep=r'''    }else if (strcmp(argv[0], "g30_bms") == 0 || strcmp(argv[0], "g30_bms_audit") == 0){
        uint8_t i;
        uint16_t magic=(uint16_t)g30_bms_audit_byte(0,0)|((uint16_t)g30_bms_audit_byte(0,1)<<8);
        uint16_t fw=(uint16_t)g30_bms_audit_byte(2,0)|((uint16_t)g30_bms_audit_byte(2,1)<<8);
        uint16_t factory=(uint16_t)g30_bms_audit_byte(3,0)|((uint16_t)g30_bms_audit_byte(3,1)<<8);
        uint16_t actual=(uint16_t)g30_bms_audit_byte(4,0)|((uint16_t)g30_bms_audit_byte(4,1)<<8);
        uint16_t cycles=(uint16_t)g30_bms_audit_byte(5,0)|((uint16_t)g30_bms_audit_byte(5,1)<<8);
        uint16_t charges=(uint16_t)g30_bms_audit_byte(6,0)|((uint16_t)g30_bms_audit_byte(6,1)<<8);
        uint16_t mfg=(uint16_t)g30_bms_audit_byte(7,0)|((uint16_t)g30_bms_audit_byte(7,1)<<8);
        uint16_t status=(uint16_t)g30_bms_audit_byte(8,0)|((uint16_t)g30_bms_audit_byte(8,1)<<8);
        uint16_t rem=(uint16_t)g30_bms_audit_byte(8,2)|((uint16_t)g30_bms_audit_byte(8,3)<<8);
        uint16_t soc=(uint16_t)g30_bms_audit_byte(8,4)|((uint16_t)g30_bms_audit_byte(8,5)<<8);
        int16_t current=(int16_t)((uint16_t)g30_bms_audit_byte(8,6)|((uint16_t)g30_bms_audit_byte(8,7)<<8));
        uint16_t pack10=(uint16_t)g30_bms_audit_byte(8,8)|((uint16_t)g30_bms_audit_byte(8,9)<<8);
        uint8_t t1=g30_bms_audit_byte(8,10),t2=g30_bms_audit_byte(8,11);
        uint16_t balance=(uint16_t)g30_bms_audit_byte(8,12)|((uint16_t)g30_bms_audit_byte(8,13)<<8);
        uint16_t health=(uint16_t)g30_bms_audit_byte(9,0)|((uint16_t)g30_bms_audit_byte(9,1)<<8);
        uint16_t straps=(uint16_t)g30_bms_audit_byte(11,0)|((uint16_t)g30_bms_audit_byte(11,1)<<8);
        uint32_t txsum=0u,oksum=0u,tosum=0u;
        uint16_t c[10],cmin=65535u,cmax=0u; uint32_t csum=0u;
        char serial[15];
        for(i=0u;i<14u;i++){ uint8_t b=g30_bms_audit_byte(1,i); serial[i]=(b>=32u&&b<=126u)?(char)b:'.'; }
        serial[14]='\0';
        for(i=0u;i<10u;i++){
          c[i]=(uint16_t)g30_bms_audit_byte(10,(uint8_t)(2u*i))|((uint16_t)g30_bms_audit_byte(10,(uint8_t)(2u*i+1u))<<8);
          if(c[i]<cmin)cmin=c[i]; if(c[i]>cmax)cmax=c[i]; csum+=c[i];
        }
        for(i=0u;i<g30_bms_audit_slot_count();i++){ txsum+=g30_bms_audit_tx(i); oksum+=g30_bms_audit_ok(i); tosum+=g30_bms_audit_timeout(i); }
        commands_printf(phandle,"BMSAUDIT round=%u baud=115200 tx=%lu ok=%lu timeout=%lu raw=%lu crcBad=%u unexpected=%u",
          (unsigned)g30_bms_audit_round(),(unsigned long)txsum,(unsigned long)oksum,(unsigned long)tosum,
          (unsigned long)g30_bms_audit_raw_total(),(unsigned)g30_bms_audit_crc_bad(),(unsigned)g30_bms_audit_unexpected());
        commands_printf(phandle,"BMSID magic=%04X serial=%s fw=%04X factory=%u actual=%u cycles=%u charges=%u mfg=%04X",
          (unsigned)magic,serial,(unsigned)fw,(unsigned)factory,(unsigned)actual,(unsigned)cycles,(unsigned)charges,(unsigned)mfg);
        commands_printf(phandle,"BMSLIVE status=%04X rem=%u soc=%u current10mA=%d pack10mV=%u tempCode=%u,%u tempC=%d,%d balance=%04X health=%u straps=%04X",
          (unsigned)status,(unsigned)rem,(unsigned)soc,(int)current,(unsigned)pack10,(unsigned)t1,(unsigned)t2,
          (int)t1-20,(int)t2-20,(unsigned)balance,(unsigned)health,(unsigned)straps);
        commands_printf(phandle,"BMSCELLS %u,%u,%u,%u,%u,%u,%u,%u,%u,%u min=%u max=%u delta=%u sum=%lu",
          (unsigned)c[0],(unsigned)c[1],(unsigned)c[2],(unsigned)c[3],(unsigned)c[4],
          (unsigned)c[5],(unsigned)c[6],(unsigned)c[7],(unsigned)c[8],(unsigned)c[9],
          (unsigned)cmin,(unsigned)cmax,(unsigned)(cmax-cmin),(unsigned long)csum);
        commands_printf(phandle,
          "BMSCROSS rem=%u/%u soc=%u/%u current=%d/%d pack=%u/%u tempRaw=%02X%02X/%02X%02X balance=%04X/%04X",
          (unsigned)rem,(unsigned)((uint16_t)g30_bms_audit_byte(13,0)|((uint16_t)g30_bms_audit_byte(13,1)<<8)),
          (unsigned)soc,(unsigned)((uint16_t)g30_bms_audit_byte(14,0)|((uint16_t)g30_bms_audit_byte(14,1)<<8)),
          (int)current,(int)(int16_t)((uint16_t)g30_bms_audit_byte(15,0)|((uint16_t)g30_bms_audit_byte(15,1)<<8)),
          (unsigned)pack10,(unsigned)((uint16_t)g30_bms_audit_byte(16,0)|((uint16_t)g30_bms_audit_byte(16,1)<<8)),
          (unsigned)g30_bms_audit_byte(8,11),(unsigned)g30_bms_audit_byte(8,10),
          (unsigned)g30_bms_audit_byte(17,1),(unsigned)g30_bms_audit_byte(17,0),
          (unsigned)balance,(unsigned)((uint16_t)g30_bms_audit_byte(18,0)|((uint16_t)g30_bms_audit_byte(18,1)<<8)));
        commands_printf(phandle,
          "BMSACT %02X%02X%02X%02X%02X%02X%02X%02X%02X%02X%02X%02X",
          (unsigned)g30_bms_audit_byte(12,0),(unsigned)g30_bms_audit_byte(12,1),
          (unsigned)g30_bms_audit_byte(12,2),(unsigned)g30_bms_audit_byte(12,3),
          (unsigned)g30_bms_audit_byte(12,4),(unsigned)g30_bms_audit_byte(12,5),
          (unsigned)g30_bms_audit_byte(12,6),(unsigned)g30_bms_audit_byte(12,7),
          (unsigned)g30_bms_audit_byte(12,8),(unsigned)g30_bms_audit_byte(12,9),
          (unsigned)g30_bms_audit_byte(12,10),(unsigned)g30_bms_audit_byte(12,11));
        return;
    }else if (strcmp(argv[0], "g30_bms_slots") == 0){
        uint8_t i,j;
        for(i=0u;i<g30_bms_audit_slot_count();i++){
          char hex[41]; uint8_t n=g30_bms_audit_last_len(i); if(n>20u)n=20u;
          for(j=0u;j<n;j++){ static const char h[]="0123456789ABCDEF"; uint8_t b=g30_bms_audit_byte(i,j); hex[2u*j]=h[b>>4]; hex[2u*j+1u]=h[b&15u]; }
          hex[2u*n]='\0';
          commands_printf(phandle,"BASLOT i=%u reg=%02X ask=%u tx=%u ok=%u timeout=%u len=%u lat=%u/%u/%u data=%s",
            (unsigned)i,(unsigned)g30_bms_audit_reg(i),(unsigned)g30_bms_audit_ask(i),
            (unsigned)g30_bms_audit_tx(i),(unsigned)g30_bms_audit_ok(i),(unsigned)g30_bms_audit_timeout(i),
            (unsigned)g30_bms_audit_last_len(i),(unsigned)g30_bms_audit_last_latency(i),
            (unsigned)g30_bms_audit_min_latency(i),(unsigned)g30_bms_audit_max_latency(i),hex);
        }
        return;
'''
s=s[:start]+rep+s[end:]
p.write_text(s)

# Update PHY note and retain powerlock.
p=root/"common_files/src/terminal.c"
s=p.read_text().replace("BMSPHY note=passive_gpio_sample_16k no_pin_reconfig no_exti no_bms_write powerstage_locked",
                        "BMSPHY note=115200_full_audit no_bms_write Cpin_untouched powerstage_locked")
p.write_text(s)

print("BMS FULL AUDIT V1 applied: 19-slot read-only semantic audit + cross-checks + latency")
