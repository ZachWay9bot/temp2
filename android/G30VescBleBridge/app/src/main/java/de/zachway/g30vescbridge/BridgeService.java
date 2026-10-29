package de.zachway.g30vescbridge;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattDescriptor;
import android.bluetooth.BluetoothGattService;
import android.bluetooth.BluetoothManager;
import android.bluetooth.BluetoothProfile;
import android.bluetooth.BluetoothStatusCodes;
import android.bluetooth.le.BluetoothLeScanner;
import android.bluetooth.le.ScanCallback;
import android.bluetooth.le.ScanFilter;
import android.bluetooth.le.ScanResult;
import android.bluetooth.le.ScanSettings;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.ParcelUuid;
import android.util.Base64;

import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.util.ArrayDeque;
import java.util.Arrays;
import java.util.Collections;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class BridgeService extends Service {
    public static volatile String lastStatus = "Nicht gestartet.";

    private static final int NOTIFICATION_ID = 3020;
    private static final String CHANNEL_ID = "g30_vesc_bridge";
    private static final int TCP_PORT = 65102;

    private static final UUID NUS_SERVICE =
            UUID.fromString("6e400001-b5a3-f393-e0a9-e50e24dcca9e");
    private static final UUID NUS_WRITE =
            UUID.fromString("6e400002-b5a3-f393-e0a9-e50e24dcca9e");
    private static final UUID NUS_NOTIFY =
            UUID.fromString("6e400003-b5a3-f393-e0a9-e50e24dcca9e");
    private static final UUID CCCD =
            UUID.fromString("00002902-0000-1000-8000-00805f9b34fb");

    private static final int TUNNEL_CMD = 0x7E;
    private static final int TUNNEL_ARG = 0x56;
    private static final int TUNNEL_CHUNK = 56;

    private static final int AUTH_IDLE = 0;
    private static final int AUTH_WAIT_INIT = 1;
    private static final int AUTH_WAIT_PING = 2;
    private static final int AUTH_WAIT_PAIR = 3;
    private static final int AUTH_READY = 4;

    private final Handler main = new Handler(Looper.getMainLooper());
    private final ExecutorService io = Executors.newCachedThreadPool();
    private final NinebotCrypto crypto = new NinebotCrypto();
    private final Object txLock = new Object();
    private final ArrayDeque<byte[]> gattTx = new ArrayDeque<>();
    private final Object tcpLock = new Object();

    private BluetoothAdapter adapter;
    private BluetoothLeScanner scanner;
    private BluetoothGatt gatt;
    private BluetoothGattCharacteristic writeChar;
    private BluetoothGattCharacteristic notifyChar;
    private BluetoothDevice targetDevice;
    private String targetName = "";

    private boolean scanning;
    private boolean gattWriting;
    private volatile boolean running;
    private volatile boolean authReady;
    private volatile int authState = AUTH_IDLE;
    private boolean directStored;

    private final byte[] encryptedRx = new byte[512];
    private int encryptedRxLen;
    private int encryptedRxExpected;

    private ServerSocket serverSocket;
    private Socket tcpSocket;
    private OutputStream tcpOut;

    private SharedPreferences prefs;

    @Override public void onCreate() {
        super.onCreate();
        running = true;
        prefs = getSharedPreferences("bridge_keys", MODE_PRIVATE);
        createNotificationChannel();
        startForeground(NOTIFICATION_ID, makeNotification("Startet …"));

        BluetoothManager bm = (BluetoothManager)getSystemService(Context.BLUETOOTH_SERVICE);
        adapter = bm == null ? null : bm.getAdapter();

        startTcpServer();
        main.post(this::startScan);
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (!running) running = true;
        if (gatt == null && !scanning) main.post(this::startScan);
        return START_STICKY;
    }

    @Override public IBinder onBind(Intent intent) {
        return null;
    }

    @Override public void onDestroy() {
        running = false;
        authReady = false;
        authState = AUTH_IDLE;
        stopScan();
        closeGatt();
        closeTcpClient();
        try { if (serverSocket != null) serverSocket.close(); } catch (Exception ignored) {}
        io.shutdownNow();
        stopForeground(STOP_FOREGROUND_REMOVE);
        setStatus("Gestoppt.");
        super.onDestroy();
    }

    private boolean hasBlePermissions() {
        if (Build.VERSION.SDK_INT >= 31) {
            return checkSelfPermission(Manifest.permission.BLUETOOTH_SCAN) == PackageManager.PERMISSION_GRANTED &&
                    checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED;
        }
        return checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED;
    }

    private void startScan() {
        if (!running || scanning || gatt != null) return;
        if (!hasBlePermissions()) {
            setStatus("Bluetooth-Berechtigung fehlt. App öffnen und erlauben.");
            return;
        }
        if (adapter == null || !adapter.isEnabled()) {
            setStatus("Bluetooth ist aus.");
            return;
        }

        scanner = adapter.getBluetoothLeScanner();
        if (scanner == null) {
            setStatus("BLE Scanner nicht verfügbar.");
            return;
        }

        ScanFilter filter = new ScanFilter.Builder()
                .setServiceUuid(new ParcelUuid(NUS_SERVICE))
                .build();
        ScanSettings settings = new ScanSettings.Builder()
                .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
                .build();

        scanning = true;
        setStatus("Suche originales G30-Dashboard …");
        scanner.startScan(Collections.singletonList(filter), settings, scanCallback);

        main.postDelayed(() -> {
            if (scanning) {
                stopScan();
                setStatus("Kein NBScooter gefunden. Neuer Scan …");
                main.postDelayed(this::startScan, 1200);
            }
        }, 12000);
    }

    private void stopScan() {
        if (!scanning) return;
        try {
            if (scanner != null && hasBlePermissions()) scanner.stopScan(scanCallback);
        } catch (Exception ignored) {}
        scanning = false;
    }

    private final ScanCallback scanCallback = new ScanCallback() {
        @Override public void onScanResult(int callbackType, ScanResult result) {
            if (!running || !hasBlePermissions()) return;

            BluetoothDevice d = result.getDevice();
            String name = null;
            try { name = d.getName(); } catch (SecurityException ignored) {}
            if ((name == null || name.isEmpty()) && result.getScanRecord() != null) {
                name = result.getScanRecord().getDeviceName();
            }
            if (name == null || !name.startsWith("NB")) return;

            targetDevice = d;
            targetName = name;
            stopScan();
            setStatus("Gefunden: " + name + " · verbinde BLE …");
            connectGatt();
        }

        @Override public void onScanFailed(int errorCode) {
            scanning = false;
            setStatus("BLE Scanfehler " + errorCode + ". Neuer Versuch …");
            main.postDelayed(BridgeService.this::startScan, 1500);
        }
    };

    private void connectGatt() {
        if (!running || targetDevice == null || !hasBlePermissions()) return;
        closeGatt();
        try {
            gatt = targetDevice.connectGatt(this, false, gattCallback, BluetoothDevice.TRANSPORT_LE);
        } catch (SecurityException e) {
            setStatus("BLE Connect ohne Berechtigung.");
        }
    }

    private final BluetoothGattCallback gattCallback = new BluetoothGattCallback() {
        @Override public void onConnectionStateChange(BluetoothGatt g, int status, int newState) {
            if (newState == BluetoothProfile.STATE_CONNECTED && status == BluetoothGatt.GATT_SUCCESS) {
                setStatus("BLE verbunden · suche NUS …");
                try { g.discoverServices(); } catch (SecurityException ignored) {}
            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                authReady = false;
                authState = AUTH_IDLE;
                directStored = false;
                writeChar = null;
                notifyChar = null;
                synchronized (txLock) {
                    gattTx.clear();
                    gattWriting = false;
                }
                encryptedRxLen = 0;
                encryptedRxExpected = 0;
                setStatus("BLE getrennt · reconnect …");
                try { g.close(); } catch (Exception ignored) {}
                if (gatt == g) gatt = null;
                main.postDelayed(BridgeService.this::startScan, 1200);
            }
        }

        @Override public void onServicesDiscovered(BluetoothGatt g, int status) {
            if (status != BluetoothGatt.GATT_SUCCESS) {
                setStatus("NUS Service-Discovery fehlgeschlagen.");
                safeDisconnect();
                return;
            }

            BluetoothGattService s = g.getService(NUS_SERVICE);
            if (s == null) {
                setStatus("Nordic UART Service fehlt.");
                safeDisconnect();
                return;
            }

            writeChar = s.getCharacteristic(NUS_WRITE);
            notifyChar = s.getCharacteristic(NUS_NOTIFY);
            if (writeChar == null || notifyChar == null) {
                setStatus("NUS Write/Notify fehlt.");
                safeDisconnect();
                return;
            }

            try {
                g.setCharacteristicNotification(notifyChar, true);
                BluetoothGattDescriptor cccd = notifyChar.getDescriptor(CCCD);
                if (cccd == null) {
                    setStatus("NUS CCCD fehlt.");
                    safeDisconnect();
                    return;
                }

                boolean queued;
                if (Build.VERSION.SDK_INT >= 33) {
                    queued = g.writeDescriptor(cccd, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE)
                            == BluetoothStatusCodes.SUCCESS;
                } else {
                    cccd.setValue(BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE);
                    queued = g.writeDescriptor(cccd);
                }
                if (!queued) {
                    setStatus("Notify-Aktivierung konnte nicht gesendet werden.");
                    safeDisconnect();
                }
            } catch (SecurityException e) {
                setStatus("BLE Notify ohne Berechtigung.");
            }
        }

        @Override public void onDescriptorWrite(BluetoothGatt g, BluetoothGattDescriptor descriptor, int status) {
            if (!CCCD.equals(descriptor.getUuid()) || status != BluetoothGatt.GATT_SUCCESS) {
                if (CCCD.equals(descriptor.getUuid())) {
                    setStatus("Notify-Aktivierung fehlgeschlagen: " + status);
                    safeDisconnect();
                }
                return;
            }

            crypto.reset(targetName);
            authReady = false;
            authState = AUTH_WAIT_INIT;
            setStatus("NUS bereit · NinebotCrypto INIT …");
            main.postDelayed(BridgeService.this::sendInit, 300);
        }

        @Override public void onCharacteristicChanged(BluetoothGatt g, BluetoothGattCharacteristic characteristic) {
            if (Build.VERSION.SDK_INT < 33 && NUS_NOTIFY.equals(characteristic.getUuid())) {
                byte[] value = characteristic.getValue();
                if (value != null) feedEncryptedBytes(value);
            }
        }

        @Override public void onCharacteristicChanged(BluetoothGatt g,
                                                      BluetoothGattCharacteristic characteristic,
                                                      byte[] value) {
            if (NUS_NOTIFY.equals(characteristic.getUuid()) && value != null) {
                feedEncryptedBytes(value);
            }
        }

        @Override public void onCharacteristicWrite(BluetoothGatt g,
                                                    BluetoothGattCharacteristic characteristic,
                                                    int status) {
            synchronized (txLock) {
                gattWriting = false;
            }
            if (status != BluetoothGatt.GATT_SUCCESS) {
                setStatus("BLE Write fehlgeschlagen: " + status + " · Session neu.");
                safeDisconnect();
                return;
            }
            writeNextGattChunk();
        }
    };

    private void sendInit() {
        if (authState != AUTH_WAIT_INIT) return;
        setStatus("AUTH 1/3 · INIT 0x5B");
        sendPlain(NinebotCrypto.DEV_BLE, NinebotCrypto.CMD_INIT, 0, null);
    }

    private void sendPing() {
        if (authState != AUTH_WAIT_PING) return;
        setStatus("AUTH 2/3 · 0x5C · beim ersten Pairing Power-Taste kurz drücken");
        sendPlain(NinebotCrypto.DEV_BLE, NinebotCrypto.CMD_PING, 0, crypto.getAppKey());
        main.postDelayed(() -> {
            if (running && authState == AUTH_WAIT_PING && !authReady) sendPing();
        }, 1100);
    }

    private void sendPair() {
        if (authState != AUTH_WAIT_PAIR) return;
        setStatus(directStored ? "AUTH 3/3 · gespeicherter Key · 0x5D" : "AUTH 3/3 · PAIR 0x5D");
        sendPlain(NinebotCrypto.DEV_BLE, NinebotCrypto.CMD_PAIR, 0, crypto.getSerial());
        main.postDelayed(() -> {
            if (running && authState == AUTH_WAIT_PAIR && !authReady) sendPair();
        }, 1600);
    }

    private void handlePlain(NinebotCrypto.Packet p) {
        if (p == null) return;

        if (p.src == NinebotCrypto.DEV_BLE &&
                p.dst == NinebotCrypto.DEV_PHONE &&
                p.cmd == NinebotCrypto.CMD_INIT &&
                crypto.hasInitData()) {

            String serialKey = "key_" + crypto.serialHex();
            String stored = prefs.getString(serialKey, null);

            if (stored != null) {
                try {
                    byte[] key = Base64.decode(stored, Base64.NO_WRAP);
                    if (key.length == 16) {
                        crypto.setAppKey(key);
                        crypto.switchToBoundAppKey();
                        directStored = true;
                        authState = AUTH_WAIT_PAIR;
                        sendPair();
                        return;
                    }
                } catch (Exception ignored) {}
                prefs.edit().remove(serialKey).apply();
            }

            directStored = false;
            crypto.generateAppKey();
            authState = AUTH_WAIT_PING;
            sendPing();
            return;
        }

        if (p.src == NinebotCrypto.DEV_BLE &&
                p.dst == NinebotCrypto.DEV_PHONE &&
                p.cmd == NinebotCrypto.CMD_PING) {
            if (p.arg == 0x01) {
                authState = AUTH_WAIT_PAIR;
                sendPair();
            } else {
                authState = AUTH_WAIT_PING;
                setStatus("Scooter wartet auf Bestätigung · Power-Taste kurz drücken");
            }
            return;
        }

        if (p.src == NinebotCrypto.DEV_BLE &&
                p.dst == NinebotCrypto.DEV_PHONE &&
                p.cmd == NinebotCrypto.CMD_PAIR) {
            if (p.arg == 0x01) {
                authState = AUTH_READY;
                authReady = true;

                if (!directStored) {
                    String serialKey = "key_" + crypto.serialHex();
                    prefs.edit().putString(
                            serialKey,
                            Base64.encodeToString(crypto.getAppKey(), Base64.NO_WRAP)
                    ).apply();
                }

                setStatus("AUTH READY · VESC Tool TCP 127.0.0.1:" + TCP_PORT);
            } else if (directStored) {
                String serialKey = "key_" + crypto.serialHex();
                prefs.edit().remove(serialKey).apply();
                directStored = false;
                setStatus("Gespeicherter Key abgelehnt · neue saubere Pairing-Session …");
                safeDisconnect();
            }
            return;
        }

        if (authReady &&
                p.src == NinebotCrypto.DEV_ESC &&
                p.dst == NinebotCrypto.DEV_PHONE &&
                p.cmd == TUNNEL_CMD &&
                p.arg == TUNNEL_ARG) {
            writeTcp(p.payload);
        }
    }

    private void feedEncryptedBytes(byte[] data) {
        for (byte b : data) {
            int ub = b & 0xFF;

            if (encryptedRxLen == 0) {
                if (ub != 0x5A) continue;
                encryptedRx[encryptedRxLen++] = b;
                continue;
            }
            if (encryptedRxLen == 1) {
                if (ub != 0xA5) {
                    encryptedRxLen = (ub == 0x5A) ? 1 : 0;
                    if (encryptedRxLen == 1) encryptedRx[0] = b;
                    continue;
                }
                encryptedRx[encryptedRxLen++] = b;
                continue;
            }

            if (encryptedRxLen >= encryptedRx.length) {
                encryptedRxLen = 0;
                encryptedRxExpected = 0;
                continue;
            }

            encryptedRx[encryptedRxLen++] = b;

            if (encryptedRxLen == 3) {
                encryptedRxExpected = (encryptedRx[2] & 0xFF) + 13;
                if (encryptedRxExpected < 13 || encryptedRxExpected > encryptedRx.length) {
                    encryptedRxLen = 0;
                    encryptedRxExpected = 0;
                }
            }

            if (encryptedRxExpected > 0 && encryptedRxLen == encryptedRxExpected) {
                byte[] frame = Arrays.copyOf(encryptedRx, encryptedRxExpected);
                encryptedRxLen = 0;
                encryptedRxExpected = 0;
                NinebotCrypto.Packet p = crypto.decryptFrame(frame);
                if (p != null) handlePlain(p);
            }
        }
    }

    private void sendPlain(int dst, int cmd, int arg, byte[] payload) {
        if (gatt == null || writeChar == null) return;
        byte[] plain = NinebotCrypto.buildPlain(NinebotCrypto.DEV_PHONE, dst, cmd, arg, payload);
        byte[] enc = crypto.encryptPlain(plain);
        if (enc == null) {
            setStatus("NinebotCrypto TX fehlgeschlagen.");
            safeDisconnect();
            return;
        }
        queueGattFrame(enc);
    }

    private void queueGattFrame(byte[] enc) {
        synchronized (txLock) {
            for (int off = 0; off < enc.length; off += 20) {
                gattTx.add(Arrays.copyOfRange(enc, off, Math.min(enc.length, off + 20)));
            }
        }
        writeNextGattChunk();
    }

    private void writeNextGattChunk() {
        BluetoothGatt localGatt = gatt;
        BluetoothGattCharacteristic localWrite = writeChar;
        if (localGatt == null || localWrite == null) return;

        byte[] chunk;
        synchronized (txLock) {
            if (gattWriting) return;
            chunk = gattTx.poll();
            if (chunk == null) return;
            gattWriting = true;
        }

        boolean ok = false;
        try {
            if (Build.VERSION.SDK_INT >= 33) {
                ok = localGatt.writeCharacteristic(
                        localWrite,
                        chunk,
                        BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
                ) == BluetoothStatusCodes.SUCCESS;
            } else {
                localWrite.setWriteType(BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT);
                localWrite.setValue(chunk);
                ok = localGatt.writeCharacteristic(localWrite);
            }
        } catch (SecurityException ignored) {}

        if (!ok) {
            synchronized (txLock) { gattWriting = false; }
            setStatus("BLE Write konnte nicht gestartet werden.");
            safeDisconnect();
        }
    }

    private void sendTunnel(byte[] data, int off, int len) {
        int p = off;
        int left = len;
        while (left > 0 && running) {
            while (running && !authReady) {
                try { Thread.sleep(80); } catch (InterruptedException e) { return; }
            }
            if (!running) return;

            int n = Math.min(TUNNEL_CHUNK, left);
            byte[] chunk = Arrays.copyOfRange(data, p, p + n);
            sendPlain(NinebotCrypto.DEV_ESC, TUNNEL_CMD, TUNNEL_ARG, chunk);
            p += n;
            left -= n;
        }
    }

    private void startTcpServer() {
        io.execute(() -> {
            try {
                serverSocket = new ServerSocket();
                serverSocket.setReuseAddress(true);
                serverSocket.bind(new InetSocketAddress(InetAddress.getLoopbackAddress(), TCP_PORT));
                while (running) {
                    Socket s = serverSocket.accept();
                    synchronized (tcpLock) {
                        closeTcpClientLocked();
                        tcpSocket = s;
                        tcpSocket.setTcpNoDelay(true);
                        tcpOut = tcpSocket.getOutputStream();
                    }
                    setStatus(authReady
                            ? "VESC Tool TCP verbunden · BLE Tunnel READY"
                            : "VESC Tool TCP verbunden · warte auf BLE AUTH READY");
                    serviceTcpClient(s);
                }
            } catch (Exception e) {
                if (running) setStatus("TCP Bridge Fehler: " + e.getClass().getSimpleName());
            }
        });
    }

    private void serviceTcpClient(Socket s) {
        try {
            InputStream in = s.getInputStream();
            byte[] buf = new byte[1024];
            while (running && !s.isClosed()) {
                int n = in.read(buf);
                if (n < 0) break;
                if (n == 0) continue;
                sendTunnel(buf, 0, n);
            }
        } catch (Exception ignored) {
        } finally {
            synchronized (tcpLock) {
                if (tcpSocket == s) closeTcpClientLocked();
            }
            if (running) setStatus(authReady
                    ? "AUTH READY · warte auf VESC Tool TCP 127.0.0.1:" + TCP_PORT
                    : "TCP getrennt · BLE/Auth läuft weiter");
        }
    }

    private void writeTcp(byte[] payload) {
        synchronized (tcpLock) {
            if (tcpOut == null) return;
            try {
                tcpOut.write(payload);
                tcpOut.flush();
            } catch (Exception e) {
                closeTcpClientLocked();
            }
        }
    }

    private void closeTcpClient() {
        synchronized (tcpLock) { closeTcpClientLocked(); }
    }

    private void closeTcpClientLocked() {
        try { if (tcpOut != null) tcpOut.close(); } catch (Exception ignored) {}
        try { if (tcpSocket != null) tcpSocket.close(); } catch (Exception ignored) {}
        tcpOut = null;
        tcpSocket = null;
    }

    private void safeDisconnect() {
        BluetoothGatt local = gatt;
        if (local == null) return;
        try {
            if (hasBlePermissions()) local.disconnect();
        } catch (Exception ignored) {}
    }

    private void closeGatt() {
        BluetoothGatt local = gatt;
        gatt = null;
        if (local != null) {
            try {
                if (hasBlePermissions()) local.disconnect();
            } catch (Exception ignored) {}
            try { local.close(); } catch (Exception ignored) {}
        }
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel ch = new NotificationChannel(
                    CHANNEL_ID,
                    "G30 VESC BLE Bridge",
                    NotificationManager.IMPORTANCE_LOW
            );
            getSystemService(NotificationManager.class).createNotificationChannel(ch);
        }
    }

    private Notification makeNotification(String text) {
        Notification.Builder b = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(this, CHANNEL_ID)
                : new Notification.Builder(this);
        return b.setContentTitle("G30 VESC BLE Bridge")
                .setContentText(text)
                .setSmallIcon(android.R.drawable.stat_sys_data_bluetooth)
                .setOngoing(true)
                .build();
    }

    private void setStatus(String s) {
        lastStatus = s;
        try {
            NotificationManager nm = (NotificationManager)getSystemService(NOTIFICATION_SERVICE);
            nm.notify(NOTIFICATION_ID, makeNotification(s));
        } catch (Exception ignored) {}
    }
}
