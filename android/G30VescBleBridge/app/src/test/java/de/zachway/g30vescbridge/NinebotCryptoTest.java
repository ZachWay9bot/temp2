package de.zachway.g30vescbridge;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;

import org.junit.Test;

public class NinebotCryptoTest {
    @Test public void initEncryptionMatchesRealG30Trace() {
        NinebotCrypto c = new NinebotCrypto();
        c.reset("NBScooter2088");
        byte[] plain = NinebotCrypto.buildPlain(
                NinebotCrypto.DEV_PHONE,
                NinebotCrypto.DEV_BLE,
                NinebotCrypto.CMD_INIT,
                0,
                null
        );
        byte[] enc = c.encryptPlain(plain);
        assertArrayEquals(
                hex("5A A5 00 66 EE F3 7C 00 00 45 FF 00 00"),
                enc
        );
    }

    @Test public void initReplyDecryptsExactlyLikeRealHardwareTrace() {
        NinebotCrypto c = new NinebotCrypto();
        c.reset("NBScooter2088");

        // Sending INIT advances the local iterator exactly like the real session.
        c.encryptPlain(NinebotCrypto.buildPlain(
                NinebotCrypto.DEV_PHONE,
                NinebotCrypto.DEV_BLE,
                NinebotCrypto.CMD_INIT,
                0,
                null
        ));

        byte[] rx = hex(
                "5A A5 1E 79 F1 F3 7D C0 48 B5 0B CE 11 C1 E4 A1 A4 C7 7B E3 " +
                "F1 8B 21 58 CB 13 AB FD D4 F4 D6 B8 B1 51 06 60 F8 00 00 4F F4 00 00"
        );
        NinebotCrypto.Packet p = c.decryptFrame(rx);
        assertNotNull(p);
        assertEquals(0x21, p.src);
        assertEquals(0x3E, p.dst);
        assertEquals(0x5B, p.cmd);
        assertEquals(0x01, p.arg);
        assertArrayEquals(
                hex("D6 B7 E1 F3 77 F4 04 03 28 56 A3 49 BB 3E 23 5D " +
                    "4E 34 47 53 44 31 31 31 31 43 35 34 38 37"),
                p.payload
        );
    }

    private static byte[] hex(String s) {
        String x = s.replaceAll("\\s+", "");
        byte[] out = new byte[x.length() / 2];
        for (int i = 0; i < out.length; i++) {
            out[i] = (byte)Integer.parseInt(x.substring(i * 2, i * 2 + 2), 16);
        }
        return out;
    }
}
