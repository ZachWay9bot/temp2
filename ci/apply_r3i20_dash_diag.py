#!/usr/bin/env python3
"""R3I20 dashboard instrumentation overlay on the exact R3I19 CI source.
No changes to the motor-control loop, observer, IAP, flash layout, or recovery.
"""
from pathlib import Path
import sys

root=Path(sys.argv[1] if len(sys.argv)>1 else "SOURCE_KOXX3")
src=root/"common_files/src"
def once(path,old,new):
    data=path.read_text()
    cnt=data.count(old)
    if cnt != 1:
        raise RuntimeError(f"{path}: expected one anchor, got {cnt}: {old[:100]!r}")
    path.write_text(data.replace(old,new,1))

h=src/"defines.h"
once(h,'#define HW_NAME "G30D-R3I19-STOCK-DASH-FINAL"','#define HW_NAME "G30D-R3I20-DASH-DIAG"')

app=src/"app_uartcomm.c"
once(app,'#include <math.h>','#include <math.h>\n#include <stdio.h>')

diag=r"""
#ifdef G30P
/* Diagnostic state for the *existing* stock dashboard USART2/PA2 task.
 * Only reads existing peripheral registers; no new TX on the yellow wire. */
static volatile uint32_t dd_task_start, dd_alloc_failed, dd_uart_init, dd_rx_start;
static volatile uint32_t dd_bytes, dd_frames, dd_cmd64, dd_cmd65, dd_cmd61;
static volatile uint32_t dd_last_gas, dd_last_brake, dd_tx_calls, dd_tx_result;
static volatile uint32_t dd_tx_error, dd_meta_rx, dd_meta_query;
static port_str *dd_port;

/* Use VESC Tool's terminal command "g30dash", NOT the stock dashboard UART. */
void g30_dash_diag_format(char *out, unsigned cap, unsigned page){
    port_str *p=dd_port;
    uint32_t state=0u,err=0u,rx_dma=0u,tx_dma=0u,remaining=0u,cr1=0u,cr3=0u;
    if(p && p->uart){
        state=(uint32_t)p->uart->gState;
        err=(uint32_t)p->uart->ErrorCode;
        cr1=p->uart->Instance->CR1;
        cr3=p->uart->Instance->CR3;
        if(p->uart->hdmarx){
            rx_dma=(uint32_t)p->uart->hdmarx->State;
            remaining=p->uart->hdmarx->Instance->CNDTR;
        }
        if(p->uart->hdmatx) tx_dma=(uint32_t)p->uart->hdmatx->State;
    }
    if(page==0u){
        (void)snprintf(out,cap,
          "R3I20 DASH task=%lu allocFail=%lu uartInit=%lu rxDMA=%lu bytes=%lu valid=%lu 64=%lu 65=%lu 61=%lu",
          (unsigned long)dd_task_start,(unsigned long)dd_alloc_failed,
          (unsigned long)dd_uart_init,(unsigned long)dd_rx_start,
          (unsigned long)dd_bytes,(unsigned long)dd_frames,
          (unsigned long)dd_cmd64,(unsigned long)dd_cmd65,(unsigned long)dd_cmd61);
    }else if(page==1u){
        (void)snprintf(out,cap,
          "DASH gas=%lu brake=%lu txCalls=%lu txResult=%lu txErr=%lu metaRx=%lu query=%lu",
          (unsigned long)dd_last_gas,(unsigned long)dd_last_brake,
          (unsigned long)dd_tx_calls,(unsigned long)dd_tx_result,
          (unsigned long)dd_tx_error,(unsigned long)dd_meta_rx,
          (unsigned long)dd_meta_query);
    }else{
        (void)snprintf(out,cap,
          "USART2 state=%lu err=%lu dmaRx=%lu dmaTx=%lu CNDTR=%lu CR1=%04lX CR3=%04lX (status+1, 0=not called)",
          (unsigned long)state,(unsigned long)err,
          (unsigned long)rx_dma,(unsigned long)tx_dma,(unsigned long)remaining,
          (unsigned long)(cr1&0xFFFFu),(unsigned long)(cr3&0xFFFFu));
    }
}
#endif
"""
once(app,"void my_uart_send_data(unsigned char *buf, unsigned int len, port_str * port){",diag+"\nvoid my_uart_send_data(unsigned char *buf, unsigned int len, port_str * port){")
# Keep the R3I19 TX sequence and state transitions intact; record HAL results.
once(app,"HAL_UART_Transmit_DMA(port->uart, buf, len);\n\twhile(port->uart->hdmatx->State != HAL_DMA_STATE_READY){",
"""#ifdef G30P
    dd_tx_calls++;
    HAL_StatusTypeDef dd_ret = HAL_UART_Transmit_DMA(port->uart, buf, len);
    dd_tx_result=(uint32_t)dd_ret+1u;
    dd_tx_error=(uint32_t)port->uart->ErrorCode;
#else
    HAL_UART_Transmit_DMA(port->uart, buf, len);
#endif
\twhile(port->uart->hdmatx->State != HAL_DMA_STATE_READY){""")

once(app,"""\tuint8_t * usart_rx_dma_buffer = pvPortMalloc(port->rx_buffer_size);
\tHAL_UART_MspInit(port->uart);
\tif(port->half_duplex){
\t\tHAL_HalfDuplex_Init(port->uart);
\t}
\tHAL_UART_Receive_DMA(port->uart, usart_rx_dma_buffer, port->rx_buffer_size);""",
"""    dd_task_start++;
    dd_port=port;
\tuint8_t * usart_rx_dma_buffer = pvPortMalloc(port->rx_buffer_size);
    if(!usart_rx_dma_buffer){
        dd_alloc_failed++;
        port->task_handle=NULL;
        vTaskDelete(NULL);
        return;
    }
\tHAL_UART_MspInit(port->uart);
\tif(port->half_duplex){
        dd_uart_init=(uint32_t)HAL_HalfDuplex_Init(port->uart)+1u;
\t}
    dd_rx_start=(uint32_t)HAL_UART_Receive_DMA(port->uart, usart_rx_dma_buffer, port->rx_buffer_size)+1u;""")

# Observe every physically DMA-received byte.
once(app,"""\t\twhile(rd_ptr != uart_get_write_pos(port)) {
\t\t\tif(ninebot_parse(usart_rx_dma_buffer[rd_ptr] ,&frame)\t\t==0){""",
"""        while(rd_ptr != uart_get_write_pos(port)) {
            dd_bytes++;
            if(ninebot_parse(usart_rx_dma_buffer[rd_ptr] ,&frame)==0){
                dd_frames++;""") if False else None
# Formatting of the parser line is stable in the R3I19 overlay, with tabs/spaces
data=app.read_text()
old="if(ninebot_parse(usart_rx_dma_buffer[rd_ptr] ,&frame)\t\t==0){"
if old not in data:
    old="if(ninebot_parse(usart_rx_dma_buffer[rd_ptr] ,&frame)\t==0){"
if old not in data:
    old="if(ninebot_parse(usart_rx_dma_buffer[rd_ptr] ,&frame)\t==0){"
if old not in data:
    import re
    candidate=re.search(r'if\(ninebot_parse\(usart_rx_dma_buffer\[rd_ptr\]\s*,\s*&frame\)\s*==\s*0\)\s*\{',data)
    if not candidate: raise RuntimeError("Cannot find original ninebot_parse line")
    old=candidate.group(0)
once(app,old,"dd_bytes++;\\n            "+old+"\\n                dd_frames++;".replace("\\n","\n"))
once(app,"""                        adc1=frame.payload[1];
                        adc2=frame.payload[2];
                        VescToSTM_timeout_reset();""",
"""                        dd_last_gas=frame.payload[1];
                        dd_last_brake=frame.payload[2];
                        if(frame.cmd==0x64u) dd_cmd64++;
                        else if(frame.cmd==0x65u) dd_cmd65++;
                        else if(frame.cmd==0x61u) dd_cmd61++;
                        adc1=frame.payload[1];
                        adc2=frame.payload[2];
                        VescToSTM_timeout_reset();""")
once(app,"""                            if(query_due) g30_dash_metadata_last_query_ms=now?now:1u;
                            g30_dash_send_heartbeat_ack(port,query_due);""",
"""                            if(query_due){
                                dd_meta_query++;
                                g30_dash_metadata_last_query_ms=now?now:1u;
                            }
                            g30_dash_send_heartbeat_ack(port,query_due);""")
once(app,"""                        g30_dash_metadata_seen=1u;""","""                        dd_meta_rx++;
                        g30_dash_metadata_seen=1u;""")

vesc=src/"VescCommand.c"
once(vesc,'#include "app.h"', '#include "app.h"\n#ifdef G30P\nextern void g30_dash_diag_format(char *out, unsigned cap, unsigned page);\n#endif')
data=vesc.read_text()
start=data.index("static void commands_process_packet_g30(")
slot=data.index("switch (packet_id) {",start)+len("switch (packet_id) {")
insert=r"""
    case COMM_TERMINAL_CMD:
        /* Read-only diagnostics via IoT VESC Tool Terminal: g30dash */
        if(len>=7u && memcmp(data,"g30dash",7u)==0){
            for(unsigned page=0;page<3u;page++){
                uint8_t sb[PACKET_SIZE(150)];
                uint8_t *b=sb+PACKET_HEADER;
                b[0]=COMM_PRINT;
                g30_dash_diag_format((char*)(b+1),138u,page);
                reply_func(sb,(unsigned int)(strlen((char*)b+1u)+2u),phandle);
            }
        }
        break;
"""
vesc.write_text(data[:slot]+insert+data[slot:])

print("R3I20 DASH DIAG overlay applied",h,app,vesc)
print("No motor-control/observer/recovery code changed")
