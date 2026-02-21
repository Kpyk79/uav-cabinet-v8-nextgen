import os
import httpx
import json
import re
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Form, UploadFile, File, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv
from google import genai
from google.genai import types

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
    'віпс "Павлівка"', 'впс "Велика Михайлівка"', 'віпс "Слов\'яносербка"', 
    'віпс "Гребеники"', 'впс "Степанівка"', 'віпс "Лучинське"', 
    'віпс "Кучурган"', 'віпс "Лиманське"', "Група ВОПРтаПБпПС", "ВЗФБпАКтаЗПБпС"
]

@app.on_event("startup")
async def startup_event():
    global knowledge_files_cache
    if not ai_client: 
        print("API ключ Gemini не знайдено. База знань не завантажена.")
        return
        
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
                    print(f"Завантаження {filename} до Gemini...")
                    uploaded_file = ai_client.files.upload(file=file_path, config={'display_name': filename})
                    knowledge_files_cache.append(uploaded_file)
                    
        print(f"База знань готова! Активних документів: {len(knowledge_files_cache)}")
    except Exception as e:
        print(f"Помилка ініціалізації бази знань: {e}")

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

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
