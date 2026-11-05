#!/usr/bin/env python3
from pathlib import Path

root=Path("SOURCE_KOXX3")

# Build ID
p=root/"common_files/src/defines.h"
s=p.read_text()
old='#define HW_NAME "SESC-DRV126-POWERCORE6500-BMSTEL-V2"'
new='#define HW_NAME "SESC-DRV126-POWERCORE6500-BMSPHY-V1"'
assert old in s
p.write_text(s.replace(old,new,1))

# Header API
p=root/"common_files/src/task_LED.h"
s=p.read_text()
start=s.index("/* G30 BMSTEL V2:")
end=s.index("\n\n\n\n#endif", start)
rep='''/* G30 BMSPROBE V1: read-only USART3 auto-probe. */
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
 * G30 BMSPROBE V1
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

print("SESC POWERCORE6500 BMSPHY V1 applied: GPIO pad sampler + USART3/DMA register diagnostics")


# BMS PHY V1: sample PB10/PB11 in the 16 kHz HF task without reconfiguring pins.
p=root/"common_files/src/mc_tasks.c"
s=p.read_text()
needle="__weak uint8_t TSK_HighFrequencyTask(void)"
assert needle in s
defs=r'''
/* G30 BMSPHY V1: passive MCU-pad activity sampler.
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
