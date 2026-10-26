# SmartESC v21b temp2 – statischer Kommunikationsaudit (2026-10-26)

Basis: `main` HEAD `3fa979bd2235ac3a4103e5d9e62c466e5de7e20e`; nur Quellcode-Lesekontrolle, kein ARM-Neubuild und kein Hardwaretest.

## Bestätigt
- `g30p/Src/main.c`: USART1 initialisiert, `G30_IoT_RxInit()`, danach `task_comm_init()`, Runtime-Task und Scheduler. ADC und TIM1 werden jedoch vorher initialisiert.
- `g30p/Src/stm32f1xx_it.c`: USART1 IRQ-Priorität 5, RXNE, ORE/NE/FE durch SR/DR-Zugriff quittiert, 256-Byte FIFO (255 Byte nutzbar), Overflow-Flag.
- `g30p/Src/stm32f1xx_hal_msp.c`: PB6/PB7 plus USART1 AFIO-Remap vorhanden.
- `common_files/src/task_cli.c`: jedes empfangene Byte geht an beide Parser; `G30Recovery_AppInit()` nach erfolgreicher `packet_init()`.
- `common_files/src/packet.h`: maximal 512 Byte VESC-Payload, `packet_init()` reserviert dynamisch Paket-State und mindestens 520 Byte RX-Puffer.
- `common_files/src/task_init.c`: `task_comm_init()` bestätigt nur den Task-Handle aus `xTaskCreate`, nicht die spätere `packet_init()`-Erfolgsbedingung.
- G30 UART TX ist blockierender `HAL_UART_Transmit(...,100U)`; Rückgabestatus wird ignoriert.

## Konkrete Risiken / noch nicht nachgewiesen
1. Scheitert `packet_init()` wegen Heapmangel, beendet `task_cli` sich ohne Neustart; VESC und In-App-IAP verstummen zusammen. Das ist ein echter Failure Path, keine hypothetische Parserfunktion.
2. 255 Byte FIFO-Nutzkapazität ist kleiner als ein zulässiger 512-Byte-VESC-Payload. Ein FIFO muss während langer Übertragungen laufend geleert werden; bei blockierenden Antworten oder Motor-/RTOS-Last kann Overflow auftreten. Kein Stresstest belegt.
3. Das Overflow-Flag wird gesetzt, aber hier nicht ausgewertet oder als VESC-Diagnose gemeldet.
4. UART TX Timeout/Fehler werden ignoriert; Antwortverlust kann unsichtbar bleiben.
5. ARM-Build / tatsächlicher Heap, Stack, Flash-Marge und physischer VESC/IAP-Rückweg wurden in diesem Audit NICHT neu verifiziert.

## Nächste Reihenfolge (keine Flashfreigabe)
1. FreeRTOS-Heap, Taskstacks und Linker-Ausgabe prüfen, dann `packet_init()`-Failure Path minimal und ohne Protokolländerung beheben.
2. IRQ-Ringpuffer und TX gegen lange GET_MCCONF/APPCONF-Frames testen.
3. ARM-Build + Hosttests auf dem neuen Commit nachweisen.
4. Erst danach Hardware-Kommunikation auf dem wiederherstellbaren guten 3-Cap und IAP-Lesebefehl; keine ungeprüfte Firmware flashen.

Nicht verändern: Bootloader, IAP-Layout, UART-Pinout, Stromgrenzen, Rekuperation, Security.
