import os
import httpx
import json
import re
import uuid
from datetime import datetime
from typing import Optional, List
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Form, UploadFile, File, Query, Response, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv
from google import genai
from google.genai import types
from io import BytesIO
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

# --- CONFIG & SETUP ---
load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# ДОДАЙТЕ ЦІ ТРИ РЯДКИ:
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "knowledge_base")
os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
knowledge_files_cache = [] # Тут зберігатимуться завантажені документи

app = FastAPI(title="UAV Command System v10.6")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")

if not URL or not KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env file")

# FIX: Force IPv4 for httpx to prevent [Errno 11001] getaddrinfo failed on Windows
try:
    # Set explicit transport to avoid IPv6 DNS drops during intense async bursts
    transport = httpx.HTTPTransport(local_address="0.0.0.0", retries=3)
    custom_client = httpx.Client(transport=transport, timeout=30.0)
    supabase: Client = create_client(URL, KEY)
    supabase.postgrest.session = custom_client
except Exception as e:
    print(f"Попередження налаштування httpx: {e}")
    supabase: Client = create_client(URL, KEY)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    ai_client = genai.Client(api_key=GEMINI_API_KEY)
else:
    ai_client = None

UNITS = [
    'впс "Кодима"', 'віпс "Загнітків"', 'віпс "Шершенці"', 'впс "Станіславка"', 
    'віпс "Тимкове"', 'віпс "Чорна"', 'впс "Окни"', 'віпс "Ткаченкове"', 
    'віпс "Гулянка"', 'віпс "Новосеменівка"', 'впс "Великокомарівка"', 
    'віпс "Павлівка"', 'віпс "Велика Михайлівка"', 'віпс "Слов\'яносербка"', 
    'віпс "Гребеники"', 'впс "Степанівка"', 'віпс "Лучинське"', 
    'віпс "Кучурган"', 'віпс "Лиманське"', "Група ВОПРтаПБпПС", "ВЗФБпАКтаЗПБпС"
]

async def cleanup_database_names():
    """Знаходить і виправляє ненормалізовані імена операторів у всій базі даних."""
    print("Запуск очищення імен операторів у базі даних...")
    try:
        # 1. Отримуємо всі записи польотів (тільки поле operator)
        # Примітка: для великих баз краще використовувати розширені запити, 
        # але для поточного об'єму достатньо простого перебору унікальних значень.
        res = supabase.table("flights").select("operator").execute()
        if not res.data: return
        
        # 2. Знаходимо унікальні імена, які потребують виправлення
        unique_operators = set(item['operator'] for item in res.data if item.get('operator'))
        
        updates_count = 0
        for original_name in unique_operators:
            normalized_name = normalize_operator_name(original_name)
            
            if original_name != normalized_name:
                # 3. Оновлюємо всі рядки з цим ім'ям
                print(f"  Нормалізація: '{original_name}' -> '{normalized_name}'")
                supabase.table("flights").update({"operator": normalized_name}).eq("operator", original_name).execute()
                updates_count += 1
        
        if updates_count > 0:
            print(f"Очищення завершено. Виправлено типів імен: {updates_count}")
        else:
            print("База даних вже нормалізована.")
            
    except Exception as e:
        print(f"Помилка під час очищення бази: {e}")

@app.on_event("startup")
async def startup_event():
    global knowledge_files_cache
    
    # 1. Синхронізація бази знань
    if ai_client: 
        print("Синхронізація бази знань з Gemini...")
        try:
            # Отримуємо список файлів, які вже є в хмарі, щоб не дублювати
            existing_files = {f.display_name: f for f in ai_client.files.list()}
            
            # Скануємо локальну папку
            for filename in os.listdir(KNOWLEDGE_DIR):
                if filename.lower().endswith(('.pdf', '.txt', '.docx')):
                    file_path = os.path.join(KNOWLEDGE_DIR, filename)
                    
                    if filename in existing_files:
                        print(f"Файл {filename} вже є в базі Gemini.")
                        knowledge_files_cache.append(existing_files[filename])
                    else:
                        try:
                            print(f"Завантаження {filename} до Gemini...")
                            uploaded_file = ai_client.files.upload(file=file_path, config={'display_name': filename})
                            knowledge_files_cache.append(uploaded_file)
                        except Exception:
                            # Якщо дисплейне ім'я або ШЛЯХ з кирилицею "ламає" SDK на Windows
                            print("⚠️ Помилка завантаження файлу (можливо через кирилицю назви). Спроба через тимчасовий файл...")
                            import shutil
                            import tempfile
                            
                            temp_dir = tempfile.gettempdir()
                            file_ext = os.path.splitext(filename)[1]
                            safe_temp_name = f"gemini_v3_{int(datetime.now().timestamp())}_{hash(filename)%1000}{file_ext}"
                            temp_path = os.path.join(temp_dir, safe_temp_name)
                            
                            try:
                                # Використовуємо системне копіювання, яке краще справляється з шляхами
                                shutil.copy2(file_path, temp_path)
                                uploaded_file = ai_client.files.upload(file=temp_path, config={'display_name': safe_temp_name})
                                knowledge_files_cache.append(uploaded_file)
                                print(f"✅ Успішно завантажено (через temp): {safe_temp_name}")
                                if os.path.exists(temp_path): os.remove(temp_path)
                            except Exception as inner_e:
                                # Не друкуємо filename тут, щоб не викликати UnicodeEncodeError у терміналі
                                print(f"❌ Не вдалося завантажити через temp: {str(inner_e).encode('ascii', 'ignore').decode('ascii')}")
                                if os.path.exists(temp_path): os.remove(temp_path)
                        
            print(f"База знань готова! Активних документів: {len(knowledge_files_cache)}")
        except Exception as e:
            print(f"⚠️ Загальна помилка ініціалізації бази знань: {e}")
    else:
        print("API ключ Gemini не знайдено. База знань не завантажена.")

    # 2. Очищення та нормалізація імен у базі (Запуск у фоні, щоб не затримувати старт)
    import asyncio
    asyncio.create_task(cleanup_database_names())

# --- MODELS ---

class FlightEntry(BaseModel):
    date: str
    shift_time: str
    operator: str
    unit: str
    drone: str
    takeoff: str
    landing: str
    duration: Optional[float] = 0.0
    distance: Optional[float] = 0.0
    battery_cycles: Optional[float] = 0.0
    result: Optional[str] = "Без ознак порушення"
    weather: Optional[str] = "Нормальні"
    conditions: Optional[str] = "Норма"
    route: Optional[str] = "Не вказано"
    battery_id: Optional[str] = ""

class AnnouncementUpdate(BaseModel):
    text: str
    is_active: bool

class AuthCheck(BaseModel):
    unit: str
    operator: str
    password: str

class StatusUpdate(BaseModel):
    id: int
    status: str

# --- HELPERS ---

def calculate_duration(t1: str, t2: str):
    try:
        fmt = "%H:%M"
        start = datetime.strptime(t1.strip(), fmt)
        end = datetime.strptime(t2.strip(), fmt)
        diff = (end - start).total_seconds() / 60
        if diff < 0: diff += 1440
        return int(diff)
    except:
        return 0

def normalize_operator_name(name: str) -> str:
    """Нормалізує ім'я оператора: прибирає звання, ініціали та зайві знаки, залишаючи лише прізвище."""
    if not name: return "Невідомо"
    
    # Список звань та скорочень для видалення
    ranks = [
        r"солдат", r"сержант", r"лейтенант", r"капітан", r"майор", r"підполковник", r"полковник",
        r"мл\.?\s*с-нт", r"ст\.?\s*с-нт", r"мл\.", r"ст\.", r"с-нт", r"лт", r"кпт", r"м\-р", r"п\-к", r"ген",
        r"рядовий", r"старшина", r"прапорщик"
    ]
    
    # 1. Прибираємо звання (регістронезалежно)
    res_name = name
    for rank in ranks:
        res_name = re.sub(rf'\b{rank}\b\.?\s*', '', res_name, flags=re.IGNORECASE)
    
    # 2. Прибираємо ініціали (напр. "О.Г.", "О. Г.", "Гонцов О.")
    # Видаляємо поодинокі букви з крапками або без
    res_name = re.sub(r'\b[А-ЯЁA-Z]\.\s*', '', res_name)
    res_name = re.sub(r'\s+[А-ЯЁA-Z](\.|$)', '', res_name)
    
    # 3. Прибираємо зайві знаки
    res_name = res_name.strip(' ._,-')
    
    # 4. Беремо лише перше слово (зазвичай це прізвище після очищення)
    words = res_name.split()
    if words:
        res_name = words[0]
    
    # 5. Вирівнюємо регістр
    if res_name:
        res_name = res_name.capitalize()
    
    return res_name or "Невідомо"

# --- API ROUTES ---

@app.get("/api/get_announcement")
async def get_announcement():
    res = supabase.table("app_settings").select("*").eq("id", 1).execute()
    if res.data:
        return res.data[0]
    return {"is_announcement_active": False, "announcement_text": ""}

@app.post("/api/update_announcement")
async def update_announcement(data: AnnouncementUpdate):
    try:
        supabase.table("app_settings").update({
            "announcement_text": data.text,
            "is_announcement_active": data.is_active
        }).eq("id", 1).execute()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/get_unit_drones")
async def get_unit_drones(unit: str = Query(...)):
    res = supabase.table("drones").select("*").eq("unit", unit).execute()
    return res.data

@app.post("/api/update_drone_status")
async def update_drone_status(data: StatusUpdate):
    try:
        res = supabase.table("drones").update({"status": data.status}).eq("id", data.id).execute()
        return {"status": "ok"}
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/add_new_drone")
async def add_new_drone(data: dict):
    try:
        res = supabase.table("drones").insert({
            "unit": data['unit'],
            "model": data['model'],
            "serial_number": data['serial_number'],
            "status": "Active"
        }).execute()
        return res.data
    except Exception as e:
        print(f"Error adding drone: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/check_auth")
async def check_auth(data: AuthCheck):
    """Перевіряє пароль або реєструє нового оператора під пароль."""
    normalized_name = normalize_operator_name(data.operator)
    try:
        # Шукаємо існуючий пароль
        res = supabase.table("operator_passwords").select("*").eq("unit", data.unit).eq("name", normalized_name).execute()
        
        if not res.data:
            # Якщо запису немає - реєструємо (перший вхід)
            supabase.table("operator_passwords").insert({
                "unit": data.unit,
                "name": normalized_name,
                "password": data.password
            }).execute()
            return {"status": "ok", "message": "Зареєстровано новий профіль"}
        
        # Якщо запис є - перевіряємо пароль
        stored_password = res.data[0].get('password')
        if stored_password == data.password:
            return {"status": "ok", "message": "Успішний вхід"}
        else:
            return {"status": "error", "message": "Неправильний пароль для цього прізвища"}
            
    except Exception as e:
        print(f"Auth error: {e}")
        # Якщо таблиці не існує - можливо, треба повідомити користувача або створити її
        raise HTTPException(status_code=500, detail="Помилка авторизації (можливо, відсутня таблиця operator_passwords)")

@app.delete("/api/delete_drone/{id}")
async def delete_drone(id: int):
    try:
        supabase.table("drones").delete().eq("id", id).execute()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/add_flight")
async def add_flight(entry: FlightEntry):
    try:
        data = entry.dict()
        # Нормалізація імені оператора перед збереженням
        data["operator"] = normalize_operator_name(data.get("operator", ""))
        
        if entry.result == "Польоти не здійснювались":
            data["duration"] = 0
            data["distance"] = 0
            data["battery_cycles"] = 0
        else:
            data["duration"] = str(calculate_duration(entry.takeoff, entry.landing))
        if "id" in data: del data["id"]
        res = supabase.table("flights").insert(data).execute()
        return {"status": "success", "data": res.data}
    except Exception as e:
        print(f"Database Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/publish_with_telegram")
async def publish_report(report_text: str = Form(...), images: List[UploadFile] = File(None)):
    try:
        async with httpx.AsyncClient() as client:
            if not images:
                await client.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                    data={"chat_id": TELEGRAM_CHAT_ID, "text": report_text, "parse_mode": "HTML"}
                )
            else:
                media = []
                files = {}
                if images:
                    for i, img in enumerate(images):
                        file_id = f"pic{i}"
                    img_content = await img.read()
                    files[file_id] = (img.filename, img_content)
                    
                    media_item = {
                        "type": "photo",
                        "media": f"attach://{file_id}",
                        "parse_mode": "HTML"
                    }
                    if i == 0:
                        media_item["caption"] = report_text
                    media.append(media_item)

                await client.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMediaGroup",
                    data={"chat_id": TELEGRAM_CHAT_ID, "media": json.dumps(media)},
                    files=files
                )
        return {"status": "ok"}
    except Exception as e:
        print(f"Telegram API Error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/get_options")
async def get_options():
    return {
        "units": UNITS, 
        "weather": ["Нормальні", "Складні умови", "Несприятливі умови"], 
        "flight_modes": ["Normal", "АТТІ"], 
        "results": ["Без ознак порушення", "Затримання", "Польоти не здійснювались"]
    }

@app.get("/api/get_all_flights")
async def get_all_flights():
    all_data = []
    limit = 1000
    start = 0
    while True:
        res = supabase.table("flights").select("*").order("id", desc=True).range(start, start + limit - 1).execute()
        batch = res.data
        if not batch: break
        all_data.extend(batch)
        if len(batch) < limit: break
        start += limit
    return all_data

@app.delete("/api/delete_flight/{id}")
async def delete_flight(id: int):
    supabase.table("flights").delete().eq("id", id).execute()
    return {"status": "deleted"}

# --- PAGE ROUTES ---
@app.get("/")
async def read_index(): return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
@app.get("/dashboard")
async def read_dashboard(): return FileResponse(os.path.join(FRONTEND_DIR, "dashboard.html"))
@app.get("/request")
async def read_request(): return FileResponse(os.path.join(FRONTEND_DIR, "request.html"))
@app.get("/admin")
async def read_admin(): return FileResponse(os.path.join(FRONTEND_DIR, "admin.html"))
@app.get("/analytics")
async def read_analytics(): return FileResponse(os.path.join(FRONTEND_DIR, "analytics.html"))
@app.get("/report")
async def read_report():
    return FileResponse(
        os.path.join(FRONTEND_DIR, "report.html"),
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )
@app.get("/handbook")
async def read_handbook(): return FileResponse(os.path.join(FRONTEND_DIR, "handbook.html"))
@app.get("/fleet")
async def read_fleet(): return FileResponse(os.path.join(FRONTEND_DIR, "fleet_management.html"))
@app.get("/admin_analytics")
async def read_admin_analytics(): return FileResponse(os.path.join(FRONTEND_DIR, "admin_analytics.html"))
@app.get("/support")
async def read_support(): return FileResponse(os.path.join(FRONTEND_DIR, "support.html"))
@app.get("/xxx")
async def read_xxx(): return FileResponse(os.path.join(FRONTEND_DIR, "xxx.html"))

# --- 9. API для ШІ-чату з Інтеграцією Google Maps та Weather API ---
class ChatMessage(BaseModel):
    message: str

@app.post("/api/chat")
async def chat_with_ai(message: str = Form(...), image: Optional[UploadFile] = File(None)):
    user_msg = message.strip()
    
    # 1. Пошук координат у повідомленні (формат 48.4647, 35.0461)
    coords_match = re.search(r"(\d{2}\.\d{3,})[,\s]+(\d{2}\.\d{3,})", user_msg)
    
    context_addon = ""
    if coords_match:
        lat, lon = coords_match.groups()
        google_api_key = os.environ.get("GOOGLE_API_KEY") # ПЕРЕКОНАЙТЕСЬ, ЩО ТУТ НОВИЙ КЛЮЧ
        
        try:
            async with httpx.AsyncClient() as client:
                location_info = "Не визначено"
                msl_info = "Не визначено"
                nearby_places = "Не знайдено"
                
                if google_api_key:
                    # 1. Пряма адреса (Geocoding)
                    geo_url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={lat},{lon}&key={google_api_key}&language=uk"
                    geo_res = await client.get(geo_url)
                    if geo_res.status_code == 200:
                        geo_data = geo_res.json()
                        if geo_data.get("results"):
                            location_info = geo_data["results"][0].get("formatted_address", "Невідома місцевість")

                    # 2. Висота над рівнем моря MSL (Elevation API)
                    elev_url = f"https://maps.googleapis.com/maps/api/elevation/json?locations={lat},{lon}&key={google_api_key}"
                    elev_res = await client.get(elev_url)
                    if elev_res.status_code == 200:
                        elev_data = elev_res.json()
                        if elev_data.get("results"):
                            msl_info = f"{round(elev_data['results'][0].get('elevation', 0))} м"

                    # 3. Найближчі орієнтири (Places API - прибрано жорсткі фільтри для кращого пошуку)
                    places_url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={lat},{lon}&radius=5000&key={google_api_key}&language=uk"
                    places_res = await client.get(places_url)
                    if places_res.status_code == 200:
                        places_data = places_res.json()
                        places_list = [p.get("name") for p in places_data.get("results", [])[:5]]
                        if places_list:
                            nearby_places = ", ".join(places_list)

                # 4. Погода (Додано вологість та витягування напрямку вітру)
                weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,wind_gusts_10m&wind_speed_unit=ms&timezone=auto"
                w_res = await client.get(weather_url)
                weather_info = "Дані недоступні"
                if w_res.status_code == 200:
                    w_data = w_res.json().get("current", {})
                    temp = w_data.get("temperature_2m", "-")
                    hum = w_data.get("relative_humidity_2m", "-")
                    wind = w_data.get("wind_speed_10m", "-")
                    gusts = w_data.get("wind_gusts_10m", "-")
                    wind_dir = w_data.get("wind_direction_10m", "-")
                    weather_info = f"Температура: {temp}°C, Вологість: {hum}%, Вітер: {wind} м/с (пориви {gusts} м/с), Напрямок вітру: {wind_dir}°"

                # 5. Магнітні бурі (K-index) з офіційного API NOAA (США)
                k_index = "Невідомо"
                try:
                    noaa_url = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
                    noaa_res = await client.get(noaa_url, timeout=3.0)
                    if noaa_res.status_code == 200:
                        noaa_data = noaa_res.json()
                        if len(noaa_data) > 1:
                            k_index = noaa_data[-1][1] # Беремо найсвіжіший Kp індекс
                except Exception as e:
                    print(f"NOAA K-index Error: {e}")

                now_date = datetime.now().strftime("%d.%m.%Y")
                now_time = datetime.now().strftime("%H:%M")
                
                # Додаток до промпту: ЖОРСТКІ ІНСТРУКЦІЇ
                context_addon = f"""
                
                [СИСТЕМА: ВИЯВЛЕНО КООРДИНАТИ {lat}, {lon}. НАДАЮ АВТОМАТИЧНІ ДАНІ]
                - Топографія: Адреса: {location_info}. Висота MSL: {msl_info}. Орієнтири (5км): {nearby_places}.
                - Метео: {weather_info}. K-index: {k_index}.
                
                ІНСТРУКЦІЯ ДЛЯ ШІ ЩОДО ФОРМАТУВАННЯ ЗВІТУ:
                1. РЕЛЬЄФ: Якщо рельєф не вказано прямо, проаналізуй висоту {msl_info} та адресу і зроби логічний висновок (напр. "Рівнина", "Височина", "Міська забудова"). НЕ ПИШИ "Дані відсутні".
                2. НАПРЯМОК ВІТРУ: Конвертуй азимут вітру в сторони світу (Пн, Пд, Зх, Сх) і вкажи, куди буде зносити дрон (ЗНЕСЕННЯ ATTI).
                3. Заповни всі дані без винятків.
                """
        except Exception as e:
            print(f"API Fetch Error: {e}")

    # Збираємо фінальний текст для ШІ
    final_prompt = user_msg + context_addon

    system_prompt = os.environ.get("AI_SYSTEM_PROMPT", "Ти — терміновий технічний асистент та інструктор із БпЛА (DJI, Autel), РЕБ/РЕР. Твій пріоритет — миттєва допомога оператору. ПРАВИЛА: 1. Пиши коротко, без довгих вступів. 2. Надавай чіткий алгоритм дій. 3. Аналізуй локації та погоду для планування маршрутів, якщо користувач надсилає координати.")
    
    async def generate_response():
        try:
            if not ai_client:
                yield "Дякую за запитання! Будь ласка, налаштуйте API-ключ Gemini у файлі .env."
                return

            contents = []
            
            # 1. Додаємо всі PDF-мануали з бази знань
            if knowledge_files_cache:
                contents.extend(knowledge_files_cache)
                
            # 2. Додаємо сам запит користувача з координатами
            contents.append(final_prompt)
            if image:
                image_bytes = await image.read()
                contents.append(types.Part.from_bytes(data=image_bytes, mime_type=image.content_type))
            
            model_name = os.environ.get("GEMINI_MODEL_NAME", "gemini-flash-latest")
            
            # Вмикаємо функцію Grounding (пошук в Google), як ви і вказали
            ai_config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=[{"google_search": {}}]
            )
            
            try:
                response = await ai_client.aio.models.generate_content_stream(
                    model=model_name,
                    contents=contents,
                    config=ai_config
                )
                async for chunk in response:
                    if chunk.text:
                        yield chunk.text
            except Exception as e:
                print(f"Primary Model Error: {e}")
                # Fallback без Grounding, якщо API Google перевантажено
                fallback_config = types.GenerateContentConfig(system_instruction=system_prompt)
                response = await ai_client.aio.models.generate_content_stream(
                    model="gemini-2.0-flash-lite",
                    contents=contents,
                    config=fallback_config
                )
                async for chunk in response:
                    if chunk.text:
                        yield chunk.text
        except Exception as e:
            print(f"AI Stream Error: {e}")
            yield "Сервіс ШІ тимчасово недоступний (високе навантаження або вичерпано ліміти)."

    return StreamingResponse(generate_response(), media_type="text/plain")

class DocxRequest(BaseModel):
    text: str
    filename: str

@app.post("/api/generate_docx")
async def generate_docx(report_data: str = Form(...), filename: str = Form(...)):
    try:
        data = json.loads(report_data)
        doc = Document()
        
        # --- Налаштування шрифту (Times New Roman, 12pt) ---
        style = doc.styles['Normal']
        font = style.font
        font.name = 'Times New Roman'
        font.size = Pt(12)
        
        # Виправлення для відображення назви шрифту в Word
        r = style.element.rPr.rFonts
        r.set(qn('w:ascii'), 'Times New Roman')
        r.set(qn('w:hAnsi'), 'Times New Roman')

        # 1. Шапка документа
        header = doc.add_paragraph()
        header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        header.add_run(data.get('header', "Начальнику відділу організації повітряної розвідки\nта протидії безпілотним повітряним суднам штабу\nпідполковнику            Армену МКРТЧЯН"))

        # 2. Назва документа
        title = doc.add_paragraph()
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_run = title.add_run("\nДОНЕСЕННЯ ПРО ПОЛІТ")
        title_run.bold = True

        # 3. БАЗОВІ ДАНІ
        doc.add_paragraph(f"Дата вильотів : {data.get('date', '__.__.____')}")
        doc.add_paragraph(f"Ділянка : {data.get('unit', '___')}")
        doc.add_paragraph("Вильоти:")

        # 4. ТАБЛИЦЯ ПОЛЬОТІВ
        flights = data.get('flights', [])
        table = doc.add_table(rows=1, cols=4)
        table.style = 'Table Grid'
        
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = 'Прізвище екіпажу'
        hdr_cells[1].text = 'К-сть'
        hdr_cells[2].text = 'Тип БпАК'
        hdr_cells[3].text = 'Час та дистанція вильотів'
        
        if not flights:
            row_cells = table.add_row().cells
            row_cells[0].text = 'Немає даних'
            row_cells[1].text = '0'
            row_cells[2].text = '-'
            row_cells[3].text = '-'
        else:
            for flight in flights:
                row_cells = table.add_row().cells
                row_cells[0].text = flight.get('operator', '')
                row_cells[1].text = str(flight.get('count', ''))
                row_cells[2].text = flight.get('drone', '')
                row_cells[3].text = flight.get('details', '')

        # 5. МАРШРУТ ТА ЕКІПАЖ
        doc.add_paragraph(f"\n Маршрут : {data.get('route', '___')}")
        doc.add_paragraph(f"БпАК  : {data.get('drones_list', '___')}")
        doc.add_paragraph("Склад екіпажу:")
        doc.add_paragraph(f"командир зовнішнього екіпажу: {data.get('commander', '___')};")
        doc.add_paragraph(f"оператор: {data.get('operators', '___')}.")
        
        # 6. РЕЗУЛЬТАТИ
        doc.add_paragraph("Результати:")
        doc.add_paragraph(data.get('result', "Під час польотів порушень ОПДК не виявлено."))

        # 7. ФОТОФІКСАЦІЯ (ЯКЩО Є ФОТО)
        photo_b64 = data.get('photo')
        temp_photo_path = None
        if photo_b64 and photo_b64.startswith('data:image'):
            try:
                import base64
                header_data, encoded = photo_b64.split(",", 1)
                photo_data = base64.b64decode(encoded)
                temp_photo_path = os.path.join("app", f"{uuid.uuid4()}.jpg")
                with open(temp_photo_path, "wb") as f:
                    f.write(photo_data)
                
                pic_para = doc.add_paragraph()
                pic_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                pic_para.add_run().add_picture(temp_photo_path, width=Cm(15))
            except Exception as e:
                print(f"Помилка завантаження фото: {e}")

        # 8. ЗВ'ЯЗОК
        doc.add_paragraph("\nЗв'язок на кордоні підтримувався :")
        doc.add_paragraph(f"з ПН, ОЧ {data.get('unit', '___')} по р/ст. по радіомережі;")
        doc.add_paragraph("відео-, фотодокументування здійснювалися штатною апаратурою БпАК.")
        
        # 9. ПОГОДА ТА СТАН ТЕХНІКИ
        doc.add_paragraph(f"\nПогода по маршруту:  {data.get('weather', '___')}")
        doc.add_paragraph("Готовність екіпажу та стан БпАК: БпАК справний, недоліків у роботі техніки не виявлено.")
        doc.add_paragraph("Політ виконано в штатному режимі, відмов у системах керування та телеметрії не зафіксовано. Зауважень немає.")

        # 10. ПІДПИС
        doc.add_paragraph("\nДонесення склав")
        doc.add_paragraph("Командир зовнішнього екіпажу:")
        
        # Форматування підпису (Звання зліва, ПІБ справа)
        sign_text = data.get('commander_short', '___')
        doc.add_paragraph(sign_text)

        # Зберігаємо в тимчасовий файл
        temp_id = str(uuid.uuid4())
        temp_filepath = os.path.join("app", f"{temp_id}.docx")
        doc.save(temp_filepath)

        # Визначаємо безпечну назву файлу
        if not filename.lower().endswith(".docx"):
            filename += ".docx"
            
        def cleanup_temp_files(doc_path: str, photo_path: str = None):
            try:
                if os.path.exists(doc_path):
                    os.remove(doc_path)
                if photo_path and os.path.exists(photo_path):
                    os.remove(photo_path)
            except Exception as e:
                print(f"Error deleting temp files: {e}")

        from fastapi import BackgroundTasks
        background_tasks = BackgroundTasks()
        background_tasks.add_task(cleanup_temp_files, temp_filepath, temp_photo_path)

        encoded_filename = quote(filename)
        safe_ascii = "report.docx"

        return FileResponse(
            path=temp_filepath,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            background=background_tasks,
            headers={
                "Content-Disposition": f"attachment; filename=\"{safe_ascii}\"; filename*=UTF-8''{encoded_filename}"
            }
        )
    except Exception as e:
        print(f"DOCX Generation Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
