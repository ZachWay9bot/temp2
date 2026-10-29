/* HF4 dashboard link R1: transport and raw input diagnosis only.
 * No ADC override, motor setter, auto-arm, timeout reset, or flash command.
 * USART1/VESC motor commands and the complete HF4 motor core are unchanged. */
#include "main.h"
#include "task_init.h"
#include "g30_dash_link.h"
#include "g30_dash_proto.h"
#include "ninebot.h"
#include "VescToSTM.h"
#include "VescCommand.h"
#include "task.h"
#include <math.h>

typedef struct {
    port_str *port;
    g30_dash_parser parser;
    uint8_t rx[128];
    uint32_t bytes, valid, bad, cmd64, cmd65;
    uint32_t tx_calls, tx_ok, tx_fail, rx_errors;
    uint16_t version;
    uint8_t gas, brake, init_result, rx_result, tx_result;
} dash_link_state;
/* SRAM footprint is allocated from the existing FreeRTOS heap, not carved
 * out of the almost-full static data region. One UART owner, one task. */
static dash_link_state *dash;
static uint32_t alloc_failed;

static unsigned rx_pos(dash_link_state *d) {
    return (128u-d->port->uart->hdmarx->Instance->CNDTR)&127u;
}

static void send_status(dash_link_state *d) {
    UART_HandleTypeDef *u=d->port->uart;
    uint8_t status[6]={m365_to_display.mode,0,0,0,0,0};
    uint8_t tx[15];
    float level=VescToSTM_get_battery_level(0);
    float speed=fabsf(VescToSTM_get_speed()*3.6f);
    if(!isfinite(level)||level<0.0f) level=0.0f;
    if(level>1.0f) level=1.0f;
    if(!isfinite(speed)||speed<0.0f) speed=0.0f;
    if(speed>255.0f) speed=255.0f;
    status[1]=(uint8_t)(100.0f*level+0.5f);
    status[2]=m365_to_display.light?100u:0u;
    status[4]=(uint8_t)(speed+0.5f);
    status[5]=(uint8_t)(pMCI[M1]->pSTM->hFaultOccurred&0xFFu);
    unsigned len=g30_dash_status_frame(status,tx);
    d->tx_calls++;
    /* No TX-DMA buffer lifetime or forced gState=READY. HAL blocking TX
     * waits for UART_FLAG_TC: the final stop bit leaves before RX resumes.
     * Interrupts, including the original FOC ISR, remain enabled. */
    HAL_StatusTypeDef result=HAL_HalfDuplex_EnableTransmitter(u);
    if(result==HAL_OK) result=HAL_UART_Transmit(u,tx,(uint16_t)len,5u);
    d->tx_result=(uint8_t)result+1u;
    if(result==HAL_OK) d->tx_ok++; else d->tx_fail++;
    /* Return to receive mode on both success and failure. */
    if(HAL_HalfDuplex_EnableReceiver(u)!=HAL_OK) d->rx_errors++;
}

static void dash_task(void *arg) {
    dash_link_state *d=(dash_link_state*)arg;
    UART_HandleTypeDef *u=d->port->uart;
    unsigned rd=0;
    d->init_result=(uint8_t)HAL_HalfDuplex_Init(u)+1u;
    if(d->init_result==1u && HAL_HalfDuplex_EnableReceiver(u)==HAL_OK)
        d->rx_result=(uint8_t)HAL_UART_Receive_DMA(u,d->rx,sizeof(d->rx))+1u;
    if(d->rx_result!=1u) {
        /* Remain inspectable via COM9; no drive fallback or automatic restart. */
        for(;;) vTaskDelay(pdMS_TO_TICKS(100));
    }
    CLEAR_BIT(u->Instance->CR3,USART_CR3_EIE);
    /* Circular reception needs no RX half/full IRQ callbacks. Disable only
     * these DMA interrupts; hardware DMA continues to fill the ring. */
    __HAL_DMA_DISABLE_IT(u->hdmarx,DMA_IT_HT|DMA_IT_TC);
    for(;;) {
        unsigned reply_pending=0;
        while(rd!=rx_pos(d)) {
            uint8_t b=d->rx[rd]; rd=(rd+1u)&127u; d->bytes++;
            int result=g30_dash_feed(&d->parser,b,HAL_GetTick());
            if(result<0) d->bad++;
            if(result==1) {
                d->valid++;
                unsigned kind=g30_dash_input_kind(&d->parser);
                if(kind) {
                    d->gas=d->parser.payload[1];d->brake=d->parser.payload[2];
                    if(kind==64u) {
                        d->cmd64++;reply_pending=1;
                        if(d->parser.len>=7u)
                            d->version=(uint16_t)d->parser.payload[5]|((uint16_t)d->parser.payload[6]<<8);
                    } else d->cmd65++;
                }
            }
        }
        /* Do not switch away from RX in the middle of a newly arriving frame. */
        if(reply_pending && d->parser.state==0u && rd==rx_pos(d)) send_status(d);
        if(u->Instance->SR&(USART_SR_ORE|USART_SR_FE|USART_SR_NE|USART_SR_PE)) {
            d->rx_errors++;
            __HAL_UART_CLEAR_OREFLAG(u);
        }
        /* 1 tick (0.5 ms at the existing 2-kHz RTOS tick), rather than the old
         * two 10-tick waits. Never send an unsolicited periodic status frame. */
        vTaskDelay(1);
    }
}

void g30_dash_link_start(port_str *port) {
    if(port->task_handle) return;
    if(dash) return;
    dash_link_state *d=pvPortMalloc(sizeof(*d));
    if(!d){alloc_failed++;return;}
    memset(d,0,sizeof(*d));d->port=port;dash=d;
    if(xTaskCreate(dash_task,"DASH-LINK",256,d,PRIO_BELOW_NORMAL,&port->task_handle)!=pdPASS) {
        dash=NULL;alloc_failed++;vPortFree(d);
    }
}

void g30_dash_link_print(PACKET_STATE_t *phandle) {
    dash_link_state *d=dash;
    if(!d){commands_printf(phandle,"HF4 DASH R1 readonly=1 task=0 allocFail=%lu",(unsigned long)alloc_failed);return;}
    commands_printf(phandle,"HF4 DASH R1 readonly=1 init=%u rxDMA=%u bytes=%lu valid=%lu bad=%lu",
        d->init_result,d->rx_result,(unsigned long)d->bytes,(unsigned long)d->valid,(unsigned long)d->bad);
    commands_printf(phandle,"DASH gas=%u brake=%u 64=%lu 65=%lu ver=%04x txCalls=%lu txOK=%lu txFail=%lu txLast=%u",
        d->gas,d->brake,(unsigned long)d->cmd64,(unsigned long)d->cmd65,d->version,
        (unsigned long)d->tx_calls,(unsigned long)d->tx_ok,(unsigned long)d->tx_fail,d->tx_result);
    UART_HandleTypeDef *u=d->port->uart;
    commands_printf(phandle,"USART2 SR=%04lx CR1=%04lx CR3=%04lx CNDTR=%lu rxErr=%lu stackFree=%u heap=%u",
        (unsigned long)u->Instance->SR,(unsigned long)u->Instance->CR1,(unsigned long)u->Instance->CR3,
        (unsigned long)u->hdmarx->Instance->CNDTR,(unsigned long)d->rx_errors,
        (unsigned)uxTaskGetStackHighWaterMark(d->port->task_handle),(unsigned)xPortGetFreeHeapSize());
}
