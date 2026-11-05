#!/usr/bin/env python3
from pathlib import Path

root=Path("SOURCE_KOXX3")

# Identity: child of the battery-safe/powerlock build.
p=root/"common_files/src/defines.h"
s=p.read_text()
old='#define HW_NAME "SESC-DRV126-POWERCORE6500-BMS-BATTERY-SAFE-V1"'
new='#define HW_NAME "SESC-DRV126-POWERCORE6500-BMS-FINALREAD-V1"'
assert old in s
p.write_text(s.replace(old,new,1))

# Public read-only telemetry API.
p=root/"common_files/src/task_LED.h"
s=p.read_text()
start=s.index("/* G30 BMS BATTERY SAFE V1:")
end=s.index("\n\n\n\n#endif",start)
rep=r'''/* G30 BMS FINALREAD V1: production read-only stock BMS polling. */
uint8_t g30_bms_final_fresh(void);
uint32_t g30_bms_final_status_age_ms(void);
uint32_t g30_bms_final_cells_age_ms(void);
uint16_t g30_bms_final_tx(void);
uint16_t g30_bms_final_valid(void);
uint16_t g30_bms_final_crc_bad(void);
uint16_t g30_bms_final_timeouts(void);
uint16_t g30_bms_final_unexpected(void);
uint16_t g30_bms_final_status(void);
uint16_t g30_bms_final_remaining_mah(void);
uint16_t g30_bms_final_soc(void);
int32_t g30_bms_final_current_ma(void);
uint32_t g30_bms_final_pack_mv(void);
int16_t g30_bms_final_temp1_c(void);
int16_t g30_bms_final_temp2_c(void);
uint16_t g30_bms_final_balance(void);
uint16_t g30_bms_final_soh(void);
uint16_t g30_bms_final_cell_mv(uint8_t i);
uint16_t g30_bms_final_cell_min_mv(void);
uint16_t g30_bms_final_cell_max_mv(void);
uint16_t g30_bms_final_cell_delta_mv(void);
uint16_t g30_bms_final_fw(void);
uint16_t g30_bms_final_factory_mah(void);
uint16_t g30_bms_final_actual_mah(void);
uint16_t g30_bms_final_cycles(void);
uint16_t g30_bms_final_charge_count(void);
uint16_t g30_bms_final_mfg_date_raw(void);
uint16_t g30_bms_final_config(void);
const char *g30_bms_final_serial(void);
'''
s=s[:start]+rep+s[end:]
p.write_text(s)

# Replace probe matrix with a 115200-only, read-only production driver.
p=root/"common_files/src/task_LED.c"
s=p.read_text()
start=s.index("/* -------------------------------------------------------------------------\n * G30 BMS BATTERY SAFE V1")
end=s.index("void prv_LED_blink(uint32_t speed){",start)
block=r'''/* -------------------------------------------------------------------------
 * G30 BMS FINALREAD V1
 *
 * Production read-only stock G30 BMS driver.
 * - USART3 PB10/PB11, 115200 8N1 only (real hardware confirmed).
 * - Exact Stock126 status request: READ 0x30, 12 bytes, nominal 110 ms cadence.
 * - Cells: READ 0x40, 20 bytes, 550 ms cadence.
 * - Slow metadata/auxiliary reads are interleaved without delaying READ30.
 * - No BMS WRITE, no C/CHRG_MOD manipulation.
 * - BMS values are telemetry only: observer/protection keep using ESC ADC.
 * - Power-stage lock is implemented separately in the MCSDK low-level driver
 *   and remains mandatory for the complete BMS workstream.
 * ------------------------------------------------------------------------- */

#define G30_BMS_RX_N 64u
#define G30_BMS_PAYLOAD_N 24u
#define G30_BMS_STATUS_PERIOD_MS 110u
#define G30_BMS_CELLS_PERIOD_MS 550u
#define G30_BMS_SLOW_PERIOD_MS 1000u
#define G30_BMS_RESPONSE_TIMEOUT_MS 45u

typedef struct {
    uint8_t rx_dma[G30_BMS_RX_N];
    uint8_t payload[G30_BMS_PAYLOAD_N];
    uint8_t rd;
    uint8_t dma_started;
    uint8_t ps,len,pi,src,dst,cmd,arg,crc_lo;
    uint16_t sum;
    uint8_t outstanding;
    uint8_t expected_arg;
    uint8_t expected_len;
    uint8_t slow_index;
    uint32_t req_ms;
    uint32_t status_due_ms;
    uint32_t cells_due_ms;
    uint32_t slow_due_ms;
    uint32_t last_any_ms;
    uint32_t last_status_ms;
    uint32_t last_cells_ms;
    uint16_t tx,valid,crc_bad,timeouts,unexpected;

    char serial[15];
    uint16_t fw;
    uint16_t factory_mah;
    uint16_t actual_mah;
    uint16_t cycles;
    uint16_t charge_count;
    uint16_t mfg_date_raw;
    uint16_t config;
    uint8_t uid[12];

    uint16_t status;
    uint16_t remaining_mah;
    uint16_t soc;
    int16_t current_raw;
    uint16_t pack_raw;
    uint16_t temp_raw;
    uint16_t balance;
    uint16_t soh;
    uint16_t cell_mv[10];
    uint16_t cell_min_mv;
    uint16_t cell_max_mv;
    uint16_t cell_delta_mv;

    /* Retain cheap TX pad evidence for diagnostics; no busy RX window. */
    uint32_t phy_tx_low;
    uint32_t phy_tx_edges;
    uint8_t phy_tx_prev;
} g30_bms_final_state_t;

static g30_bms_final_state_t *g30_bms_final_state;
#define BF(s) (g30_bms_final_state->s)

static uint16_t g30_bms_u16(const uint8_t *p){
    return (uint16_t)p[0] | ((uint16_t)p[1]<<8);
}

uint8_t g30_bms_final_fresh(void){
    return (g30_bms_final_state && BF(last_status_ms) &&
            (HAL_GetTick()-BF(last_status_ms))<500u) ? 1u : 0u;
}
uint32_t g30_bms_final_status_age_ms(void){
    return (!g30_bms_final_state || !BF(last_status_ms)) ? 0xffffffffu : HAL_GetTick()-BF(last_status_ms);
}
uint32_t g30_bms_final_cells_age_ms(void){
    return (!g30_bms_final_state || !BF(last_cells_ms)) ? 0xffffffffu : HAL_GetTick()-BF(last_cells_ms);
}
uint16_t g30_bms_final_tx(void){return g30_bms_final_state?BF(tx):0u;}
uint16_t g30_bms_final_valid(void){return g30_bms_final_state?BF(valid):0u;}
uint16_t g30_bms_final_crc_bad(void){return g30_bms_final_state?BF(crc_bad):0u;}
uint16_t g30_bms_final_timeouts(void){return g30_bms_final_state?BF(timeouts):0u;}
uint16_t g30_bms_final_unexpected(void){return g30_bms_final_state?BF(unexpected):0u;}
uint16_t g30_bms_final_status(void){return g30_bms_final_state?BF(status):0u;}
uint16_t g30_bms_final_remaining_mah(void){return g30_bms_final_state?BF(remaining_mah):0u;}
uint16_t g30_bms_final_soc(void){return g30_bms_final_state?BF(soc):0u;}
int32_t g30_bms_final_current_ma(void){return g30_bms_final_state?(int32_t)BF(current_raw)*10:0;}
uint32_t g30_bms_final_pack_mv(void){return g30_bms_final_state?(uint32_t)BF(pack_raw)*10u:0u;}
int16_t g30_bms_final_temp1_c(void){return g30_bms_final_state?(int16_t)((BF(temp_raw)&0xffu)-20):0;}
int16_t g30_bms_final_temp2_c(void){return g30_bms_final_state?(int16_t)(((BF(temp_raw)>>8)&0xffu)-20):0;}
uint16_t g30_bms_final_balance(void){return g30_bms_final_state?BF(balance):0u;}
uint16_t g30_bms_final_soh(void){return g30_bms_final_state?BF(soh):0u;}
uint16_t g30_bms_final_cell_mv(uint8_t i){return (g30_bms_final_state && i<10u)?BF(cell_mv)[i]:0u;}
uint16_t g30_bms_final_cell_min_mv(void){return g30_bms_final_state?BF(cell_min_mv):0u;}
uint16_t g30_bms_final_cell_max_mv(void){return g30_bms_final_state?BF(cell_max_mv):0u;}
uint16_t g30_bms_final_cell_delta_mv(void){return g30_bms_final_state?BF(cell_delta_mv):0u;}
uint16_t g30_bms_final_fw(void){return g30_bms_final_state?BF(fw):0u;}
uint16_t g30_bms_final_factory_mah(void){return g30_bms_final_state?BF(factory_mah):0u;}
uint16_t g30_bms_final_actual_mah(void){return g30_bms_final_state?BF(actual_mah):0u;}
uint16_t g30_bms_final_cycles(void){return g30_bms_final_state?BF(cycles):0u;}
uint16_t g30_bms_final_charge_count(void){return g30_bms_final_state?BF(charge_count):0u;}
uint16_t g30_bms_final_mfg_date_raw(void){return g30_bms_final_state?BF(mfg_date_raw):0u;}
uint16_t g30_bms_final_config(void){return g30_bms_final_state?BF(config):0u;}
const char *g30_bms_final_serial(void){return g30_bms_final_state?BF(serial):"";}

/* Compatibility for the retained g30_bmsphy diagnostic command. */
uint32_t g30_bmsphy_txwin_low(void){return g30_bms_final_state?BF(phy_tx_low):0u;}
uint32_t g30_bmsphy_txwin_edges(void){return g30_bms_final_state?BF(phy_tx_edges):0u;}
uint32_t g30_bmsphy_rxwin_low(void){return 0u;}
uint32_t g30_bmsphy_rxwin_edges(void){return 0u;}

static void g30_bms_final_decode(uint8_t arg,const uint8_t *p,uint8_t n){
    uint8_t i;
    uint32_t now=HAL_GetTick();
    BF(last_any_ms)=now;

    if(arg==0x10u && n>=14u){
        for(i=0u;i<14u;i++){
            uint8_t c=p[i];
            BF(serial)[i]=(c>=32u && c<=126u)?(char)c:'?';
        }
        BF(serial)[14]='\0';
    }else if(arg==0x17u && n>=2u){
        BF(fw)=g30_bms_u16(p);
    }else if(arg==0x18u && n>=4u){
        BF(factory_mah)=g30_bms_u16(p);
        BF(actual_mah)=g30_bms_u16(p+2);
    }else if(arg==0x1bu && n>=4u){
        BF(cycles)=g30_bms_u16(p);
        BF(charge_count)=g30_bms_u16(p+2);
    }else if(arg==0x20u && n>=2u){
        BF(mfg_date_raw)=g30_bms_u16(p);
    }else if(arg==0x30u && n>=12u){
        BF(status)=g30_bms_u16(p+0);
        BF(remaining_mah)=g30_bms_u16(p+2);
        BF(soc)=g30_bms_u16(p+4);
        BF(current_raw)=(int16_t)g30_bms_u16(p+6);
        BF(pack_raw)=g30_bms_u16(p+8);
        BF(temp_raw)=g30_bms_u16(p+10);
        BF(last_status_ms)=now;
    }else if(arg==0x36u && n>=2u){
        BF(balance)=g30_bms_u16(p);
    }else if(arg==0x3bu && n>=2u){
        BF(soh)=g30_bms_u16(p);
    }else if(arg==0x40u && n>=20u){
        uint16_t mn=0xffffu,mx=0u;
        for(i=0u;i<10u;i++){
            uint16_t v=g30_bms_u16(p+(uint8_t)(i*2u));
            BF(cell_mv)[i]=v;
            if(v<mn) mn=v;
            if(v>mx) mx=v;
        }
        BF(cell_min_mv)=mn;
        BF(cell_max_mv)=mx;
        BF(cell_delta_mv)=(mx>=mn)?(uint16_t)(mx-mn):0u;
        BF(last_cells_ms)=now;
    }else if(arg==0x51u && n>=2u){
        BF(config)=g30_bms_u16(p);
    }else if(arg==0x70u && n>=12u){
        memcpy(BF(uid),p,12u);
    }
}

static void g30_bms_final_parse_byte(uint8_t b){
    switch(BF(ps)){
    default:
    case 0:
        if(b==0x5au) BF(ps)=1u;
        break;
    case 1:
        if(b==0xa5u) BF(ps)=2u;
        else BF(ps)=(b==0x5au)?1u:0u;
        break;
    case 2:
        BF(len)=b;
        if(BF(len)>G30_BMS_PAYLOAD_N){BF(ps)=0u;break;}
        BF(sum)=b;BF(pi)=0u;BF(ps)=3u;
        break;
    case 3: BF(src)=b;BF(sum)=(uint16_t)(BF(sum)+b);BF(ps)=4u;break;
    case 4: BF(dst)=b;BF(sum)=(uint16_t)(BF(sum)+b);BF(ps)=5u;break;
    case 5: BF(cmd)=b;BF(sum)=(uint16_t)(BF(sum)+b);BF(ps)=6u;break;
    case 6:
        BF(arg)=b;BF(sum)=(uint16_t)(BF(sum)+b);
        BF(ps)=BF(len)?7u:8u;
        break;
    case 7:
        if(BF(pi)<G30_BMS_PAYLOAD_N) BF(payload)[BF(pi)]=b;
        BF(pi)++;
        BF(sum)=(uint16_t)(BF(sum)+b);
        if(BF(pi)>=BF(len)) BF(ps)=8u;
        break;
    case 8: BF(crc_lo)=b;BF(ps)=9u;break;
    case 9: {
        uint16_t want=(uint16_t)(~BF(sum));
        uint16_t got=(uint16_t)BF(crc_lo)|((uint16_t)b<<8);
        if(got==want){
            if(BF(src)==0x22u && BF(dst)==0x20u && BF(cmd)==0x04u){
                if(BF(valid)!=0xffffu) BF(valid)++;
                if(BF(outstanding) && BF(arg)!=BF(expected_arg)){
                    if(BF(unexpected)!=0xffffu) BF(unexpected)++;
                }
                g30_bms_final_decode(BF(arg),BF(payload),BF(len));
                if(BF(outstanding) && BF(arg)==BF(expected_arg)) BF(outstanding)=0u;
            }
        }else if(BF(crc_bad)!=0xffffu){
            BF(crc_bad)++;
        }
        BF(ps)=0u;
        break;
    }
    }
}

static uint8_t g30_bms_final_start_rx(void){
    huart3.Init.BaudRate=115200u;
    if(HAL_UART_Init(&huart3)!=HAL_OK) return 0u;
    memset(BF(rx_dma),0,sizeof(BF(rx_dma)));
    BF(rd)=0u;BF(ps)=0u;
    if(HAL_UART_Receive_DMA(&huart3,BF(rx_dma),G30_BMS_RX_N)!=HAL_OK) return 0u;
    __HAL_DMA_DISABLE_IT(huart3.hdmarx,DMA_IT_HT|DMA_IT_TC|DMA_IT_TE);
    CLEAR_BIT(huart3.Instance->CR1,USART_CR1_PEIE);
    CLEAR_BIT(huart3.Instance->CR3,USART_CR3_EIE);
    BF(dma_started)=1u;
    return 1u;
}

static void g30_bms_final_drain_rx(void){
    if(BF(dma_started)){
        uint16_t left=(uint16_t)huart3.hdmarx->Instance->CNDTR;
        uint8_t wr=(uint8_t)(G30_BMS_RX_N-((left<=G30_BMS_RX_N)?left:G30_BMS_RX_N));
        while(BF(rd)!=wr){
            g30_bms_final_parse_byte(BF(rx_dma)[BF(rd)]);
            BF(rd)++;
            if(BF(rd)>=G30_BMS_RX_N) BF(rd)=0u;
        }
    }
}

static void g30_bms_final_build_read(uint8_t reg,uint8_t ask,uint8_t out[10]){
    uint16_t sum,ck;
    out[0]=0x5au;out[1]=0xa5u;out[2]=0x01u;out[3]=0x20u;out[4]=0x22u;
    out[5]=0x01u;out[6]=reg;out[7]=ask;
    sum=(uint16_t)(out[2]+out[3]+out[4]+out[5]+out[6]+out[7]);
    ck=(uint16_t)(~sum);
    out[8]=(uint8_t)ck;out[9]=(uint8_t)(ck>>8);
}

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
    t0=HAL_GetTick();
    BF(phy_tx_prev)=(uint8_t)((GPIOB->IDR>>10)&1u);
    while((huart3.Instance->SR & USART_SR_TC)==0u){
        uint8_t v=(uint8_t)((GPIOB->IDR>>10)&1u);
        if(v==0u) BF(phy_tx_low)++;
        if(v!=BF(phy_tx_prev)) BF(phy_tx_edges)++;
        BF(phy_tx_prev)=v;
        if((HAL_GetTick()-t0)>5u) return HAL_TIMEOUT;
    }
    return HAL_OK;
}

static uint8_t g30_bms_final_send(uint8_t reg,uint8_t ask){
    uint8_t fr[10];
    g30_bms_final_build_read(reg,ask,fr);
    if(g30_bmsphy_tx_frame(fr,sizeof(fr))!=HAL_OK) return 0u;
    if(BF(tx)!=0xffffu) BF(tx)++;
    BF(outstanding)=1u;
    BF(expected_arg)=reg;
    BF(expected_len)=ask;
    BF(req_ms)=HAL_GetTick();
    return 1u;
}

static void g30_bms_service_10ms(void){
    static const uint8_t slow_reg[9]={0x10u,0x17u,0x18u,0x1bu,0x20u,0x36u,0x3bu,0x51u,0x70u};
    static const uint8_t slow_len[9]={14u,2u,4u,4u,2u,2u,2u,2u,12u};
    uint32_t now;

    if(!g30_bms_final_state){
        g30_bms_final_state=(g30_bms_final_state_t*)pvPortMalloc(sizeof(*g30_bms_final_state));
        if(!g30_bms_final_state) return;
        memset(g30_bms_final_state,0,sizeof(*g30_bms_final_state));
        if(!g30_bms_final_start_rx()) return;
        now=HAL_GetTick();
        BF(status_due_ms)=now;
        BF(cells_due_ms)=now+250u;
        BF(slow_due_ms)=now+500u;
    }

    g30_bms_final_drain_rx();
    now=HAL_GetTick();

    if(BF(outstanding)){
        if((now-BF(req_ms))<G30_BMS_RESPONSE_TIMEOUT_MS) return;
        BF(outstanding)=0u;
        if(BF(timeouts)!=0xffffu) BF(timeouts)++;
    }

    /* Stock communication heartbeat wins scheduling priority. */
    if((int32_t)(now-BF(status_due_ms))>=0){
        if(g30_bms_final_send(0x30u,12u)){
            BF(status_due_ms)=now+G30_BMS_STATUS_PERIOD_MS;
        }
        return;
    }

    if((int32_t)(now-BF(cells_due_ms))>=0){
        if(g30_bms_final_send(0x40u,20u)){
            BF(cells_due_ms)=now+G30_BMS_CELLS_PERIOD_MS;
        }
        return;
    }

    if((int32_t)(now-BF(slow_due_ms))>=0){
        uint8_t i=BF(slow_index);
        if(g30_bms_final_send(slow_reg[i],slow_len[i])){
            BF(slow_index)=(uint8_t)((i+1u)%9u);
            BF(slow_due_ms)=now+G30_BMS_SLOW_PERIOD_MS;
        }
    }
}

#undef BF

'''
s=s[:start]+block+s[end:]
p.write_text(s)

# Replace old probe terminal output with decoded telemetry.
p=root/"common_files/src/terminal.c"
s=p.read_text()
start=s.index('    }else if (strcmp(argv[0], "g30_bms") == 0 || strcmp(argv[0], "g30_bms_probe") == 0){')
end=s.index('    }else if (strcmp(argv[0], "g30_hall") == 0){',start)
rep=r'''    }else if (strcmp(argv[0], "g30_bms") == 0 || strcmp(argv[0], "g30_bms_final") == 0){
        commands_printf(phandle,
          "BMS final=1 uart=3 baud=115200 fresh=%u statusAge=%lums cellsAge=%lums tx=%u valid=%u crcBad=%u timeout=%u unexpected=%u",
          (unsigned)g30_bms_final_fresh(),
          (unsigned long)g30_bms_final_status_age_ms(),
          (unsigned long)g30_bms_final_cells_age_ms(),
          (unsigned)g30_bms_final_tx(),(unsigned)g30_bms_final_valid(),
          (unsigned)g30_bms_final_crc_bad(),(unsigned)g30_bms_final_timeouts(),
          (unsigned)g30_bms_final_unexpected());
        commands_printf(phandle,
          "BMS live status=%04X remain=%umAh soc=%u current=%ldmA pack=%lumV temp=%d/%dC balance=%04X soh=%u",
          (unsigned)g30_bms_final_status(),(unsigned)g30_bms_final_remaining_mah(),
          (unsigned)g30_bms_final_soc(),(long)g30_bms_final_current_ma(),
          (unsigned long)g30_bms_final_pack_mv(),
          (int)g30_bms_final_temp1_c(),(int)g30_bms_final_temp2_c(),
          (unsigned)g30_bms_final_balance(),(unsigned)g30_bms_final_soh());
        commands_printf(phandle,
          "BMS cells=%u,%u,%u,%u,%u,%u,%u,%u,%u,%u min=%u max=%u delta=%u",
          (unsigned)g30_bms_final_cell_mv(0),(unsigned)g30_bms_final_cell_mv(1),
          (unsigned)g30_bms_final_cell_mv(2),(unsigned)g30_bms_final_cell_mv(3),
          (unsigned)g30_bms_final_cell_mv(4),(unsigned)g30_bms_final_cell_mv(5),
          (unsigned)g30_bms_final_cell_mv(6),(unsigned)g30_bms_final_cell_mv(7),
          (unsigned)g30_bms_final_cell_mv(8),(unsigned)g30_bms_final_cell_mv(9),
          (unsigned)g30_bms_final_cell_min_mv(),(unsigned)g30_bms_final_cell_max_mv(),
          (unsigned)g30_bms_final_cell_delta_mv());
        commands_printf(phandle,
          "BMS meta sn=%s fw=%04X factory=%umAh actual=%umAh cycles=%u charges=%u mfg=%04X cfg=%04X",
          g30_bms_final_serial(),(unsigned)g30_bms_final_fw(),
          (unsigned)g30_bms_final_factory_mah(),(unsigned)g30_bms_final_actual_mah(),
          (unsigned)g30_bms_final_cycles(),(unsigned)g30_bms_final_charge_count(),
          (unsigned)g30_bms_final_mfg_date_raw(),(unsigned)g30_bms_final_config());
        commands_printf(phandle,
          "BMS policy=read_only stockREAD30=110ms cells=550ms observer_source=ADC protection_source=ADC writes=0 Cpin=untouched powerstage_locked=1");
        return;
'''
s=s[:start]+rep+s[end:]
p.write_text(s)

print("SESC BMS FINALREAD V1 applied: 115200-only read-only driver, Stock READ30 cadence, powerlock retained")
