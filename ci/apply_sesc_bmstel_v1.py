#!/usr/bin/env python3
from pathlib import Path

root=Path("SOURCE_KOXX3")

# Build ID
p=root/"common_files/src/defines.h"
s=p.read_text()
old='#define HW_NAME "SESC-DRV126-POWERCORE6500-SPEEDTEL-V1"'
new='#define HW_NAME "SESC-DRV126-POWERCORE6500-BMSTEL-V1"'
assert old in s
p.write_text(s.replace(old,new,1))

# Header API
p=root/"common_files/src/task_LED.h"
s=p.read_text()
needle='''void task_LED_init();
void task_LED_set_brake_light(en_brake mode);
'''
rep='''void task_LED_init();
void task_LED_set_brake_light(en_brake mode);

/* G30 BMSTEL V1: stock-like USART3 BMS polling, telemetry only. */
uint16_t g30_bms_pack_cv(void);
int16_t g30_bms_current_ca(void);
uint8_t g30_bms_soc_pct(void);
uint32_t g30_bms_age_ms(void);
uint16_t g30_bms_tx_count(void);
uint16_t g30_bms_rx_ok_count(void);
uint16_t g30_bms_crc_bad_count(void);
uint8_t g30_bms_fresh(void);
'''
assert needle in s
p.write_text(s.replace(needle,rep,1))

# Minimal BMS service inside existing LED task, no new task.
p=root/"common_files/src/task_LED.c"
s=p.read_text()
needle='''extern stm_state VescToSTM_mode;

void prv_LED_blink(uint32_t speed){'''
block=r'''extern stm_state VescToSTM_mode;

/* -------------------------------------------------------------------------
 * G30 BMSTEL V1
 *
 * Stock DRV126 sends ESC(0x20)->BMS(0x22) READ(0x01), ARG 0x30,
 * payload 0x0C. Exact stock frame:
 *   5A A5 01 20 22 01 30 0C 7F FF
 *
 * The BMS response block at 0x30 is 12 bytes / six 16-bit registers:
 *   0x30 status, 0x31 capacity, 0x32 SOC, 0x33 current,
 *   0x34 pack voltage (0.01 V), 0x35 temperature.
 *
 * This first child is deliberately telemetry-only. The BMS voltage is NOT
 * fed into Hall FOC, FO76, protection or VESC bus-voltage reporting yet.
 *
 * RAM is intentionally tiny because this build has very little static headroom.
 * USART3 RX uses its existing circular DMA channel, but all DMA transfer/error
 * interrupts are disabled after start. The low-priority 10 ms LED task polls
 * CNDTR and parses received bytes, so BMS DMA cannot preempt the FOC ISR.
 * ------------------------------------------------------------------------- */

#define G30_BMS_RX_N 24u

static uint8_t g30_bms_rx_dma[G30_BMS_RX_N];
static uint16_t g30_bms_pack_cv_v;
static int16_t g30_bms_current_ca_v;
static uint8_t g30_bms_soc_pct_v;
static uint32_t g30_bms_last_ok_ms;
static uint16_t g30_bms_tx_v;
static uint16_t g30_bms_rx_ok_v;
static uint16_t g30_bms_crc_bad_v;
static uint8_t g30_bms_rd;
static uint8_t g30_bms_dma_started;
static uint8_t g30_bms_poll_div;

/* Streaming parser state. No second frame buffer. */
static uint8_t g30_bms_ps;
static uint8_t g30_bms_len;
static uint8_t g30_bms_pi;
static uint8_t g30_bms_src;
static uint8_t g30_bms_dst;
static uint8_t g30_bms_cmd;
static uint8_t g30_bms_arg;
static uint8_t g30_bms_crc_lo;
static uint16_t g30_bms_sum;
static uint16_t g30_bms_tmp_soc;
static uint16_t g30_bms_tmp_cur;
static uint16_t g30_bms_tmp_v;

uint16_t g30_bms_pack_cv(void){ return g30_bms_pack_cv_v; }
int16_t g30_bms_current_ca(void){ return g30_bms_current_ca_v; }
uint8_t g30_bms_soc_pct(void){ return g30_bms_soc_pct_v; }
uint32_t g30_bms_age_ms(void){
    if(!g30_bms_last_ok_ms) return 0xffffffffu;
    return HAL_GetTick()-g30_bms_last_ok_ms;
}
uint16_t g30_bms_tx_count(void){ return g30_bms_tx_v; }
uint16_t g30_bms_rx_ok_count(void){ return g30_bms_rx_ok_v; }
uint16_t g30_bms_crc_bad_count(void){ return g30_bms_crc_bad_v; }
uint8_t g30_bms_fresh(void){
    return g30_bms_last_ok_ms && (HAL_GetTick()-g30_bms_last_ok_ms)<1000u;
}

static void g30_bms_parse_byte(uint8_t b){
    switch(g30_bms_ps){
    default:
    case 0:
        if(b==0x5au) g30_bms_ps=1u;
        break;
    case 1:
        if(b==0xa5u) g30_bms_ps=2u;
        else g30_bms_ps=(b==0x5au)?1u:0u;
        break;
    case 2:
        g30_bms_len=b;
        if(g30_bms_len>16u){ g30_bms_ps=0u; break; }
        g30_bms_sum=b;
        g30_bms_pi=0u;
        g30_bms_ps=3u;
        break;
    case 3:
        g30_bms_src=b; g30_bms_sum=(uint16_t)(g30_bms_sum+b); g30_bms_ps=4u;
        break;
    case 4:
        g30_bms_dst=b; g30_bms_sum=(uint16_t)(g30_bms_sum+b); g30_bms_ps=5u;
        break;
    case 5:
        g30_bms_cmd=b; g30_bms_sum=(uint16_t)(g30_bms_sum+b); g30_bms_ps=6u;
        break;
    case 6:
        g30_bms_arg=b; g30_bms_sum=(uint16_t)(g30_bms_sum+b);
        g30_bms_tmp_soc=0u; g30_bms_tmp_cur=0u; g30_bms_tmp_v=0u;
        g30_bms_ps=g30_bms_len?7u:8u;
        break;
    case 7:
        g30_bms_sum=(uint16_t)(g30_bms_sum+b);
        if(g30_bms_src==0x22u && g30_bms_dst==0x20u &&
           g30_bms_cmd==0x04u && g30_bms_arg==0x30u){
            if(g30_bms_pi==4u) g30_bms_tmp_soc=(uint16_t)b;
            else if(g30_bms_pi==5u) g30_bms_tmp_soc|=(uint16_t)b<<8;
            else if(g30_bms_pi==6u) g30_bms_tmp_cur=(uint16_t)b;
            else if(g30_bms_pi==7u) g30_bms_tmp_cur|=(uint16_t)b<<8;
            else if(g30_bms_pi==8u) g30_bms_tmp_v=(uint16_t)b;
            else if(g30_bms_pi==9u) g30_bms_tmp_v|=(uint16_t)b<<8;
        }
        g30_bms_pi++;
        if(g30_bms_pi>=g30_bms_len) g30_bms_ps=8u;
        break;
    case 8:
        g30_bms_crc_lo=b; g30_bms_ps=9u;
        break;
    case 9: {
        uint16_t expected=(uint16_t)(~g30_bms_sum);
        uint16_t got=(uint16_t)g30_bms_crc_lo|((uint16_t)b<<8);
        if(got==expected){
            if(g30_bms_src==0x22u && g30_bms_dst==0x20u &&
               g30_bms_cmd==0x04u && g30_bms_arg==0x30u && g30_bms_len>=10u){
                g30_bms_pack_cv_v=g30_bms_tmp_v;
                g30_bms_current_ca_v=(int16_t)g30_bms_tmp_cur;
                g30_bms_soc_pct_v=(g30_bms_tmp_soc>100u)?100u:(uint8_t)g30_bms_tmp_soc;
                g30_bms_last_ok_ms=HAL_GetTick();
                g30_bms_rx_ok_v++;
            }
        }else{
            g30_bms_crc_bad_v++;
        }
        g30_bms_ps=0u;
        break;
    }
    }
}

static void g30_bms_service_10ms(void){
    if(!g30_bms_dma_started){
        if(HAL_UART_Receive_DMA(&huart3,g30_bms_rx_dma,G30_BMS_RX_N)==HAL_OK){
            /* Circular RX continues without callbacks. Remove all BMS-DMA IRQ load
             * from the real-time path; the task polls DMA CNDTR instead. */
            __HAL_DMA_DISABLE_IT(huart3.hdmarx,DMA_IT_HT|DMA_IT_TC|DMA_IT_TE);
            CLEAR_BIT(huart3.Instance->CR1,USART_CR1_PEIE);
            CLEAR_BIT(huart3.Instance->CR3,USART_CR3_EIE);
            g30_bms_dma_started=1u;
        }
    }

    if(g30_bms_dma_started){
        uint16_t left=(uint16_t)huart3.hdmarx->Instance->CNDTR;
        uint8_t wr=(uint8_t)(G30_BMS_RX_N-((left<=G30_BMS_RX_N)?left:G30_BMS_RX_N));
        while(g30_bms_rd!=wr){
            g30_bms_parse_byte(g30_bms_rx_dma[g30_bms_rd]);
            g30_bms_rd++;
            if(g30_bms_rd>=G30_BMS_RX_N) g30_bms_rd=0u;
        }

        /* Existing task cadence is 10 ms. 11 ticks ~= 110 ms, matching the
         * 105 ms nominal Stock DRV126 BMS service without adding a timer/task. */
        g30_bms_poll_div++;
        if(g30_bms_poll_div>=11u){
            static const uint8_t stock_read30[10]={
                0x5a,0xa5,0x01,0x20,0x22,0x01,0x30,0x0c,0x7f,0xff
            };
            g30_bms_poll_div=0u;
            if(HAL_UART_Transmit(&huart3,(uint8_t*)stock_read30,sizeof(stock_read30),5u)==HAL_OK){
                g30_bms_tx_v++;
            }
        }
    }
}

void prv_LED_blink(uint32_t speed){'''
assert needle in s
s=s.replace(needle,block,1)
needle='''		vTaskDelay(MS_TO_TICKS(10));'''
rep='''		g30_bms_service_10ms();
		vTaskDelay(MS_TO_TICKS(10));'''
assert needle in s
s=s.replace(needle,rep,1)
p.write_text(s)

# Terminal read-only diagnostic
p=root/"common_files/src/terminal.c"
s=p.read_text()
needle='''    }else if (strcmp(argv[0], "g30_hall") == 0){'''
rep='''    }else if (strcmp(argv[0], "g30_bms") == 0){
        uint32_t age=g30_bms_age_ms();
        commands_printf(phandle,
            "BMS stockPoll=1 uart=3 fresh=%u tx=%u rx=%u crcBad=%u pack=%umV current=%dmA soc=%u age=%lums adc=%ldmV",
            (unsigned)g30_bms_fresh(),
            (unsigned)g30_bms_tx_count(),(unsigned)g30_bms_rx_ok_count(),
            (unsigned)g30_bms_crc_bad_count(),
            (unsigned)((uint32_t)g30_bms_pack_cv()*10u),
            (int)((int32_t)g30_bms_current_ca()*10),
            (unsigned)g30_bms_soc_pct(),
            (unsigned long)age,
            (long)(VescToSTM_get_bus_voltage()*1000.0f));
        commands_printf(phandle,
            "BMS note=telemetry_only observer_source=ADC protection_source=ADC frame=5AA501202201300C7FFF");
        return;
    }else if (strcmp(argv[0], "g30_hall") == 0){'''
assert needle in s
s=s.replace(needle,rep,1)
p.write_text(s)

print("SESC POWERCORE6500 BMSTEL V1 applied: exact Stock126 read30 keepalive + read-only BMS telemetry")
