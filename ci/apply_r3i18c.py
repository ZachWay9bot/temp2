from pathlib import Path

root = Path("SOURCE_KOXX3/common_files/src")
app = root / "app_uartcomm.c"
defs = root / "defines.h"

s = app.read_text()

anchor = """    my_uart_send_data(tx,sizeof(tx),port);
}
#endif

void task_app(void * argument)
"""
insert = """    my_uart_send_data(tx,sizeof(tx),port);
}

static uint8_t g30_dash_meta_seen=0u;
static TickType_t g30_dash_meta_last=0;

static void g30_dash_send_meta_query(port_str *port){
    /* Stock G30 dashboard bootstrap observed on hardware:
     * ESC 20->21 CMD01 ARG00 LEN0, dashboard answers
     * 21->20 CMD04 ARG00 LEN13. Retry at most once per second
     * until that metadata ACK is received. */
    uint8_t tx[9]={0x5A,0xA5,0x00,0x20,0x21,0x01,0x00,0x00,0x00};
    uint16_t sum=0;
    for(unsigned i=2;i<=6;i++) sum=(uint16_t)(sum+tx[i]);
    uint16_t crc=(uint16_t)(~sum);
    tx[7]=(uint8_t)crc;
    tx[8]=(uint8_t)(crc>>8);
    my_uart_send_data(tx,sizeof(tx),port);
}
#endif

void task_app(void * argument)
"""
if anchor not in s:
    raise SystemExit("R3I18C helper anchor missing")
s = s.replace(anchor, insert, 1)

old = """                if(frame.addr==0x21 && frame.arg==0x00){
                    if((frame.cmd==0x64 || frame.cmd==0x65) && frame.len>=3u){
                        /* Native G30 hall payload:
                         * [dataLen, throttle, brake, updating, beeping, ...].
                         * CMD64 also requests the ESC display/status response.
                         * CMD65 is the normal hall update. Other stock commands stay inert. */
                        adc1=frame.payload[1];
                        adc2=frame.payload[2];
                        VescToSTM_timeout_reset();
                        app_check_timer();
                        if(frame.cmd==0x64) g30_dash_send_status(port);
                    }
                }
"""
new = """                if(frame.addr==0x21 && frame.arg==0x00){
                    if(frame.cmd==0x04 && frame.len==13u){
                        /* Stock dashboard ACK/metadata response to our bootstrap query. */
                        g30_dash_meta_seen=1u;
                    }
                    if((frame.cmd==0x64 || frame.cmd==0x65) && frame.len>=3u){
                        /* Native G30 hall payload:
                         * [dataLen, throttle, brake, updating, beeping, ...].
                         * CMD64 is the periodic heartbeat/status request and also
                         * carries hall values. CMD65 is the normal hall update. */
                        adc1=frame.payload[1];
                        adc2=frame.payload[2];
                        VescToSTM_timeout_reset();
                        app_check_timer();
                        if(frame.cmd==0x64){
                            g30_dash_send_status(port);
                            TickType_t now=xTaskGetTickCount();
                            if(!g30_dash_meta_seen &&
                               (g30_dash_meta_last==0 ||
                                (now-g30_dash_meta_last)>=pdMS_TO_TICKS(1000))){
                                g30_dash_send_meta_query(port);
                                g30_dash_meta_last=now;
                            }
                        }
                    }
                }
"""
if old not in s:
    raise SystemExit("R3I18C frame anchor missing")
s = s.replace(old, new, 1)
app.write_text(s)

d = defs.read_text()
old_id = '#define HW_NAME "G30D-R3I18B-STOCK-DASH-VERIFIED"'
new_id = '#define HW_NAME "G30D-R3I18C-DASH-HEARTBEAT-ACK"'
if old_id not in d:
    raise SystemExit("R3I18C build id anchor missing")
defs.write_text(d.replace(old_id, new_id, 1))

print("R3I18C heartbeat/bootstrap ACK transform applied")
