# HF4 native dashboard link R1

Base: `6c15e44c5f60b33a194c38d2a994b39c872a163d`, frozen R3I15HF4.
Build: `G30D-HF4-DASH-LINK-R1`.

This candidate diagnoses native G30 Yellowwire communication. It does not turn
dashboard throttle or brake bytes into motor commands. The existing HF4 VESC
command and motor-control sources remain byte-identical. VESC commands over
USART1 retain their original behavior; this is not a global motor inhibit.

## Behavior

- USART2/PA2, 115200 8N1, half duplex, existing open-drain pin configuration.
- A dedicated 128-byte circular RX DMA buffer is polled once per RTOS tick.
- Native `5A A5 LEN SRC DST CMD ARG DATA CHECKSUM_LE` frames are parsed.
- `21 -> 20 CMD64 ARG00` carries raw inputs and requests a six-byte status ACK.
- `21 -> 20 CMD65 ARG00` carries raw inputs and has no reply.
- Throttle/brake remain unscaled raw bytes. No fixed 40/197 or 41/181 mapping.
- Status: mode, battery, light level 0/100, beep=0, speed, fault.
- TX is bounded polling with the HAL UART transmission-complete check, no
  TX-DMA, no arbitrary gState writes, no RTOS delay before transmission.
- Read-only `g30dash` terminal diagnostics on the existing USART1/COM9 path.
- Task allocation failure and RX/TX status are visible in diagnostics.

Not included: R3I16 mode changes, R3I17 detect, R3I18/R3I19 drive path, R3I20 BLE
tunnel, dashboard motor drive, or new power/button policy. Metadata/version
variant work follows after the native status exchange has passed on hardware.

## Validation

The host test uses recorded native dashboard frames and the exact recorded
ESC status response. It rejects single-bit corruption, wrong routing, truncated
frames, and checks the maximum payload under address/undefined sanitizers.
`DASH_R1_CHANGE_AUDIT.json` asserts that all original files except the explicit
application/terminal/identity/project hooks remain unchanged.

The ARM build and image checks are CI validation, not a physical bus result.
Hardware acceptance is still required: compare `g30dash` snapshots against the
existing C3 logger, raw input values at rest and during deliberate lever travel,
and valid CMD64 response counts/checksums. Keep the power stage disconnected;
use the separately verified 5-V logic-only bench arrangement for this diagnosis.

Do not apply a motor command from these raw inputs until measured throttle
and brake endpoints, direction, neutral, and the boot behavior are established.
