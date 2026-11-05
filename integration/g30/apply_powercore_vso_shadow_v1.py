#!/usr/bin/env python3
"""Apply read-only SESC-VSO shadow integration to reconstructed PowerCore6500 FINAL V1."""

from pathlib import Path
import shutil
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "SOURCE_KOXX3")
HERE = Path(__file__).resolve().parents[2]

if not (ROOT / "common_files/src/mc_tasks.c").exists():
    raise SystemExit(f"Not a reconstructed SESC tree: {ROOT}")

dst = ROOT / "g30p/vso"
dst.mkdir(parents=True, exist_ok=True)

copy_map = [
    ("include/sesc_vso_types.h", "sesc_vso_types.h"),
    ("include/sesc_vso_math.h", "sesc_vso_math.h"),
    ("include/vesc_observer_port.h", "vesc_observer_port.h"),
    ("include/vesc_resistance_observer.h", "vesc_resistance_observer.h"),
    ("src/vesc_observer.c", "vesc_observer.c"),
    ("src/vesc_resistance_observer.c", "vesc_resistance_observer.c"),
    ("integration/g30/sesc_vso_math_g30.c", "sesc_vso_math_g30.c"),
    ("integration/g30/sesc_vso_shadow_g30.h", "sesc_vso_shadow_g30.h"),
    ("integration/g30/sesc_vso_shadow_g30.c", "sesc_vso_shadow_g30.c"),
]

for src_rel, dst_name in copy_map:
    shutil.copy2(HERE / src_rel, dst / dst_name)

# Read-only hook in the FOC loop.
mc = ROOT / "common_files/src/mc_tasks.c"
text = mc.read_text()

inc = '#include "../../g30p/vso/sesc_vso_shadow_g30.h"\n'
if inc not in text:
    # Insert after the last local include near the top without relying on a
    # specific historical include order.
    pos = text.find("\n\n", text.find("#include"))
    if pos < 0:
        raise SystemExit("Could not find mc_tasks include block")
    text = text[:pos+1] + inc + text[pos+1:]

anchor = "FW_DataProcess(pFW[M1],Vqd,Iqd);"
hook = """FW_DataProcess(pFW[M1],Vqd,Iqd);
  {
    const uint32_t vso_vbus_mv =
        (uint32_t)(((uint32_t)VBS_GetAvBusVoltage_d(pMCT[M1]->pBusVoltageSensor) * 1000u) /
                   (uint32_t)BATTERY_VOLTAGE_GAIN);
    g30_vso_shadow_step(Ialphabeta.alpha, Ialphabeta.beta,
                        Valphabeta.alpha, Valphabeta.beta,
                        Iqd.d, Iqd.q, vso_vbus_mv, hElAngle);
  }"""
if "g30_vso_shadow_step(" not in text:
    if anchor not in text:
        raise SystemExit("FOC telemetry anchor not found")
    text = text.replace(anchor, hook, 1)


# Allocate context only from normal task/init context.
ti = ROOT / "common_files/src/task_init.c"
text = ti.read_text()
if inc not in text:
    pos = text.find("\n\n", text.find("#include"))
    if pos < 0:
        raise SystemExit("Could not find task_init include block")
    text = text[:pos+1] + inc + text[pos+1:]

anchor = """void task_runtime_init(void){
	app_adc_init_timer();
"""
repl = """void task_runtime_init(void){
	app_adc_init_timer();
	(void)g30_vso_shadow_init();
"""
if "g30_vso_shadow_init();" not in text:
    if anchor not in text:
        raise SystemExit("task_runtime_init anchor not found")
    text = text.replace(anchor, repl, 1)
ti.write_text(text)

# Terminal diagnostics, integer-only to avoid dragging float formatting into CLI.
te = ROOT / "common_files/src/terminal.c"
text = te.read_text()
if inc not in text:
    pos = text.find("\n\n", text.find("#include"))
    if pos < 0:
        raise SystemExit("Could not find terminal include block")
    text = text[:pos+1] + inc + text[pos+1:]

anchor = """	}else if (strcmp(argv[0], "limits") == 0){"""
cmd = r'''	}else if (strcmp(argv[0], "vso_shadow") == 0){
		if(argc == 2 && strcmp(argv[1], "reset") == 0){
			g30_vso_shadow_reset_diag();
			commands_printf(phandle, "VSO shadow diag reset\n");
		}else{
			g30_vso_shadow_diag_t d = g30_vso_shadow_get_diag();
			commands_printf(phandle,
				"VSO init=%u heap=%u fast=%lu obs=%lu r=%lu nf=%lu cyc=%lu/%lu "
				"ctrl=%d obsAng=%d err=%d maxErr=%u erpm=%ld lambda=%luuWb R=%lumOhm\n",
				(unsigned)d.initialized, (unsigned)d.heap_alloc_ok,
				(unsigned long)d.fast_calls, (unsigned long)d.observer_updates,
				(unsigned long)d.resistance_updates, (unsigned long)d.nonfinite_events,
				(unsigned long)d.cycles_last, (unsigned long)d.cycles_max,
				(int)d.control_angle_s16, (int)d.observer_angle_s16,
				(int)d.phase_error_s16, (unsigned)d.phase_error_abs_max_s16,
				(long)d.pll_erpm, (unsigned long)d.lambda_uwb,
				(unsigned long)d.resistance_mohm);
		}
''' + anchor

if 'strcmp(argv[0], "vso_shadow")' not in text:
    if anchor not in text:
        raise SystemExit("terminal command anchor not found")
    text = text.replace(anchor, cmd, 1)
te.write_text(text)

# Unique child build identity. Do not touch the accepted freeze.
de = ROOT / "common_files/src/defines.h"
text = de.read_text()
old = "SESC-DRV126-POWERCORE6500-FINAL-V1"
new = "SESC-DRV126-POWERCORE6500-VSO-SHADOW-V1"
if new not in text:
    if old not in text:
        raise SystemExit("PowerCore6500 FINAL V1 build id not found")
    text = text.replace(old, new)
de.write_text(text)

# Safety audit: the adapter itself must have no control authority.
shadow = (dst / "sesc_vso_shadow_g30.c").read_text()
for forbidden in (
    "PWMC_SetPhaseVoltage",
    "MCI_SetCurrentReferences",
    "PWMC_SwitchOnPWM",
    "PWMC_SwitchOffPWM",
    "LL_TIM_EnableAllOutputs",
    "LL_TIM_DisableAllOutputs",
):
    if forbidden in shadow:
        raise SystemExit(f"Forbidden control symbol in shadow adapter: {forbidden}")

print("SESC_VSO_SHADOW_V1_APPLIED")
