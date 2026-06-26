import json
import os
import re
import threading
import logging
from google import genai
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("synthai.adapter_researcher")

RESEARCH_KEY = os.getenv("GEMINI_RESEARCH_API_KEY")
research_client = None

if RESEARCH_KEY:
    research_client = genai.Client(api_key=RESEARCH_KEY)

_pending_car = None
_lock = threading.Lock()


def set_car_context(make: str, model: str, year: str):
    global _pending_car
    car = {"make": make, "model": model, "year": year}
    with _lock:
        _pending_car = car

    from adapters import get_analyzing_adapters
    analyzing = get_analyzing_adapters()
    if analyzing:
        for adapter in analyzing:
            # ВИПРАВЛЕНО: передаємо car як аргумент, не читаємо глобальний стан з потоку
            threading.Thread(
                target=_safe_research_and_update,
                args=(adapter, car),
                daemon=True
            ).start()


def _safe_research_and_update(adapter: dict, car: dict):
    """Обгортка з обробкою помилок для фонового потоку."""
    try:
        research_and_update(adapter, car)
    except Exception as e:
        logger.error(f"Помилка дослідження адаптера {adapter.get('id', '?')}: {e}")


def get_pending_car():
    with _lock:
        return _pending_car


def research_and_update(adapter: dict, car: dict):
    from adapters import update_adapter_with_car
    caps = research_adapter(
        adapter["name"],
        adapter["description"],
        car.get("make", ""),
        car.get("model", ""),
        car.get("year", "")
    )
    update_adapter_with_car(adapter["id"], car, caps)
    logger.info(f"Адаптер готовий: {adapter['id']} | {caps.get('summary', '')}")


def research_adapter(name: str, description: str, car_make: str = "", car_model: str = "", car_year: str = "") -> dict:
    if not research_client:
        return _default_caps()

    car_info = f"{car_year} {car_make} {car_model}".strip() if car_make else "будь-яке авто"

    prompt = f"""Ти експерт з OBD діагностики та автомобільних протоколів.
Знайди реальні OBD PID коди для авто: {car_info}
Адаптер: {name} — {description}

Поверни ТІЛЬКИ валідний JSON без пояснень та markdown:
{{
  "can_read_dtc": true,
  "can_clear_dtc": true,
  "can_read_sensors": true,
  "can_control_actuators": false,
  "can_read_advanced": false,
  "protocols": ["ISO9141-2"],
  "sensors_available": ["Оберти двигуна", "Температура"],
  "actuators_available": [],
  "limitations": [],
  "summary": "1-2 речення українською",
  "pids": [
    {{
      "name": "Оберти двигуна",
      "pid": "010C",
      "mode": "01",
      "formula": "((A*256)+B)/4",
      "unit": "RPM",
      "description": "Оберти двигуна в хвилину"
    }},
    {{
      "name": "Температура охолодження",
      "pid": "0105",
      "mode": "01",
      "formula": "A-40",
      "unit": "°C",
      "description": "Температура охолоджувальної рідини"
    }},
    {{
      "name": "Швидкість",
      "pid": "010D",
      "mode": "01",
      "formula": "A",
      "unit": "км/год",
      "description": "Швидкість автомобіля"
    }},
    {{
      "name": "Напруга АКБ",
      "pid": "ATRV",
      "mode": "AT",
      "formula": "A",
      "unit": "В",
      "description": "Напруга бортової мережі"
    }}
  ],
  "dtc_commands": {{
    "read": "03",
    "clear": "04",
    "read_pending": "07"
  }}
}}"""

    try:
        response = research_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        text = response.text

        # ВИПРАВЛЕНО: надійне витягування JSON через regex
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if not match:
            logger.warning("JSON не знайдено у відповіді Gemini")
            return _default_caps()

        return json.loads(match.group(0))
    except json.JSONDecodeError as e:
        logger.error(f"Помилка парсингу JSON: {e}")
        return _default_caps()
    except Exception as e:
        logger.error(f"Помилка запиту до Gemini: {e}")
        return _default_caps()


def _default_caps():
    return {
        "can_read_dtc": True,
        "can_clear_dtc": True,
        "can_read_sensors": True,
        "can_control_actuators": False,
        "can_read_advanced": False,
        "protocols": ["ISO9141-2"],
        "sensors_available": ["Напруга"],
        "actuators_available": [],
        "limitations": ["Тільки стандартні OBD-II"],
        "summary": "Базовий OBD адаптер",
        "pids": [
            {"name": "Напруга АКБ", "pid": "ATRV", "mode": "AT", "formula": "A", "unit": "В", "description": "Напруга бортової мережі"},
            {"name": "Коди помилок", "pid": "03", "mode": "03", "formula": "A", "unit": "", "description": "Читання DTC кодів"}
        ],
        "dtc_commands": {"read": "03", "clear": "04", "read_pending": "07"}
    }
