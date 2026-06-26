# SynthAI — AI Automotive Diagnostic Stand

<div align="center">

```
███████╗██╗   ██╗███╗   ██╗████████╗██╗  ██╗ █████╗ ██╗
██╔════╝╚██╗ ██╔╝████╗  ██║╚══██╔══╝██║  ██║██╔══██╗██║
███████╗ ╚████╔╝ ██╔██╗ ██║   ██║   ███████║███████║██║
╚════██║  ╚██╔╝  ██║╚██╗██║   ██║   ██╔══██║██╔══██║██║
███████║   ██║   ██║ ╚████║   ██║   ██║  ██║██║  ██║██║
╚══════╝   ╚═╝   ╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝
```

**Розумний діагностичний стенд з AI-асистентом IRIS**

🇺🇦 Українська (нижче) | [🇬🇧 Read in English](#synthai-in-english)

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.x-lightgrey?logo=flask)](https://flask.palletsprojects.com/)
[![Gemini](https://img.shields.io/badge/Gemini-2.5_Flash-orange?logo=google)](https://aistudio.google.com/)
[![OBD](https://img.shields.io/badge/OBD--II-ELM327-green)](https://en.wikipedia.org/wiki/OBD-II_PIDs)
[![License](https://img.shields.io/badge/License-MIT-blue)](LICENSE)

</div>

---

## Що це таке

SynthAI — це локальний AI-стенд для автомобільної діагностики. Замість дорогого обладнання — звичайний ПК з Ubuntu, Bluetooth OBD адаптер і відкритий вебінтерфейс. AI-асистент IRIS спілкується українською, читає дані з авто в реальному часі та пояснює помилки простою мовою.

**Режими роботи:**

* **Онлайн** — використовує Google Gemini 2.5 Flash (швидко, точно)
* **Офлайн** — автоматично перемикається на локальну модель Ollama `gemma3:12b` без інтернету

---

## Можливості

* 💬 **AI-чат з IRIS** — природна діалогова діагностика українською мовою
* 🔌 **OBD-II діагностика** — читання датчиків, кодів помилок (DTC), очищення помилок
* 📊 **Live дашборд** — показники двигуна в реальному часі (оберти, температура, швидкість тощо)
* 🔊 **Голосовий режим** — розпізнавання мови (Google STT) + синтез мовлення (Edge TTS, голос Polina)
* 🚗 **База автомобілів** — збереження авто та історії діагностик
* 🔧 **Менеджер адаптерів** — AI автоматично визначає PID-коди для конкретного авто через Gemini
* 📝 **Історія сесій** — зберігає всі діалоги між запусками
* 🌐 **Кіоск-режим** — автозапуск Firefox у повноекранному режимі без робочого столу

---

## Стек

|Шар|Технологія|
|-|-|
|Бекенд|Python 3.11+, Flask|
|AI онлайн|Google Gemini 2.5 Flash|
|AI офлайн|Ollama + Gemma 3 12B|
|OBD|ELM327 через Bluetooth (`/dev/rfcomm0`)|
|TTS|Edge TTS (`uk-UA-PolinaNeural`)|
|STT|SpeechRecognition + Google API|
|Аудіо|pygame, PipeWire|
|Фронтенд|Vanilla JS + HTML/CSS (без фреймворків)|
|Автозапуск|OpenBox + systemd|

---

## Вимоги до обладнання

* **ОС:** Ubuntu 22.04 / 24.04
* **RAM:** 8 GB мінімум (16 GB рекомендовано для Gemma 12B)
* **SSD:** 50 GB+ вільного місця
* **Bluetooth:** донгл або вбудований (Realtek, Intel)
* **OBD адаптер:** ELM327 Bluetooth (v1.5 або v2.1)

---

## Встановлення

### 1. Клонуйте репозиторій

```bash
git clone https://github.com/Synth410/SynthAI-.git
cd SynthAI-/autodiag
```

### 2. Запустіть встановлення

```bash
chmod +x install.sh
./install.sh
```

Скрипт інтерактивно запитає:

* API ключі Gemini (безкоштовно на [aistudio.google.com](https://aistudio.google.com))
* MAC адресу вашого OBD Bluetooth адаптера
* Ім'я користувача Ubuntu

### 3. Знайдіть MAC адресу OBD адаптера

```bash
bluetoothctl scan on
# знайдіть ваш OBD пристрій у списку (зазвичай "OBDII" або "ELM327")
```

### 4. Перезавантажте систему

```bash
sudo reboot
```

Після перезавантаження система автоматично підключиться до OBD адаптера і відкриє інтерфейс у браузері.

---

## Ручний запуск (без автозапуску)

```bash
cd autodiag
source venv/bin/activate
python3 app.py
# відкрийте http://localhost:5000
```

---

## Конфігурація

Всі налаштування зберігаються у файлі `.env` (приклад — `autodiag/.env.example`):

```env
GEMINI_API_KEY=ваш_ключ
GEMINI_RESEARCH_API_KEY=другий_ключ_або_той_самий
OBD_MAC=AA:BB:CC:11:22:33
```

> ⚠️ **Ніколи не комітьте `.env` у репозиторій.** Файл вже доданий до `.gitignore`.

---

## Структура проєкту

```
autodiag/
├── app.py                  # Головний Flask-сервер, всі маршрути
├── obd_module.py           # ELM327 підключення, читання PID та DTC
├── adapters.py             # Менеджер OBD адаптерів (CRUD, активація)
├── adapter_researcher.py   # AI-дослідник PID кодів через Gemini
├── voice.py                # TTS (Edge TTS) + STT (SpeechRecognition)
├── install.sh              # Автоматичне встановлення
├── start.sh                # Ручний запуск
├── .env                    # API ключі та MAC адреса (не в git)
├── data/
│   ├── cars.json           # База автомобілів
│   └── adapters.json       # Збережені адаптери
├── history/                # Сесії діалогів (автогенерується)
└── templates/
    ├── index.html          # Головна сторінка (чат + голос)
    ├── dashboard.html      # Live OBD дашборд
    ├── adapters.html       # Менеджер адаптерів
    └── cars.html           # База автомобілів
```

---

## Як користуватись

### Перша діагностика

1. Підключіть OBD адаптер до роз'єму авто (під рулем)
2. Переконайтесь що Bluetooth з'єднання активне
3. В чаті напишіть марку і модель авто, наприклад:

> *"Ford Focus 2015"*

4. IRIS автоматично підбере PID коди для цього авто
5. Запитайте діагностику:

> *"Проведи діагностику"* або натисніть кнопку **Сканувати**

### Голосовий режим

Натисніть кнопку 🎤 в правому нижньому куті — IRIS перейде у режим голосового спілкування.

### Читання помилок

> *"Які помилки є на авто?"* / *"Прочитай DTC"*

### Очищення помилок

> *"Очисти помилки"* / *"Скинь помилки"*

### Конкретні датчики

> *"Яка температура двигуна?"* / *"Скільки обертів?"* / *"Яка напруга АКБ?"*

---

## Підтримка

Створював це з 0 знань на диплом

Telegram: [@Synth41](https://t.me/Synth41)

---

<a name="synthai-in-english"></a>

# SynthAI (in English)

<div align="center">

**A smart automotive diagnostic stand with the IRIS AI assistant**

</div>

---

## What it is

SynthAI is a local AI stand for automotive diagnostics. Instead of expensive equipment, all you need is a regular PC running Ubuntu, a Bluetooth OBD adapter, and an open web interface. The IRIS AI assistant communicates in Ukrainian, reads live data from the car, and explains error codes in plain language.

**Operating modes:**

* **Online** — uses Google Gemini 2.5 Flash (fast, accurate)
* **Offline** — automatically switches to the local Ollama `gemma3:12b` model when there's no internet

---

## Features

* 💬 **AI chat with IRIS** — natural conversational diagnostics (in Ukrainian)
* 🔌 **OBD-II diagnostics** — reads sensors, error codes (DTC), and clears errors
* 📊 **Live dashboard** — real-time engine metrics (RPM, temperature, speed, etc.)
* 🔊 **Voice mode** — speech recognition (Google STT) + speech synthesis (Edge TTS, Polina voice)
* 🚗 **Car database** — stores vehicles and diagnostic history
* 🔧 **Adapter manager** — AI automatically determines PID codes for a specific car via Gemini
* 📝 **Session history** — saves all conversations between runs
* 🌐 **Kiosk mode** — auto-launches Firefox in fullscreen with no desktop

---

## Stack

|Layer|Technology|
|-|-|
|Backend|Python 3.11+, Flask|
|AI online|Google Gemini 2.5 Flash|
|AI offline|Ollama + Gemma 3 12B|
|OBD|ELM327 over Bluetooth (`/dev/rfcomm0`)|
|TTS|Edge TTS (`uk-UA-PolinaNeural`)|
|STT|SpeechRecognition + Google API|
|Audio|pygame, PipeWire|
|Frontend|Vanilla JS + HTML/CSS (no frameworks)|
|Autostart|OpenBox + systemd|

---

## Hardware requirements

* **OS:** Ubuntu 22.04 / 24.04
* **RAM:** 8 GB minimum (16 GB recommended for Gemma 12B)
* **SSD:** 50 GB+ free space
* **Bluetooth:** dongle or built-in (Realtek, Intel)
* **OBD adapter:** ELM327 Bluetooth (v1.5 or v2.1)

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/Synth410/SynthAI-.git
cd SynthAI-/autodiag
```

### 2. Run the installer

```bash
chmod +x install.sh
./install.sh
```

The script will interactively ask for:

* Gemini API keys (free at [aistudio.google.com](https://aistudio.google.com))
* The MAC address of your OBD Bluetooth adapter
* Your Ubuntu username

### 3. Find your OBD adapter's MAC address

```bash
bluetoothctl scan on
# look for your OBD device in the list (usually "OBDII" or "ELM327")
```

### 4. Reboot

```bash
sudo reboot
```

After reboot the system will automatically connect to the OBD adapter and open the interface in a browser.

---

## Manual run (without autostart)

```bash
cd autodiag
source venv/bin/activate
python3 app.py
# open http://localhost:5000
```

---

## Configuration

All settings are stored in the `.env` file (see `autodiag/.env.example`):

```env
GEMINI_API_KEY=your_key
GEMINI_RESEARCH_API_KEY=second_key_or_the_same_one
OBD_MAC=AA:BB:CC:11:22:33
```

> ⚠️ **Never commit `.env` to the repository.** It's already added to `.gitignore`.

---

## Project structure

```
autodiag/
├── app.py                  # Main Flask server, all routes
├── obd_module.py           # ELM327 connection, PID and DTC reading
├── adapters.py             # OBD adapter manager (CRUD, activation)
├── adapter_researcher.py   # AI researcher for PID codes via Gemini
├── voice.py                # TTS (Edge TTS) + STT (SpeechRecognition)
├── install.sh              # Automated installation
├── start.sh                # Manual launch
├── .env                    # API keys and MAC address (not in git)
├── data/
│   ├── cars.json           # Car database
│   └── adapters.json       # Saved adapters
├── history/                # Conversation sessions (auto-generated)
└── templates/
    ├── index.html          # Main page (chat + voice)
    ├── dashboard.html      # Live OBD dashboard
    ├── adapters.html       # Adapter manager
    └── cars.html           # Car database
```

---

## Usage

### First diagnostic run

1. Plug the OBD adapter into the car's port (usually under the steering wheel)
2. Make sure the Bluetooth connection is active
3. In the chat, type your car's make and model, e.g.:

> *"Ford Focus 2015"*

4. IRIS will automatically pick the right PID codes for that car
5. Ask for a diagnostic:

> *"Run a diagnostic"* or click the **Scan** button

### Voice mode

Click the 🎤 button in the bottom-right corner — IRIS will switch to voice conversation mode.

### Reading errors

> *"What errors does the car have?"* / *"Read the DTC"*

### Clearing errors

> *"Clear the errors"* / *"Reset the errors"*

### Specific sensors

> *"What's the engine temperature?"* / *"What's the RPM?"* / *"What's the battery voltage?"*

---

## Support

Built this from zero knowledge for a thesis project.

Telegram: [@Synth41](https://t.me/Synth41)

---

## License

This project is licensed under the [MIT License](LICENSE).
