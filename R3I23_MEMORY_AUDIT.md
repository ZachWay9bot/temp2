# R3I23 DASH-ONLY – RAM/Heap/Stack Audit

## Ausgangspunkt R3I22

ARM size:
- text: 90284
- data: 1428
- bss: 18952
- linker RAM gate: 20380 / 20480 bytes
- nominal linker reserve: 100 bytes

This linker number is not the same as free runtime RAM.

### Reserved RAM composition

- FreeRTOS heap `ucHeap`: 13312 bytes (13 KiB)
- linker `._user_heap_stack`: 1536 bytes
  - `_Min_Heap_Size = 0x200` = 512 bytes
  - `_Min_Stack_Size = 0x400` = 1024 bytes
- all remaining linked data/bss: 5532 bytes

The 1536-byte linker heap/stack block must not be removed merely to improve the percentage.
Newlib `malloc/_malloc_r/_sbrk` is linked through libc/stdio paths, and the MSP reserve is also real protection.

### FreeRTOS heap

G30 uses:
`HEAP_SIZE_KB = 13`
and heap_4.

The existing R1 hardware logs showed about 5584 bytes free FreeRTOS heap after the dashboard task was alive.
R3I22/R3I23 need a new hardware minimum-ever measurement before changing the heap size.

Do NOT reduce `HEAP_SIZE_KB` just to gain static linker headroom.

Reasons:
- CLI/VESC packet buffers are dynamically allocated.
- `COMM_SAMPLE_PRINT` allocates two current arrays on G30 because `SCOPE_UVW=0`.
- At the G30 cap of 500 samples that is 2000 bytes payload plus heap_4 block overhead.
- configuration commands also make temporary heap allocations.
- future fragmentation matters more than the nominal current-free value.

### Task stacks

Configured task stack depths:
- VESC CLI: 320 words = 1280 bytes
- DASH-LINK: 256 words = 1024 bytes
- LED: 256 words = 1024 bytes
- medium-frequency task: 128 words = 512 bytes
- safety task: 128 words = 512 bytes
- idle task: 128 words = 512 bytes
- timer task: 128 words = 512 bytes

R1 hardware evidence for DASH-LINK:
- stack high-water mark: 204 words free
- therefore only about 52 words / 208 bytes had been used at that observation point

This is not sufficient evidence to shrink the R3I23 DASH stack, because R3I23 also executes the dashboard drive-control calls. Measure R3I23 hardware high-water mark first.

### Largest non-heap static candidates

Notable RAM symbols in R3I22:
- `mc_conf`: 540 bytes
- `g30_hall_trace.samples`: 384 bytes
- FreeRTOS ready-list structures: 320 bytes
- Newlib stdio state `__sf`: 312 bytes
- `PQD_MotorPowMeasM1`: 296 bytes
- `HALL_M1`: 220 bytes
- FO76 observer diagnostic state: 192-byte block plus smaller fields

The 384-byte Hall trace is diagnostic, but it is automatically seeded during push-start and written from Hall capture IRQs.
Do not remove or heap-allocate it without a separate motor-path decision.

## Important functional finding

R3I22 still created and started the legacy `ADC_UP` FreeRTOS software timer on G30:

`task_init -> app_adc_init_timer()`

and

`task_cli -> app_check_timer()`

The callback `vTimerCallback` could execute the inherited ADC control path and call motor setters such as:
- `VescToSTM_set_current_rel`
- brake-current paths depending on app configuration
- PID/speed path depending on app configuration

This violates the intended DASH-only architecture because it leaves a second periodic motor-command source alive beside `g30_dash_link`.

## R3I23 correction

For G30P only:
- `app_adc_init_timer()` is a no-op
- `app_check_timer()` is a no-op
- `ADC_UP` is never created or started
- Mode/TEMP helpers from `app_uartcomm.c` remain available
- VESC Tool UART remains available
- dashboard drive path remains in `g30_dash_link.c`
- FOC, observer, push-start and motor-control sources are unchanged

Linker garbage collection removes `vTimerCallback` from the final R3I23 ELF.

R3I23 build result:
- Build ID: `G30D-R3I23-DASH-ONLY`
- Flash: 90720 bytes versus 91712 on R3I22, saving 992 bytes
- RAM gate: 20372 / 20480 versus 20380 / 20480, saving 8 linked bytes
- nominal linker reserve: 108 bytes
- all prior R3I21/R3I22 dashboard/button/status tests: PASS
- R3I15HF4 motor/observer static gates: PASS

## Decision

Keep:
- 13 KiB FreeRTOS heap
- 1024-byte DASH task stack
- 384-byte Hall trace
- 512-byte newlib minimum heap
- 1024-byte MSP minimum stack

until R3I23 hardware telemetry provides:
- current free heap
- minimum-ever free heap
- DASH stack high-water mark
- ideally CLI/LED stack high-water marks

The correct optimization in this audit was removing the unintended legacy G30 ADC motor timer, not shrinking safety margins.
