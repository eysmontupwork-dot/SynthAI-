from flask import Flask, render_template, request, jsonify, Response, stream_with_context
import ollama
import json
import os
import socket
import threading
import uuid
import datetime
from pathlib import Path
from google import genai
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
gemini_client = None
if GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# --- Захист API від несанкціонованого доступу в локальній мережі ---
API_TOKEN = os.getenv("API_TOKEN", "")
if not API_TOKEN:
    print("[WARNING] API_TOKEN не встановлено в .env — API-роути не захищені!")

# Сторінки (HTML-шаблони), які можна завантажити без токена — самі по собі не містять даних
_PUBLIC_PATHS = {"/", "/dashboard", "/adapters-page", "/cars"}


@app.before_request
def _require_api_token():
    if not API_TOKEN:
        return  # auth вимкнено, якщо токен не налаштований
    if request.path in _PUBLIC_PATHS or request.path.startswith("/static/"):
        return
    token = request.headers.get("X-API-Token", "")
    if token != API_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

SYSTEM_PROMPT = {
    "role": "system",
    "content": '''Ти - IRIS, діагностичний асистент стенду SynthAI.

ХТО ТИ:
- Розумний асистент для автомобільної діагностики
- Маєш доступ до OBD адаптера і можеш читати дані з авто
- Допомагаєш оператору розібратись з проблемами автомобіля

СТИЛЬ СПІЛКУВАННЯ:
- Спілкуйся природно і дружньо
- Відповідай коротко і по суті
- Можеш підтримати розмову на автомобільні теми
- Якщо питання не стосується авто — відповідай коротко і перенаправляй до діагностики
- Тільки правильна українська мова
- Не згадуй яку модель AI використовуєш

OBD ДІАГНОСТИКА:
- Якщо оператор просить дані з авто а OBD не підключено — нагадай підключити адаптер
- Якщо є дані OBD — аналізуй їх і пояснюй зрозуміло
- Коди помилок пояснюй простою мовою — що означає і що робити
- Якщо температура або інші показники критичні — попереджай

НЕ РОБИ:
- Не вигадуй дані яких немає
- Не кажи що ти AI або яку модель використовуєш'''
}

BASE_DIR = Path(__file__).resolve().parent

HISTORY_DIR = BASE_DIR / "history"
HISTORY_DIR.mkdir(exist_ok=True)

CARS_FILE = BASE_DIR / "data" / "cars.json"
CARS_FILE.parent.mkdir(exist_ok=True)
if not CARS_FILE.exists():
    CARS_FILE.write_text("[]", encoding="utf-8")

# --- Потокобезпечне сховище сесій ---
_sessions_lock = threading.Lock()
_session_histories = {}  # {session_id: [messages]}
_current_session_id = str(uuid.uuid4())[:8]


def get_current_session_id():
    with _sessions_lock:
        return _current_session_id


def set_current_session_id(session_id):
    global _current_session_id
    with _sessions_lock:
        _current_session_id = session_id


def get_history(session_id):
    with _sessions_lock:
        if session_id not in _session_histories:
            _session_histories[session_id] = [SYSTEM_PROMPT]
        return list(_session_histories[session_id])


def append_to_history(session_id, message):
    with _sessions_lock:
        if session_id not in _session_histories:
            _session_histories[session_id] = [SYSTEM_PROMPT]
        _session_histories[session_id].append(message)


def reset_history(session_id):
    with _sessions_lock:
        _session_histories[session_id] = [SYSTEM_PROMPT]


def save_session(session_id):
    history = get_history(session_id)
    if len(history) <= 1:
        return
    session_file = HISTORY_DIR / f"{session_id}.json"
    with open(session_file, "w", encoding="utf-8") as f:
        json.dump({
            "id": session_id,
            "date": datetime.datetime.now().strftime("%d.%m.%Y %H:%M"),
            "messages": history[1:]
        }, f, ensure_ascii=False, indent=2)


def load_sessions():
    sessions = []
    for f in sorted(HISTORY_DIR.glob("*.json"), reverse=True)[:20]:
        try:
            with open(f, encoding="utf-8") as fp:
                data = json.load(fp)
                first_msg = next((m["content"][:50] for m in data["messages"] if m["role"] == "user"), "Діалог")
                sessions.append({"id": data["id"], "date": data["date"], "preview": first_msg})
        except:
            pass
    return sessions


def is_online():
    try:
        socket.setdefaulttimeout(5)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except:
        return False


def run_auto_diagnosis(user_input):
    try:
        from obd_module import get_obd_data, format_obd_data
        data = get_obd_data()
        return format_obd_data(data)
    except Exception as e:
        return f"Помилка OBD діагностики: {e}"


def run_specific_pid(pid_name: str):
    try:
        from obd_module import ELMConnection
        from adapters import get_active_adapter

        adapter = get_active_adapter()
        if not adapter or not adapter.get("capabilities"):
            return "Адаптер не налаштовано або не проаналізовано"

        pids = adapter["capabilities"].get("pids", [])
        pid_info = next((p for p in pids if pid_name.lower() in p["name"].lower()), None)

        if not pid_info:
            return f"PID для '{pid_name}' не знайдено в базі адаптера"

        conn = ELMConnection()
        conn.connect(protocol='6')
        raw = conn.read_pid(pid_info["pid"])
        val = conn.parse_pid_value(pid_info, raw)
        conn.close()

        if val is not None:
            return f"{pid_info['name']}: {val} {pid_info.get('unit','')}"
        return f"{pid_info['name']}: {raw.strip()}"
    except Exception as e:
        return f"Помилка читання PID: {e}"


def run_read_dtc():
    try:
        from obd_module import ELMConnection
        conn = ELMConnection()
        conn.connect(protocol='6')
        dtc = conn.read_dtc()
        pending = conn.read_pending_dtc()
        conn.close()

        lines = []
        if dtc:
            lines.append(f"⚠️ Підтверджені помилки: {', '.join(dtc)}")
        else:
            lines.append("✅ Підтверджених помилок немає")

        if pending:
            lines.append(f"⚠️ Очікуючі помилки: {', '.join(pending)}")
        else:
            lines.append("✅ Очікуючих помилок немає")

        return "\n".join(lines)
    except Exception as e:
        return f"Помилка читання помилок: {e}"


def run_clear_dtc():
    try:
        from obd_module import ELMConnection
        conn = ELMConnection()
        conn.connect(protocol='6')
        result = conn.clear_dtc()
        conn.close()
        return "✅ Помилки очищено" if result else "❌ Не вдалось очистити помилки"
    except Exception as e:
        return f"Помилка очищення: {e}"


def detect_obd_command(text: str):
    t = text.lower()

    if any(w in t for w in ["почитай помилки", "прочитай помилки", "які помилки", "коди помилок", "перевір помилки", "dtc"]):
        return "read_dtc"

    if any(w in t for w in ["очисти помилки", "видали помилки", "скинь помилки", "очистити помилки"]):
        return "clear_dtc"

    if any(w in t for w in ["проведи діагностику", "скануй", "перевір авто", "що з авто", "діагностика", "повна діагностика"]):
        return "full_scan"

    pid_keywords = {
        "оберти": "Оберти двигуна",
        "rpm": "Оберти двигуна",
        "дросель": "Положення дросельної заслінки",
        "температура двигуна": "Температура охолодження",
        "температура охолодження": "Температура охолодження",
        "швидкість": "Швидкість",
        "напруга": "Напруга АКБ",
        "навантаження": "Навантаження на двигун",
        "витрата повітря": "Масова витрата повітря",
        "температура впуску": "Температура впускного повітря",
    }

    for keyword, pid_name in pid_keywords.items():
        if keyword in t:
            return f"pid:{pid_name}"

    return None


def load_cars():
    return json.loads(CARS_FILE.read_text(encoding="utf-8"))


def save_cars(cars):
    CARS_FILE.write_text(json.dumps(cars, ensure_ascii=False, indent=2), encoding="utf-8")


@app.route("/")
def index():
    return render_template("index.html", api_token=API_TOKEN)


@app.route("/status")
def status():
    online = is_online()
    return jsonify({"online": online, "mode": "Онлайн" if online else "Автономний"})


@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user_input = data.get("message", "")
    # Підтримка session_id від клієнта, якщо передано
    session_id = data.get("session_id", get_current_session_id())
    if not user_input:
        return jsonify({"reply": ""})

    online = is_online()

    import re as _re
    car_pattern = _re.search(
        r'(ford|opel|bmw|volkswagen|vw|toyota|honda|renault|audi|mercedes|kia|hyundai|skoda|mazda|volvo|nissan|форд|опель|бмв|тойота|рено|ауді|мерседес|шкода|хонда|нісан)\s+(\w+)\s+(\d{4})',
        user_input.lower()
    )
    if car_pattern:
        from adapter_researcher import set_car_context
        threading.Thread(
            target=set_car_context,
            args=(car_pattern.group(1), car_pattern.group(2), car_pattern.group(3)),
            daemon=True
        ).start()

    obd_cmd = detect_obd_command(user_input)

    if obd_cmd == "full_scan":
        obd_context = run_auto_diagnosis(user_input)
        user_input = user_input + f"\n\nРезультати OBD сканування:\n{obd_context}"

    elif obd_cmd == "read_dtc":
        obd_context = run_read_dtc()
        user_input = user_input + f"\n\nРезультати читання помилок:\n{obd_context}"

    elif obd_cmd == "clear_dtc":
        obd_context = run_clear_dtc()
        user_input = user_input + f"\n\nРезультат очищення:\n{obd_context}"

    elif obd_cmd and obd_cmd.startswith("pid:"):
        pid_name = obd_cmd.replace("pid:", "")
        obd_context = run_specific_pid(pid_name)
        user_input = user_input + f"\n\nДані датчика:\n{obd_context}"

    # ВИПРАВЛЕНО: messages завжди визначається тут, після всіх модифікацій user_input
    append_to_history(session_id, {"role": "user", "content": user_input})
    messages = get_history(session_id)

    def generate():
        full_reply = ""

        from adapters import get_active_adapter
        active_adapter = get_active_adapter()
        adapter_context = ""
        if active_adapter:
            caps = active_adapter.get("capabilities")
            car = active_adapter.get("car_context")
            st = active_adapter.get("status")
            if st == "analyzing":
                adapter_context = f"\nАдаптер '{active_adapter['name']}' зараз аналізується."
            elif caps and car:
                sensors = ", ".join(caps.get("sensors_available", [])[:5])
                actuators = ", ".join(caps.get("actuators_available", []))
                summary = caps.get("summary", "")
                adapter_context = f"\nАдаптер: {active_adapter['name']}\nАвто: {car.get('year','')} {car.get('make','')} {car.get('model','')}\nДоступно: {summary}\nДатчики: {sensors}\nАктуатори: {actuators or 'недоступні'}"

        gemini_prompt = f"""Ти - IRIS, діагностичний асистент стенду SynthAI.
Спілкуйся природно і дружньо українською мовою.
Якщо є дані OBD — аналізуй їх детально.
Якщо OBD не підключено і оператор питає про стан авто — нагадай підключити адаптер.
Коди помилок пояснюй простою мовою.
Не згадуй яку модель AI використовуєш.
{adapter_context}

Запит оператора: {user_input}"""

        if online and gemini_client:
            try:
                response = gemini_client.models.generate_content_stream(
                    model="gemini-2.5-flash",
                    contents=gemini_prompt
                )
                for chunk in response:
                    if chunk.text:
                        full_reply += chunk.text
                        yield f"data: {json.dumps({'token': chunk.text, 'mode': 'online'})}\n\n"
            except Exception as e:
                print(f"Gemini error: {e}")
                try:
                    stream = ollama.chat(model="gemma3:12b", messages=messages, stream=True)
                    for chunk in stream:
                        token = chunk["message"]["content"]
                        full_reply += token
                        yield f"data: {json.dumps({'token': token, 'mode': 'offline'})}\n\n"
                except Exception as e2:
                    print(f"Ollama fallback error: {e2}")
                    yield f"data: {json.dumps({'token': 'Помилка підключення до AI.', 'mode': 'offline'})}\n\n"
        else:
            try:
                stream = ollama.chat(model="gemma3:12b", messages=messages, stream=True)
                for chunk in stream:
                    token = chunk["message"]["content"]
                    full_reply += token
                    yield f"data: {json.dumps({'token': token, 'mode': 'offline'})}\n\n"
            except Exception as e:
                print(f"Ollama error: {e}")
                yield f"data: {json.dumps({'token': 'Ollama недоступна. Перевірте підключення.', 'mode': 'offline'})}\n\n"

        if full_reply:
            append_to_history(session_id, {"role": "assistant", "content": full_reply})
            save_session(session_id)
        yield f"data: {json.dumps({'done': True, 'mode': 'online' if online else 'offline'})}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@app.route("/voice/listen", methods=["POST"])
def voice_listen():
    from voice import listen
    text = listen()
    if text:
        return jsonify({"text": text, "ok": True})
    return jsonify({"text": "", "ok": False})


@app.route("/voice/speak", methods=["POST"])
def voice_speak():
    from voice import speak
    text = request.json.get("text", "")
    threading.Thread(target=speak, args=(text,), daemon=True).start()
    return jsonify({"ok": True})


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html", api_token=API_TOKEN)


@app.route("/adapters-page")
def adapters_page():
    return render_template("adapters.html", api_token=API_TOKEN)


@app.route("/api/adapters")
def api_adapters():
    from adapters import list_adapters
    return jsonify(list_adapters())


@app.route("/api/adapters", methods=["POST"])
def api_add_adapter():
    from adapters import add_adapter
    from adapter_researcher import get_pending_car, research_and_update
    data = request.json
    adapter = add_adapter(data.get("name", ""), data.get("description", ""))
    car = get_pending_car()
    if car:
        threading.Thread(target=research_and_update, args=(adapter, car), daemon=True).start()
    return jsonify(adapter)


@app.route("/api/adapters/<adapter_id>", methods=["DELETE"])
def api_delete_adapter(adapter_id):
    from adapters import delete_adapter
    delete_adapter(adapter_id)
    return jsonify({"ok": True})


@app.route("/api/adapters/<adapter_id>/activate", methods=["POST"])
def api_activate_adapter(adapter_id):
    from adapters import set_active_adapter
    set_active_adapter(adapter_id)
    return jsonify({"ok": True})


@app.route("/api/adapters/<adapter_id>/recheck", methods=["POST"])
def api_recheck_adapter(adapter_id):
    from adapters import load_adapters, update_adapter_with_car
    from adapter_researcher import research_adapter, get_pending_car
    data = request.json
    adapters = load_adapters()
    adapter = next((a for a in adapters if a["id"] == adapter_id), None)
    if not adapter:
        return jsonify({"error": "not found"}), 404
    car = adapter.get("car_context") or get_pending_car() or {}

    def recheck():
        try:
            caps = research_adapter(
                data.get("name", adapter["name"]),
                data.get("description", adapter.get("description", "")),
                car.get("make", ""), car.get("model", ""), car.get("year", "")
            )
            update_adapter_with_car(adapter_id, car, caps)
            print(f"[RECHECK] {adapter['name']} — {len(caps.get('pids', []))} PID")
        except Exception as e:
            print(f"[RECHECK ERROR] {e}")

    threading.Thread(target=recheck, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/active-adapter")
def api_active_adapter():
    from adapters import get_active_adapter
    return jsonify(get_active_adapter() or {})


@app.route("/adapter/status")
def adapter_status():
    import time

    def generate():
        last = None
        while True:
            try:
                from adapters import get_active_adapter
                adapter = get_active_adapter()
                if adapter:
                    current = f"{adapter.get('status')}_{adapter.get('id')}"
                    if current != last:
                        last = current
                        caps = adapter.get("capabilities") or {}
                        car = adapter.get("car_context") or {}
                        yield f"data: {json.dumps({'status': adapter.get('status'), 'adapter': adapter.get('name'), 'car': car, 'summary': caps.get('summary', ''), 'sensors': caps.get('sensors_available', []), 'actuators': caps.get('actuators_available', [])})}\n\n"
            except Exception as e:
                print(f"[ADAPTER STATUS ERROR] {e}")
            time.sleep(3)

    return Response(generate(), mimetype="text/event-stream")


@app.route("/obd/live")
def obd_live():
    import time

    def generate():
        while True:
            try:
                from obd_module import get_obd_data
                data = get_obd_data()
            except Exception as e:
                data = {"error": str(e)}
            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(2)

    return Response(generate(), mimetype="text/event-stream")


@app.route("/obd/scan", methods=["POST"])
def obd_scan():
    from obd_module import get_obd_data
    return jsonify(get_obd_data())


@app.route("/obd/clear", methods=["POST"])
def obd_clear():
    from obd_module import clear_dtc
    return jsonify({"ok": clear_dtc()})


@app.route("/cars")
def cars_page():
    return render_template("cars.html", api_token=API_TOKEN)


@app.route("/api/cars")
def api_cars():
    return jsonify(load_cars())


@app.route("/api/cars", methods=["POST"])
def api_add_car():
    cars = load_cars()
    car = request.json
    car["id"] = str(uuid.uuid4())[:8]
    car["created"] = datetime.datetime.now().strftime("%d.%m.%Y")
    car["diagnostics"] = []
    cars.append(car)
    save_cars(cars)
    return jsonify(car)


@app.route("/api/cars/<car_id>", methods=["DELETE"])
def api_delete_car(car_id):
    cars = [c for c in load_cars() if c["id"] != car_id]
    save_cars(cars)
    return jsonify({"ok": True})


@app.route("/api/cars/<car_id>/diagnostic", methods=["POST"])
def api_add_diagnostic(car_id):
    cars = load_cars()
    for car in cars:
        if car["id"] == car_id:
            diag = request.json
            diag["date"] = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
            diag["id"] = str(uuid.uuid4())[:8]
            car["diagnostics"].append(diag)
    save_cars(cars)
    return jsonify({"ok": True})


@app.route("/api/cars/<car_id>/diagnostic/<diag_id>", methods=["DELETE"])
def api_delete_diagnostic(car_id, diag_id):
    cars = load_cars()
    for car in cars:
        if car["id"] == car_id:
            car["diagnostics"] = [d for d in car["diagnostics"] if d["id"] != diag_id]
    save_cars(cars)
    return jsonify({"ok": True})


@app.route("/sessions")
def sessions():
    return jsonify(load_sessions())


@app.route("/session/<session_id>")
def load_session(session_id):
    session_file = HISTORY_DIR / f"{session_id}.json"
    if not session_file.exists():
        return jsonify({"error": "not found"}), 404
    with open(session_file, encoding="utf-8") as f:
        data = json.load(f)
    with _sessions_lock:
        _session_histories[session_id] = [SYSTEM_PROMPT] + data["messages"]
    set_current_session_id(session_id)
    return jsonify(data)


@app.route("/session/<session_id>/delete", methods=["DELETE"])
def delete_session(session_id):
    session_file = HISTORY_DIR / f"{session_id}.json"
    if session_file.exists():
        session_file.unlink()
    with _sessions_lock:
        _session_histories.pop(session_id, None)
    return jsonify({"ok": True})


@app.route("/new_session", methods=["POST"])
def new_session():
    new_id = str(uuid.uuid4())[:8]
    set_current_session_id(new_id)
    reset_history(new_id)
    return jsonify({"id": new_id})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
