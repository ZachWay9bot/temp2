package de.zachway.g30vescbridge;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Arrays;

import javax.crypto.Cipher;
import javax.crypto.spec.SecretKeySpec;

final class NinebotCrypto {
    static final int DEV_ESC = 0x20;
    static final int DEV_BLE = 0x21;
    static final int DEV_PHONE = 0x3E;

    static final int CMD_INIT = 0x5B;
    static final int CMD_PING = 0x5C;
    static final int CMD_PAIR = 0x5D;

    private static final byte[] FW_DATA = new byte[] {
            (byte)0x97, (byte)0xCF, (byte)0xB8, 0x02,
            (byte)0x84, 0x41, 0x43, (byte)0xDE,
            0x56, 0x00, 0x2B, 0x3B,
            0x34, 0x78, 0x0A, 0x5D
    };

    static final class Packet {
        final int src;
        final int dst;
        final int cmd;
        final int arg;
        final byte[] payload;

        Packet(int src, int dst, int cmd, int arg, byte[] payload) {
            this.src = src;
            this.dst = dst;
            this.cmd = cmd;
            this.arg = arg;
            this.payload = payload;
        }
    }

    private final byte[] scooterName16 = new byte[16];
    private final byte[] randomBleData = new byte[16];
    private final byte[] randomAppData = new byte[16];
    private final byte[] scooterSerial = new byte[14];
    private byte[] shaKey = new byte[16];

    private long msgIt;
    private boolean haveInitData;
    private boolean haveAppKey;

    synchronized void reset(String advertisedName) {
        Arrays.fill(scooterName16, (byte)0);
        Arrays.fill(randomBleData, (byte)0);
        Arrays.fill(randomAppData, (byte)0);
        Arrays.fill(scooterSerial, (byte)0);

        byte[] n = advertisedName == null
                ? new byte[0]
                : advertisedName.getBytes(StandardCharsets.UTF_8);
        System.arraycopy(n, 0, scooterName16, 0, Math.min(16, n.length));

        shaKey = sha1Concat(scooterName16, FW_DATA);
        msgIt = 0;
        haveInitData = false;
        haveAppKey = false;
    }

    synchronized boolean hasInitData() {
        return haveInitData;
    }

    synchronized byte[] getSerial() {
        return scooterSerial.clone();
    }

    synchronized String serialHex() {
        StringBuilder sb = new StringBuilder();
        for (byte b : scooterSerial) sb.append(String.format("%02x", b & 0xFF));
        return sb.toString();
    }

    synchronized void generateAppKey() {
        new SecureRandom().nextBytes(randomAppData);
        haveAppKey = true;
    }

    synchronized void setAppKey(byte[] key16) {
        if (key16 == null || key16.length != 16) {
            throw new IllegalArgumentException("App key must be 16 bytes");
        }
        System.arraycopy(key16, 0, randomAppData, 0, 16);
        haveAppKey = true;
    }

    synchronized byte[] getAppKey() {
        return randomAppData.clone();
    }

    synchronized void switchToBoundAppKey() {
        if (!haveAppKey || !haveInitData) {
            throw new IllegalStateException("No app key or BLE init data");
        }
        shaKey = sha1Concat(randomAppData, randomBleData);
    }

    static byte[] buildPlain(int src, int dst, int cmd, int arg, byte[] payload) {
        int n = payload == null ? 0 : payload.length;
        if (n > 242) throw new IllegalArgumentException("Ninebot payload too long");
        byte[] p = new byte[7 + n];
        p[0] = 0x5A;
        p[1] = (byte)0xA5;
        p[2] = (byte)n;
        p[3] = (byte)src;
        p[4] = (byte)dst;
        p[5] = (byte)cmd;
        p[6] = (byte)arg;
        if (n > 0) System.arraycopy(payload, 0, p, 7, n);
        return p;
    }

    synchronized byte[] encryptPlain(byte[] plain) {
        if (plain == null || plain.length < 7) return null;

        final int payloadLen = plain.length - 3;
        byte[] out = new byte[plain.length + 6];
        out[0] = plain[0];
        out[1] = plain[1];
        out[2] = plain[2];

        if (msgIt == 0) {
            byte[] crc = crcFirst(plain, 3, payloadLen);
            byte[] crypt = cryptoFirst(plain, 3, payloadLen);
            if (crypt == null) return null;
            System.arraycopy(crypt, 0, out, 3, crypt.length);

            int i = payloadLen + 3;
            out[i] = 0;
            out[i + 1] = 0;
            out[i + 2] = crc[0];
            out[i + 3] = crc[1];
            out[i + 4] = 0;
            out[i + 5] = 0;
            msgIt++;
        } else {
            msgIt++;
            byte[] crc = crcNext(plain, msgIt);
            byte[] crypt = cryptoNext(plain, 3, payloadLen, msgIt);
            if (crc == null || crypt == null) return null;
            System.arraycopy(crypt, 0, out, 3, crypt.length);

            int i = payloadLen + 3;
            System.arraycopy(crc, 0, out, i, 4);
            out[i + 4] = (byte)((msgIt >> 8) & 0xFF);
            out[i + 5] = (byte)(msgIt & 0xFF);
        }

        return out;
    }

    synchronized Packet decryptFrame(byte[] enc) {
        if (enc == null || enc.length < 13) return null;
        if ((enc[0] & 0xFF) != 0x5A || (enc[1] & 0xFF) != 0xA5) return null;

        final int encryptedBodyLen = enc.length - 9;
        final int plainLen = enc.length - 6;
        byte[] plain = new byte[plainLen];
        plain[0] = enc[0];
        plain[1] = enc[1];
        plain[2] = enc[2];

        long newMsgIt = msgIt;
        int ctrHi = enc[enc.length - 2] & 0xFF;
        int ctrLo = enc[enc.length - 1] & 0xFF;

        if ((newMsgIt & 0x8000L) != 0 && (ctrHi & 0x80) == 0) {
            newMsgIt += 0x10000L;
        }
        newMsgIt = (newMsgIt & 0xFFFF0000L) | ((long)ctrHi << 8) | ctrLo;

        if (newMsgIt == 0) {
            byte[] dec = cryptoFirst(enc, 3, encryptedBodyLen);
            if (dec == null) return null;
            System.arraycopy(dec, 0, plain, 3, dec.length);

            if (plainLen >= 37 &&
                    (plain[3] & 0xFF) == DEV_BLE &&
                    (plain[4] & 0xFF) == DEV_PHONE &&
                    (plain[5] & 0xFF) == CMD_INIT) {
                System.arraycopy(plain, 7, randomBleData, 0, 16);
                System.arraycopy(plain, 23, scooterSerial, 0, 14);
                shaKey = sha1Concat(scooterName16, randomBleData);
                haveInitData = true;
            }
        } else if (newMsgIt > msgIt) {
            byte[] dec = cryptoNext(enc, 3, encryptedBodyLen, newMsgIt);
            if (dec == null) return null;
            System.arraycopy(dec, 0, plain, 3, dec.length);

            if (plainLen >= 7 &&
                    (plain[3] & 0xFF) == DEV_BLE &&
                    (plain[4] & 0xFF) == DEV_PHONE &&
                    (plain[5] & 0xFF) == CMD_PING &&
                    (plain[6] & 0xFF) == 0x01 &&
                    haveAppKey) {
                shaKey = sha1Concat(randomAppData, randomBleData);
            }
            msgIt = newMsgIt;
        } else {
            return null;
        }

        int dataLen = plain[2] & 0xFF;
        if (plain.length < 7 + dataLen) return null;
        return new Packet(
                plain[3] & 0xFF,
                plain[4] & 0xFF,
                plain[5] & 0xFF,
                plain[6] & 0xFF,
                Arrays.copyOfRange(plain, 7, 7 + dataLen));
    }

    private byte[] cryptoFirst(byte[] in, int off, int len) {
        try {
            byte[] stream = aes(shaKey, FW_DATA);
            byte[] out = new byte[len];
            for (int i = 0; i < len; i++) {
                out[i] = (byte)(in[off + i] ^ stream[i & 15]);
            }
            return out;
        } catch (Exception e) {
            return null;
        }
    }

    private byte[] cryptoNext(byte[] in, int off, int len, long counter) {
        try {
            byte[] aesEncData = new byte[16];
            aesEncData[0] = 1;
            putCounter(aesEncData, counter);
            System.arraycopy(randomBleData, 0, aesEncData, 5, 8);

            byte[] out = new byte[len];
            int remaining = len;
            int src = off;
            int dst = 0;
            int blockCounter = 0;
            while (remaining > 0) {
                aesEncData[15] = (byte)(++blockCounter);
                byte[] stream = aes(shaKey, aesEncData);
                int blockLen = Math.min(16, remaining);
                for (int i = 0; i < blockLen; i++) {
                    out[dst + i] = (byte)(in[src + i] ^ stream[i]);
                }
                src += blockLen;
                dst += blockLen;
                remaining -= blockLen;
            }
            return out;
        } catch (Exception e) {
            return null;
        }
    }

    private byte[] crcFirst(byte[] data, int off, int len) {
        int sum = 0;
        for (int i = 0; i < len; i++) sum = (sum + (data[off + i] & 0xFF)) & 0xFFFF;
        int crc = (~sum) & 0xFFFF;
        return new byte[] {(byte)(crc & 0xFF), (byte)((crc >> 8) & 0xFF)};
    }

    private byte[] crcNext(byte[] plain, long counter) {
        if (plain.length < 3) return null;
        try {
            int payloadLen = plain.length - 3;
            byte[] aesEncData = new byte[16];
            aesEncData[0] = 89;
            putCounter(aesEncData, counter);
            System.arraycopy(randomBleData, 0, aesEncData, 5, 8);
            aesEncData[15] = (byte)payloadLen;

            byte[] chain = aes(shaKey, aesEncData);
            byte[] block = chain.clone();
            block[0] = (byte)(plain[0] ^ chain[0]);
            block[1] = (byte)(plain[1] ^ chain[1]);
            block[2] = (byte)(plain[2] ^ chain[2]);
            chain = aes(shaKey, block);

            int remaining = payloadLen;
            int offset = 3;
            while (remaining > 0) {
                int blockLen = Math.min(16, remaining);
                Arrays.fill(block, (byte)0);
                System.arraycopy(plain, offset, block, 0, blockLen);
                for (int i = 0; i < 16; i++) block[i] ^= chain[i];
                chain = aes(shaKey, block);
                offset += blockLen;
                remaining -= blockLen;
            }

            Arrays.fill(aesEncData, (byte)0);
            aesEncData[0] = 1;
            putCounter(aesEncData, counter);
            System.arraycopy(randomBleData, 0, aesEncData, 5, 8);
            byte[] mask = aes(shaKey, aesEncData);

            return new byte[] {
                    (byte)(mask[0] ^ chain[0]),
                    (byte)(mask[1] ^ chain[1]),
                    (byte)(mask[2] ^ chain[2]),
                    (byte)(mask[3] ^ chain[3])
            };
        } catch (Exception e) {
            return null;
        }
    }

    private static void putCounter(byte[] b, long counter) {
        b[1] = (byte)((counter >> 24) & 0xFF);
        b[2] = (byte)((counter >> 16) & 0xFF);
        b[3] = (byte)((counter >> 8) & 0xFF);
        b[4] = (byte)(counter & 0xFF);
    }

    private static byte[] sha1Concat(byte[] a, byte[] b) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-1");
            md.update(a);
            md.update(b);
            return Arrays.copyOf(md.digest(), 16);
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    private static byte[] aes(byte[] key, byte[] block16) throws Exception {
        Cipher c = Cipher.getInstance("AES/ECB/NoPadding");
        c.init(Cipher.ENCRYPT_MODE, new SecretKeySpec(key, "AES"));
        return c.doFinal(block16);
    }
}
