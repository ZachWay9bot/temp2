#!/usr/bin/env python3
"""Light-byte 0/1 A/B candidate. No hardware claims, no VESC/FOC changes."""
from pathlib import Path
import sys
root=Path(sys.argv[1] if len(sys.argv)>1 else "SOURCE_KOXX3")
dash=(root/"common_files/src/g30_dash_link.c").read_text()
pwr=(root/"common_files/src/task_pwr.c").read_text()
assert dash.count("status[2]=m365_to_display.light?1u:0u;")==1
assert "status[2]=m365_to_display.light?100u:0u;" not in dash
assert "m365_to_display.light = !m365_to_display.light;" in pwr
assert "g30_dash_status_frame(status,tx)" in dash
assert "HAL_UART_Transmit(u,tx,(uint16_t)len,5u)" in dash
for light,crc in ((0,0xFEF7),(1,0xFEF6)):
    pkt=bytes([0x5A,0xA5,6,0x20,0x21,0x64,0,4,0x59,light,0,0,0])
    got=(~sum(pkt[2:]))&0xFFFF
    assert got==crc,(light,got,crc)
    print(f"LIGHT01 CHECK status={light} CRC={got:04X} PASS")
print("LIGHT01 SOURCE STATIC GATES PASS; hardware behavior NOT TESTED")
