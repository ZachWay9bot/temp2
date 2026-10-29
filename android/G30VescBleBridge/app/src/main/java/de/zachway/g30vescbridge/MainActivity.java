package de.zachway.g30vescbridge;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.List;

public class MainActivity extends Activity {
    private static final int REQ_PERMS = 120;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private TextView statusView;

    private final Runnable statusPoll = new Runnable() {
        @Override public void run() {
            if (statusView != null) statusView.setText(BridgeService.lastStatus);
            handler.postDelayed(this, 400);
        }
    };

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(36, 36, 36, 36);

        TextView title = new TextView(this);
        title.setText("G30 VESC BLE Bridge");
        title.setTextSize(24f);
        title.setGravity(Gravity.CENTER_HORIZONTAL);
        root.addView(title, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT));

        TextView info = new TextView(this);
        info.setText(
                "\nSmartESC R3I20 + originales G30-Dashboard\n\n" +
                "1. Bridge starten.\n" +
                "2. Auf AUTH READY warten. Beim ersten Pairing ggf. Power-Taste am Scooter einmal kurz drücken.\n" +
                "3. VESC Tool öffnen → TCP.\n" +
                "4. Host 127.0.0.1, Port 65102.\n\n" +
                "VESC Tool bleibt unverändert. Die App macht nur NinebotCrypto + Tunnel."
        );
        info.setTextSize(16f);
        root.addView(info);

        statusView = new TextView(this);
        statusView.setTextSize(16f);
        statusView.setPadding(0, 30, 0, 30);
        statusView.setText(BridgeService.lastStatus);
        root.addView(statusView);

        Button start = new Button(this);
        start.setText("Bridge starten");
        start.setOnClickListener(v -> startBridgeWithPermissions());
        root.addView(start);

        Button stop = new Button(this);
        stop.setText("Bridge stoppen");
        stop.setOnClickListener(v -> {
            stopService(new Intent(this, BridgeService.class));
            BridgeService.lastStatus = "Gestoppt.";
        });
        root.addView(stop);

        ScrollView scroll = new ScrollView(this);
        scroll.addView(root);
        setContentView(scroll);
    }

    private void startBridgeWithPermissions() {
        List<String> missing = new ArrayList<>();

        if (Build.VERSION.SDK_INT >= 31) {
            if (checkSelfPermission(Manifest.permission.BLUETOOTH_SCAN) != PackageManager.PERMISSION_GRANTED) {
                missing.add(Manifest.permission.BLUETOOTH_SCAN);
            }
            if (checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
                missing.add(Manifest.permission.BLUETOOTH_CONNECT);
            }
        } else {
            if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
                missing.add(Manifest.permission.ACCESS_FINE_LOCATION);
            }
        }

        if (Build.VERSION.SDK_INT >= 33 &&
                checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            missing.add(Manifest.permission.POST_NOTIFICATIONS);
        }

        if (!missing.isEmpty()) {
            requestPermissions(missing.toArray(new String[0]), REQ_PERMS);
            return;
        }

        startBridge();
    }

    private void startBridge() {
        Intent i = new Intent(this, BridgeService.class);
        if (Build.VERSION.SDK_INT >= 26) startForegroundService(i);
        else startService(i);
        BridgeService.lastStatus = "Bridge startet …";
    }

    @Override public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != REQ_PERMS) return;
        for (int r : grantResults) {
            if (r != PackageManager.PERMISSION_GRANTED) {
                BridgeService.lastStatus = "Bluetooth-Berechtigung fehlt.";
                return;
            }
        }
        startBridge();
    }

    @Override protected void onResume() {
        super.onResume();
        handler.post(statusPoll);
    }

    @Override protected void onPause() {
        super.onPause();
        handler.removeCallbacks(statusPoll);
    }
}
