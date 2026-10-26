# SmartESC v21b – Übergabe 2026-10-26

**Einziges Entwicklungsrepository:** https://github.com/ZachWay9bot/temp2 (Branch `main`).
**Historischer gepinnter Quell-Snapshot:** `ZachWay9bot/SmartESC_STM32_v21b` Commit `533e64412dca30adfcb02f8f54a8ea82e6573f4c`. Nicht mehr dort entwickeln.
**Geprüfter temp2-Migrations-HEAD:** `ab4f7a6a8e3d19005de293f26eca70fee2a142af`. Der Zielbaum enthält ~2220 Blob-Dateien inklusive vollständigem `g30p`, `common_files`, `tools/tests`, `firmware/v0.8.7`, `legacy` und `docs`. Erster Importversuch scheiterte an GitHub-workflows-Permissions; ein späterer Import ist vorhanden. Nicht als vollständig SHA-für-SHA verglichen ausgeben.

## Verbindliches Ziel
Ninebot G30 3-Cap STM32F103 mit VESC Tool 6.06 über **IoT USART1 PB6/PB7, 115200 8N1**, Motor-Autodetect, sensorless FOC und FWD/REV/Pfeiltasten wie VESC. Dashboard USART2 PA2, BMS USART3. Nur guter 3-Cap mit ST-Link-Notrückweg testen, **niemals ungeprüften Build auf vergossenen XBOT**. Kein eigenmächtiger Bootloader/IAP/Flashlayout/Stromlimit/Brems/Rekuperations-/Security-Umbau. ST-Link nur für Rollback, nicht für normale Diagnose.

## Historische funktionierende Referenzen
`XBOT_VESC_BRIDGE_v0.4.7_SINGLE_DRIVE_PATH.zip`, `XBOT_VESC_BRIDGE_v0.4.8_FO76_DRIVE_PROFILE.zip`, frühere v0.4.2/FO76-Autodetect-Tests und v0.8.7. Ein USART1-Empfang liefert jedes Byte an **Ninebot und VESC Parser**. v0.4.7 Fahrstart ALIGN→OPEN→BLEND→CLOSED; VESC-Pfeiltasten via gemeinsamen SET_DUTY/SET_CURRENT-Pfad. Nachweis früheren Autodetects, aber v0.4.8-Fahrprofil nicht automatisch dauerhaft fahrfertig.

## Gescheiterter Hardwarestand BENCH-314
Nach Flash: Dauergrün, weder VESC Tool noch NinebotIAPFlasher erreichbar. Nicht erneut installieren; Bootloaderdefekt nicht bewiesen. SWD-Diagnose wurde vom Nutzer beendet. Rückweg des guten 3-Cap historisch ST-Link→DRV 1.8.7→IAP→DRV 1.2.6.

## Quellcode im übernommenen temp2
- `g30p/Src/main.c`: MCU-Init, UART/Comm vor Motor-Runtime, geprüfte Task-Erzeugung, Scheduler.
- `g30p/Src/stm32f1xx_it.c`: USART1 RXNE ISR mit 256-Byte-Ringpuffer, ein Verbraucher `G30_IoT_GetByte()`.
- `common_files/src/task_cli.c`: gemeinsamer UART-Stream an `G30Recovery_AppPushByte()` und `packet_process_byte()`; `G30Recovery_AppInit()` vor RX.
- `common_files/src/g30_recovery_iap.c`: Ninebot-Paketparser, IAP 0x01 READ, 0x07 BEGIN, 0x08 WRITE, 0x09 FINALIZE, 0x0A RESET, 0x0B ACK.
- `common_files/src/VescCommand.c`, `VescToSTM.c`, `g30_sensorless*.c`: G30-VESC-Motorsteuerung/Observer; noch nicht hardwarebestätigt.
- IAP-Memory im Code: App 0x08001000; Staging 0x0800E800 bis 0x0801C000 exklusiv; Control 0x0801F800. **Nicht verändern ohne Freigabe.**
- `docs/FO76_V048_DUAL_PROTOCOL_RESTORE_20261026.md`, `tools/tests/` und ursprüngliche Workflows unter `source-ci-workflows/`.

## CI- und Release-Wahrheit
Zum Quellcommit `533e6441`: G30 Hosttests PASS (Run 40386798295); Recovery-Audit PASS (40386798166); letzter ARM-Build (40386798242) wurde beim letzten Nachschauen noch ausgeführt; früherer IRQ-UART-ARM-Build (40386651600) PASS. **Keine dieser Prüfungen beweist Hardware-IAP oder VESC Tool.** Keine Flashfreigabe.

## Nächste Schritte in genau dieser Reihenfolge
1. Nur in `temp2`: Build und Tests für Ziel-HEAD frisch verifizieren, Flash/RAM/Heap-Marge, `packet_init()`-Fehlpfad, USART1 ISR/Ringpuffer.
2. VESC FW_VERSION, GET_VALUES, MCCONF/APPCONF einschließlich langer Pakete und Ninebot-Parser parallel verifizieren.
3. IoT-IAP inklusive ACKs, Adresse/TEA/CRC, sicherem Rückweg prüfen, ohne Bootloader/Flashlayout und Motorlimits eigenmächtig zu ändern. PWM-off-Status ist kein atomarer Stillstandsschutz.
4. Nachweislich funktionierenden FO76/v0.4.2-Autodetect reproduzieren, dann gemeinsamen FWD/REV sensorless FOC-Fahrpfad.
5. Hardware-Reihenfolge: VESC Connect → Values/Config → Ninebot-IAP-Lesen → Detect All → FWD → REV → bestätigter IAP-Rückweg. Nur guter 3-Cap.

**Keine Behauptung „fahrbereit“, bis die Hardware es bestätigt.**
