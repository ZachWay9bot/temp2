#!/usr/bin/env python3
from pathlib import Path
root=Path("SOURCE_KOXX3")

p=root/"common_files/src/defines.h"
s=p.read_text()
s=s.replace('SESC-DRV126-POWERCORE6500-BMS-FULL-AUDIT-V1','SESC-DRV126-POWERCORE6500-BMS-FULL-AUDIT-V2',1)
p.write_text(s)

p=root/"common_files/src/task_LED.h"
s=p.read_text()
needle='uint16_t g30_bms_audit_round(void);'
rep=needle+'''
uint16_t g30_bms_scan_tx(void);
uint16_t g30_bms_scan_ok(void);
uint16_t g30_bms_scan_timeout(void);
uint8_t g30_bms_scan_seen(uint8_t reg);
uint8_t g30_bms_scan_byte(uint8_t reg,uint8_t idx);
'''
assert needle in s
s=s.replace(needle,rep,1)
p.write_text(s)

p=root/"common_files/src/task_LED.c"
s=p.read_text()
needle='''  uint32_t phy_tx_low;
  uint32_t phy_tx_edges;'''
rep='''  uint8_t scan_data[128][2];
  uint8_t scan_seen[16];
  uint16_t scan_tx;
  uint16_t scan_ok;
  uint16_t scan_timeout;
  uint8_t scan_reg;
  uint8_t sweep;
  uint8_t scan_got;

  uint32_t phy_tx_low;
  uint32_t phy_tx_edges;'''
assert needle in s
s=s.replace(needle,rep,1)

needle='''uint16_t g30_bms_audit_round(void){ return g30_bms_audit_state?BA(round):0u; }

/* Compatibility'''
rep='''uint16_t g30_bms_audit_round(void){ return g30_bms_audit_state?BA(round):0u; }
uint16_t g30_bms_scan_tx(void){ return g30_bms_audit_state?BA(scan_tx):0u; }
uint16_t g30_bms_scan_ok(void){ return g30_bms_audit_state?BA(scan_ok):0u; }
uint16_t g30_bms_scan_timeout(void){ return g30_bms_audit_state?BA(scan_timeout):0u; }
uint8_t g30_bms_scan_seen(uint8_t reg){
  if(!g30_bms_audit_state || reg>=128u) return 0u;
  return (BA(scan_seen)[reg>>3]>>(reg&7u))&1u;
}
uint8_t g30_bms_scan_byte(uint8_t reg,uint8_t idx){
  if(!g30_bms_audit_state || reg>=128u || idx>1u) return 0u;
  return BA(scan_data)[reg][idx];
}

/* Compatibility'''
assert needle in s
s=s.replace(needle,rep,1)

needle='''      if(BA(src)==0x22u && BA(dst)==0x20u && BA(cmd)==0x04u){
        int8_t fs=g30_bms_find_slot(BA(arg));'''
rep='''      if(BA(src)==0x22u && BA(dst)==0x20u && BA(cmd)==0x04u){
        if(BA(sweep) && BA(arg)==BA(scan_reg) && BA(len)>=2u && BA(scan_reg)<128u){
          BA(scan_data)[BA(scan_reg)][0]=BA(parse_data)[0];
          BA(scan_data)[BA(scan_reg)][1]=BA(parse_data)[1];
          BA(scan_seen)[BA(scan_reg)>>3] |= (uint8_t)(1u<<(BA(scan_reg)&7u));
          if(BA(scan_ok)!=0xFFFFu) BA(scan_ok)++;
          BA(scan_got)=1u;
        }
        int8_t fs=g30_bms_find_slot(BA(arg));'''
assert needle in s
s=s.replace(needle,rep,1)

needle='''  if(BA(phase)==1u){
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
  }'''
rep='''  if(BA(phase)==1u){
    uint8_t fr[10];
    BA(req_ms)=HAL_GetTick();
    if(BA(sweep)){
      BA(scan_got)=0u;
      g30_bms_audit_build_read(BA(scan_reg),2u,fr);
      if(g30_bms_audit_tx_frame(fr,sizeof(fr))==HAL_OK && BA(scan_tx)!=0xFFFFu) BA(scan_tx)++;
    }else{
      uint8_t sl=BA(slot);
      BA(got_this)=0u;
      g30_bms_audit_build_read(g30_bms_audit_regs[sl],g30_bms_audit_asks[sl],fr);
      if(g30_bms_audit_tx_frame(fr,sizeof(fr))==HAL_OK && BA(tx)[sl]!=0xFFFFu) BA(tx)[sl]++;
    }
    g30_bms_audit_rx_window(12u);
    BA(wait_ticks)=8u;
    BA(phase)=2u;
    return;
  }

  if(BA(phase)==2u){
    if(BA(sweep)){
      if(!BA(scan_got) && BA(scan_timeout)!=0xFFFFu) BA(scan_timeout)++;
      BA(scan_reg)++;
      if(BA(scan_reg)>=128u){
        BA(scan_reg)=0u;
        BA(sweep)=0u;
        BA(slot)=0u;
        if(BA(round)!=0xFFFFu) BA(round)++;
      }
    }else{
      uint8_t sl=BA(slot);
      if(!BA(got_this) && BA(timeout)[sl]!=0xFFFFu) BA(timeout)[sl]++;
      BA(slot)++;
      if(BA(slot)>=G30_BMS_AUDIT_SLOTS){
        BA(slot)=0u;
        BA(scan_reg)=0u;
        BA(sweep)=1u;
      }
    }
    BA(phase)=1u;
  }'''
assert needle in s
s=s.replace(needle,rep,1)
p.write_text(s)

p=root/"common_files/src/terminal.c"
s=p.read_text()
needle='''        commands_printf(phandle,"BMSAUDIT round=%u baud=115200 tx=%lu ok=%lu timeout=%lu raw=%lu crcBad=%u unexpected=%u",
          (unsigned)g30_bms_audit_round(),(unsigned long)txsum,(unsigned long)oksum,(unsigned long)tosum,
          (unsigned long)g30_bms_audit_raw_total(),(unsigned)g30_bms_audit_crc_bad(),(unsigned)g30_bms_audit_unexpected());'''
rep='''        commands_printf(phandle,"BMSAUDIT round=%u baud=115200 tx=%lu ok=%lu timeout=%lu raw=%lu crcBad=%u unexpected=%u scanTx=%u scanOk=%u scanTimeout=%u",
          (unsigned)g30_bms_audit_round(),(unsigned long)txsum,(unsigned long)oksum,(unsigned long)tosum,
          (unsigned long)g30_bms_audit_raw_total(),(unsigned)g30_bms_audit_crc_bad(),(unsigned)g30_bms_audit_unexpected(),
          (unsigned)g30_bms_scan_tx(),(unsigned)g30_bms_scan_ok(),(unsigned)g30_bms_scan_timeout());'''
assert needle in s
s=s.replace(needle,rep,1)

needle='''        return;
    }else if (strcmp(argv[0], "g30_hall") == 0){'''
rep='''        return;
    }else if (strcmp(argv[0], "g30_bms_scan") == 0){
        uint16_t r;
        uint16_t seen=0u,nonzero=0u;
        for(r=0u;r<128u;r++){
          uint8_t ok=g30_bms_scan_seen((uint8_t)r);
          uint8_t lo=g30_bms_scan_byte((uint8_t)r,0u);
          uint8_t hi=g30_bms_scan_byte((uint8_t)r,1u);
          if(ok) seen++;
          if(ok && (lo||hi)) nonzero++;
          commands_printf(phandle,"BASCAN reg=%02X seen=%u data=%02X%02X word=%04X",
            (unsigned)r,(unsigned)ok,(unsigned)lo,(unsigned)hi,(unsigned)((uint16_t)lo|((uint16_t)hi<<8)));
        }
        commands_printf(phandle,"BASCAN_SUM seen=%u/128 nonzero=%u tx=%u ok=%u timeout=%u",
          (unsigned)seen,(unsigned)nonzero,(unsigned)g30_bms_scan_tx(),
          (unsigned)g30_bms_scan_ok(),(unsigned)g30_bms_scan_timeout());
        return;
    }else if (strcmp(argv[0], "g30_hall") == 0){'''
assert needle in s
s=s.replace(needle,rep,1)
p.write_text(s)

print("BMS FULL AUDIT V2 applied: known semantic audit + complete read-only 0x00..0x7F sweep")
