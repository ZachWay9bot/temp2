# G30 VESC BLE Bridge

Companion Android bridge for SmartESC R3I20.

Path:
VESC Tool mobile TCP 127.0.0.1:65102 -> this app -> NinebotCrypto -> stock G30 Nordic UART BLE -> stock dashboard -> Yellowwire -> SmartESC R3I20 CMD 0x7E/ARG 0x56 tunnel -> existing VESC parser.

The first successful pairing can require one short scooter power-button confirmation. The accepted generated client key is then stored for direct 0x5D reconnect on later sessions.

The app does not replace or patch VESC Tool. In VESC Tool select TCP and connect to 127.0.0.1 port 65102 only after this bridge reports READY.
