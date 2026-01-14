import os
import httpx
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException, Form, UploadFile, File, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Визначаємо шлях до папки з фронтендом
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app = FastAPI(title="UAV Command System v10.2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Telegram Config
TELEGRAM_TOKEN = "8532620253:AAEY7ug33Ru6VS4EZeXQPqOPiMx3fB49y-Q"
TELEGRAM_CHAT_ID = "627363301"

# Supabase Config
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(URL, KEY)

UNITS = ['впс "Кодима"', 'віпс "Загнітків"', 'віпс "Шершенці"', 'впс "Станіславка"', 'віпс "Тимкове"', 'віпс "Чорна"', 'впс "Окни"', 'віпс "Ткаченкове"', 'віпс "Гулянка"', 'віпс "Новосеменівка"', 'впс "Великокомарівка"', 'віпс "Павлівка"', 'впс "Велика Михайлівка"', 'віпс "Слов\'яносербка"', 'віпс "Гребеники"', 'впс "Степанівка"', 'віпс "Лучинське"', 'віпс "Кучурган"', 'віпс "Лиманське"', "УПЗ"]

class FlightEntry(BaseModel):
    date: str; shift_time: str; operator: str; unit: str; drone: str; route: str; takeoff: str; landing: str; distance: int; battery_id: str; battery_cycles: int; mission_type: str; conditions: str; result: str; notes: str = ""

# --- API МАРШРУТИ ---

@app.post("/api/publish_with_telegram")
async def publish_with_telegram(report_text: str = Form(...), images: list[UploadFile] = File(None)):
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            if images and len(images) > 0:
                files = {}
                media_list = []
                for i, img in enumerate(images):
                    content = await img.read()
                    name = f"pic_{i}"
                    files[name] = (img.filename, content, img.content_type)
                    media_item = {"type": "photo", "media": f"attach://{name}", "parse_mode": "HTML"}
                    if i == 0: media_item["caption"] = report_text
                    media_list.append(media_item)
                
                await client.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMediaGroup",
                    data={"chat_id": TELEGRAM_CHAT_ID, "media": json.dumps(media_list)},
                    files=files
                )
            else:
                await client.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                    data={"chat_id": TELEGRAM_CHAT_ID, "text": report_text, "parse_mode": "HTML"}
                )
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/add_flight")
async def add_flight(entry: FlightEntry):
    def calc_dur(t1, t2):
        try:
            fmt = "%H:%M"
            d = datetime.strptime(t2, fmt) - datetime.strptime(t1, fmt)
            m = int(d.total_seconds() / 60)
            return m if m > 0 else m + 1440
        except: return 0
    data = {**entry.dict(), "duration": calc_dur(entry.takeoff, entry.landing)}
    supabase.table("flights").insert(data).execute()
    return {"status": "success"}

@app.get("/api/get_options")
async def get_options():
    return {"units": UNITS, "weather": ["Нормальні", "Складні погодні умови", "Несприятливі погодні умови"], "flight_modes": ["Норма", "Політ в АТТІ"], "results": ["Без ознак порушення", "Затримання"]}

@app.get("/api/get_unit_drones")
async def get_unit_drones(unit: str):
    res = supabase.table("drones").select("model, serial_number").eq("unit", unit).execute()
    return res.data

@app.get("/api/get_my_flights")
async def get_my_flights(unit: str, operator: str):
    res = supabase.table("flights").select("*").eq("unit", unit).eq("operator", operator).order("id", desc=True).execute()
    return res.data

@app.get("/api/get_all_flights")
async def get_all_flights():
    res = supabase.table("flights").select("*").order("id", desc=True).execute()
    return res.data

# --- МАРШРУТИ ДЛЯ СТОРІНОК (HTML) ---

@app.get("/")
async def read_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/dashboard")
async def read_dashboard():
    return FileResponse(os.path.join(FRONTEND_DIR, "dashboard.html"))

@app.get("/admin")
async def read_admin():
    return FileResponse(os.path.join(FRONTEND_DIR, "admin.html"))

# Монтування статичних файлів (стилі, картинки) робимо В ОСТАННЮ ЧЕРГУ
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# --- НОВИЙ МАРШРУТ ДЛЯ ЗАЯВОК ---
@app.get("/request")
async def read_request():
    return FileResponse(os.path.join(FRONTEND_DIR, "request.html"))
