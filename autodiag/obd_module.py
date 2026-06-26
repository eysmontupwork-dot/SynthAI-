import serial
import subprocess
import time
import os
import json
import re
import ast
import operator

# ВИПРАВЛЕНО: MAC читається з .env, а не хардкодиться
OBD_MAC = os.getenv("OBD_MAC", "AA:BB:CC:11:22:33")
OBD_PORT = "/dev/rfcomm0"

# Безпечний набір символів для формул PID
_SAFE_FORMULA_RE = re.compile(r'^[A-D0-9\s\+\-\*\/\(\)\.\,]+$')

# Дозволені бінарні/унарні операції для безпечного обчислення формул PID
_SAFE_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_SAFE_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _safe_eval_formula(formula, variables):
    """Обчислює арифметичну формулу (A/B/C/D, + - * /) без eval(), через AST."""
    tree = ast.parse(formula, mode="eval")

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Name) and node.id in variables:
            return variables[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_BINOPS:
            return _SAFE_BINOPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_UNARYOPS:
            return _SAFE_UNARYOPS[type(node.op)](_eval(node.operand))
        raise ValueError(f"Недопустимий вираз у формулі PID: {ast.dump(node)}")

    return _eval(tree)


def ensure_port():
    # rfcomm connect blocks for the lifetime of the connection by design — Popen
    # without wait() is intentional here, not a leak.
    if not os.path.exists(OBD_PORT):
        subprocess.Popen(
            ["sudo", "rfcomm", "connect", "0", OBD_MAC, "1"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(5)
        if not os.path.exists(OBD_PORT):
            print(f"[OBD] {OBD_PORT} ще не з'явився після rfcomm connect — адаптер може бути не в зоні досяжності")
            return False
        try:
            subprocess.run(["sudo", "chmod", "666", OBD_PORT], timeout=5)
        except subprocess.TimeoutExpired:
            print("[OBD] chmod на rfcomm0 завис (timeout)")
            return False
    return True


class ELMConnection:
    def __init__(self):
        self.ser = None

    def connect(self, protocol='6'):
        if not ensure_port():
            return False
        try:
            self.ser = serial.Serial(OBD_PORT, 38400, timeout=3)
            time.sleep(0.5)
            self._send("ATZ")
            time.sleep(1.5)
            self._send("ATE0")
            self._send("ATL0")
            self._send("ATS0")
            self._send("ATH0")
            self._send(f"ATSP{protocol}")
            time.sleep(0.5)
            resp = self._send("0100")
            if "UNABLE" in resp or "ERROR" in resp or "NO DATA" in resp:
                return False
            return True
        except Exception as e:
            print(f"ELM connect error: {e}")
            return False

    def _send(self, cmd, timeout=3):
        if not self.ser:
            return ""
        try:
            self.ser.reset_input_buffer()
            self.ser.write(f"{cmd}\r".encode())
            time.sleep(0.3)
            end = time.time() + timeout
            response = ""
            while time.time() < end:
                if self.ser.in_waiting:
                    chunk = self.ser.read(self.ser.in_waiting).decode(errors="ignore")
                    response += chunk
                    if ">" in response:
                        break
                time.sleep(0.05)
            return response.replace("\r", "").replace("\n", "").replace(">", "").strip()
        except Exception as e:
            return f"ERROR: {e}"

    def get_voltage(self):
        resp = self._send("ATRV")
        try:
            val = resp.replace("V", "").strip()
            return f"{float(val):.1f} V"
        except:
            return resp

    def get_elm_version(self):
        resp = self._send("ATI")
        return resp.strip()

    def read_dtc(self):
        resp = self._send("03", timeout=5)
        return self._parse_dtc(resp)

    def read_pending_dtc(self):
        resp = self._send("07", timeout=5)
        return self._parse_dtc(resp)

    def clear_dtc(self):
        resp = self._send("04", timeout=5)
        return "44" in resp or "OK" in resp.upper()

    def _parse_dtc(self, raw):
        codes = []
        try:
            clean = raw.replace(" ", "").upper()
            # ВИПРАВЛЕНО: пропускаємо перший байт відповіді (43 або 47 = mode byte)
            # Шукаємо початок даних після заголовку режиму
            if clean.startswith("43") or clean.startswith("47"):
                clean = clean[2:]

            i = 0
            while i < len(clean) - 3:
                byte1 = int(clean[i:i+2], 16)
                byte2 = int(clean[i+2:i+4], 16)
                if byte1 == 0 and byte2 == 0:
                    i += 4
                    continue
                prefix = {0: "P", 1: "C", 2: "B", 3: "U"}[byte1 >> 6]
                code = f"{prefix}{(byte1 & 0x3F):02X}{byte2:02X}"
                if code != "P0000":
                    codes.append(code)
                i += 4
        except Exception as e:
            print(f"[OBD] Помилка парсингу DTC ('{raw}'): {e}")
        return codes

    def read_pid(self, pid_hex):
        cmd = pid_hex.replace(" ", "").upper()
        if cmd.startswith("AT"):
            return self._send(cmd)
        resp = self._send(cmd, timeout=3)
        return resp

    def parse_pid_value(self, pid_info, raw_response):
        try:
            clean = raw_response.replace(" ", "").upper()
            mode = pid_info.get("mode", "01")
            pid = pid_info.get("pid", "").replace(" ", "").upper()
            formula = pid_info.get("formula", "A")

            # ВИПРАВЛЕНО: безпечний eval — тільки дозволені символи
            if not _SAFE_FORMULA_RE.match(formula):
                print(f"[SECURITY] Небезпечна формула відхилена: {formula}")
                return None

            header_len = 2 + len(mode.replace("0", "4", 1)) + len(pid)
            data_start = header_len
            hex_data = clean[data_start:data_start+8]

            if len(hex_data) < 2:
                return None

            A = int(hex_data[0:2], 16) if len(hex_data) >= 2 else 0
            B = int(hex_data[2:4], 16) if len(hex_data) >= 4 else 0
            C = int(hex_data[4:6], 16) if len(hex_data) >= 6 else 0
            D = int(hex_data[6:8], 16) if len(hex_data) >= 8 else 0

            result = _safe_eval_formula(formula, {"A": A, "B": B, "C": C, "D": D})
            return round(result, 2)
        except Exception as e:
            print(f"[OBD] Помилка обчислення PID '{pid_info.get('name', '?')}' (formula='{pid_info.get('formula', '?')}'): {e}")
            return None

    def close(self):
        if self.ser:
            try:
                self.ser.close()
            except Exception as e:
                print(f"[OBD] Помилка закриття serial-порту: {e}")
            self.ser = None


def get_obd_data():
    conn = ELMConnection()
    connected = conn.connect(protocol='6')

    data = {}

    voltage = conn.get_voltage()
    data["voltage"] = {"label": "Напруга бортової мережі", "value": voltage}

    elm_ver = conn.get_elm_version()
    data["elm_version"] = {"label": "Версія ELM", "value": elm_ver}

    if not connected:
        data["dtc_codes"] = []
        data["current_dtc"] = []
        conn.close()
        return data

    from adapters import get_active_adapter
    adapter = get_active_adapter()
    pids = []
    if adapter and adapter.get("capabilities"):
        pids = adapter["capabilities"].get("pids", [])

    for pid_info in pids:
        name = pid_info.get("name", "")
        pid = pid_info.get("pid", "")
        unit = pid_info.get("unit", "")
        mode = pid_info.get("mode", "01")

        if mode == "AT" or pid.startswith("AT"):
            if pid == "ATRV":
                continue
            raw = conn.read_pid(pid)
            data[name] = {"label": name, "value": raw.strip(), "unit": unit}
        else:
            raw = conn.read_pid(pid)
            if "NO DATA" in raw.upper() or "ERROR" in raw.upper() or not raw:
                data[name] = {"label": name, "value": "Не підтримується", "unit": unit}
            else:
                val = conn.parse_pid_value(pid_info, raw)
                if val is not None:
                    data[name] = {"label": name, "value": f"{val}", "unit": unit}
                else:
                    data[name] = {"label": name, "value": raw.strip(), "unit": unit}

    try:
        dtc = conn.read_dtc()
        data["dtc_codes"] = dtc
    except Exception as e:
        print(f"[OBD] Помилка читання DTC: {e}")
        data["dtc_codes"] = []

    try:
        pending = conn.read_pending_dtc()
        data["current_dtc"] = pending
    except Exception as e:
        print(f"[OBD] Помилка читання pending DTC: {e}")
        data["current_dtc"] = []

    conn.close()
    return data


def format_obd_data(data):
    if "error" in data:
        return data["error"]

    lines = ["📊 Дані OBD діагностики:\n"]

    skip = ["dtc_codes", "current_dtc"]
    for key, info in data.items():
        if key in skip:
            continue
        if isinstance(info, dict):
            val = info.get("value", "")
            unit = info.get("unit", "")
            label = info.get("label", key)
            if val and val not in ["Не підтримується", "Помилка зчитування", ""]:
                lines.append(f"• {label}: {val} {unit}".strip())

    dtc = data.get("dtc_codes", [])
    current = data.get("current_dtc", [])

    lines.append("\n🔍 Коди помилок:")
    if dtc:
        for code in dtc:
            lines.append(f"  ⚠️ {code}")
    else:
        lines.append("  ✅ Помилок не виявлено")

    lines.append("\n🔴 Очікуючі помилки:")
    if current:
        for code in current:
            lines.append(f"  ⚠️ {code}")
    else:
        lines.append("  ✅ Немає")

    return "\n".join(lines)


def clear_dtc():
    conn = ELMConnection()
    conn.connect(protocol='6')
    result = conn.clear_dtc()
    conn.close()
    return result
