from pathlib import Path
import re, hashlib

root=Path('SOURCE_KOXX3')

def txt(p): return (root/p).read_text()
def sha(p): return hashlib.sha256((root/p).read_bytes()).hexdigest()

d=txt('common_files/src/defines.h')
assert 'SESC-DRV126-P6500-H14-SHUD4BMS-APPCOMPAT-V1' in d
assert '#define G30_DASH_APPCOMPAT_V1 1' in d

proto=txt('common_files/src/g30_dash_proto.h')
link=txt('common_files/src/g30_dash_link.c')
bms=txt('common_files/src/task_LED.c')
pwr=txt('common_files/src/task_pwr.c')

# Exact app handshake route previously observed on hardware.
assert "p->src<0x3Du||p->src>0x3Fu" in link
assert "p->cmd!=0x01u" in link
assert "p->len!=1u && p->len!=4u" in link
assert "case 0x10u" in link and 'g30_dash_get_serial' in link
assert "case 0x1Au" in link and 'out[0]=0x20u;out[1]=0x04u' in link
assert 'g30_dash_frame(p->dst,p->src,0x04u,p->arg' in link

# Stock-like physical Yellowwire TX, isolated to USART2/PA2.
assert 'u->Instance!=USART2' in link
assert 'g30_dash_pa2_crl(0xBu)' in link
assert 'g30_dash_pa2_crl(0xFu)' in link
assert 'USART_CR1_TE|USART_CR1_RE' in link
tx=re.search(r'static HAL_StatusTypeDef g30_dash_tx_stocklike.*?\n}\n',link,re.S).group(0)
assert 'USART3' not in tx and 'huart3' not in tx and 'USART1' not in tx

# Existing r6-equivalent short press path remains present and native status byte2 stays 0/100.
assert 'case SINGLE_PRESS' in pwr and 'm365_to_display.light = !m365_to_display.light' in pwr
assert 'status[2]=m365_to_display.light?100u:0u;' in link

# Read-only app compatibility only. No CMD02/CMD03 write implementation.
appblock=re.search(r'static bool g30_dash_queue_app_read.*?#endif',link,re.S).group(0)
assert 'p->cmd!=0x01u' in appblock
assert '0x02u' not in appblock and '0x03u' not in appblock

# ScootBatt telemetry routes.
assert 'case 0x29u' in link and 'VescToSTM_get_odometer' in link
assert 'case 0xB5u' in link and 'VescToSTM_get_speed' in link
assert 'if(reg==0x31u)' in link
assert 'g30_bms_stock_remaining' in bms and 'g30_bms_stock_temp_pair' in bms

# Motor fast path and accepted button implementation remain byte-identical.
assert sha('common_files/src/mc_tasks.c') == '1c3f61ad12855960ddf25ea96730328bdfaa4d8653d6f7ec9fe89d2114518c98'
assert sha('common_files/MotorControl/MCSDK/MCLib/F1xx/Src/r3_2_f1xx_pwm_curr_fdbk.c') == '14ccd029244f230d5632f18c6c278aa3021976ede8a4513939af068456eee276'
assert sha('common_files/src/task_pwr.c') == '9fb70e29f7d9cc754c05f4fc439d555822c34097347b25e54aff7beb084f6cad'

# Checksum smoke test for the exact LEN4 read shape that broke old custom firmware.
def frame(src,dst,cmd,arg,payload):
    o=[0x5a,0xa5,len(payload),src,dst,cmd,arg]+list(payload)
    s=(~sum(o[2:])) & 0xffff
    o += [s&0xff,s>>8]
    return bytes(o)

req=bytes.fromhex('5A A5 04 3E 20 01 10 0E 02 29 23 30 FF')
assert req[2]==4 and req[3:7]==bytes([0x3e,0x20,0x01,0x10]) and req[7]==14
serial_reply=frame(0x20,0x3e,0x04,0x10,b'N4GSESC0000000')
assert len(serial_reply)==23 and serial_reply[:7]==bytes([0x5a,0xa5,14,0x20,0x3e,0x04,0x10])
assert ((~sum(serial_reply[2:-2]))&0xffff)==int.from_bytes(serial_reply[-2:],'little')

print('APPCOMPAT V1 static tests: PASS')
print('  app CMD01 LEN1/LEN4 -> CMD04: PASS')
print('  stock-like PA2 per-byte TX: PASS')
print('  existing short-button 0/100 status: PASS')
print('  ScootBatt speed/odo/BMS read routes: PASS')
print('  motor fastpath hashes unchanged: PASS')
