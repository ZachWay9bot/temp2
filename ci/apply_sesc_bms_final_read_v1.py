#!/usr/bin/env python3
from pathlib import Path
root=Path("SOURCE_KOXX3")

# Final-read V1 deliberately starts from the hardware-validated FULL AUDIT V1
# semantic reader, not the V2 0x00..0x7F scanner. This removes the scan side
# effects while keeping the proven 115200 parser, Stock GPIO mode and hard
# powerstage lock unchanged.
p=root/"common_files/src/defines.h"
s=p.read_text()
old='SESC-DRV126-POWERCORE6500-BMS-FULL-AUDIT-V1'
new='SESC-DRV126-POWERCORE6500-BMS-FINAL-READ-V1'
assert old in s
p.write_text(s.replace(old,new,1))

p=root/"common_files/src/task_LED.h"
s=p.read_text()
s=s.replace('G30 BMS FULL AUDIT V1: read-only 115200 audit API.',
            'G30 BMS FINAL READ V1: verified read-only 115200 semantic API.')
p.write_text(s)

p=root/"common_files/src/task_LED.c"
s=p.read_text()
s=s.replace('G30 BMS FULL AUDIT V1\n *\n * Fixed 115200 8N1, read-only',
            'G30 BMS FINAL READ V1\n *\n * Fixed 115200 8N1, read-only')
s=s.replace('G30 BMS FULL AUDIT V1: passive MCU-pad activity sampler.',
            'G30 BMS FINAL READ V1: passive MCU-pad activity sampler.')
p.write_text(s)

p=root/"common_files/src/terminal.c"
s=p.read_text()
# Keep commands/API stable; only identify this as the verified non-scan reader.
s=s.replace('BMSAUDIT round=', 'BMSFINAL round=')
s=s.replace('BMSPHY note=passive_gpio_sample_16k no_pin_reconfig no_exti no_bms_write powerstage_locked',
            'BMSPHY note=115200_final_read no_bms_write Cpin_untouched powerstage_locked')
p.write_text(s)
print("BMS FINAL READ V1 applied: verified semantic reader, no full-register sweep, powerstage lock retained")
