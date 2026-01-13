import os
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv

# Завантаження змінних оточення (URL та KEY для Supabase)
load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app = FastAPI(title="UAV Command System v8.8")

# Налаштування CORS для доступу з різних пристроїв
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Підключення до бази даних Supabase
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
if not URL or not KEY:
    print("ПОМИЛКА: Перевірте наявність SUPABASE_URL та SUPABASE_KEY у файлі .env")

supabase: Client = create_client(URL, KEY)

# СТРОЙОВА ЗАПИСКА (Список підрозділів у вашій черзі)
UNITS = [
    'впс "Кодима"', 'віпс "Загнітків"', 'віпс "Шершенці"', 'впс "Станіславка"', 
    'віпс "Тимкове"', 'віпс "Чорна"', 'впс "Окни"', 'віпс "Ткаченкове"', 
    'віпс "Гулянка"', 'віпс "Новосеменівка"', 'впс "Великокомарівка"', 
    'віпс "Павлівка"', 'впс "Велика Михайлівка"', 'віпс "Слов\'яносербка"', 
    'віпс "Гребеники"', 'впс "Степанівка"', 'віпс "Лучинське"', 
    'віпс "Кучурган"', 'віпс "Лиманське"', "УПЗ"
]

# Модель даних для прийому польоту
class FlightEntry(BaseModel):
    date: str
    shift_time: str
    operator: str
    unit: str
    drone: str
    route: str
    takeoff: str
    landing: str
    distance: int
    battery_id: str
    battery_cycles: int
    mission_type: str
    conditions: str
    result: str
    notes: str = ""

# Допоміжна функція розрахунку часу
def calculate_duration(t1_str, t2_str):
    try:
        fmt = "%H:%M"
        t1 = datetime.strptime(t1_str, fmt)
        t2 = datetime.strptime(t2_str, fmt)
        delta = t2 - t1
        mins = int(delta.total_seconds() / 60)
        # Якщо посадка на наступну добу (напр. 23:50 -> 00:20)
        return mins if mins > 0 else mins + 1440
    except:
        return 0

# --- API ENDPOINTS ---

@app.get("/api/get_options")
async def get_options():
    """Повертає списки для випадаючих вікон форми"""
    return {
        "units": UNITS,
        "weather": ["Нормальні", "Складні погодні умови", "Несприятливі погодні умови"],
        "flight_modes": ["Норма", "Політ в АТТІ"],
        "results": ["Без ознак порушення", "Затримання"]
    }

@app.get("/api/get_unit_drones")
async def get_unit_drones(unit: str):
    """Отримує список БпЛА, закріплених за конкретним підрозділом"""
    try:
        res = supabase.table("drones").select("model, serial_number").eq("unit", unit).execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/get_my_flights")
async def get_my_flights(unit: str, operator: str):
    """Отримує польоти тільки для поточного оператора (для Журналу)"""
    try:
        res = supabase.table("flights")\
            .select("*")\
            .eq("unit", unit)\
            .eq("operator", operator)\
            .order("id", desc=True)\
            .execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/add_flight")
async def add_flight(entry: FlightEntry):
    """Додає новий політ у базу даних"""
    dur = calculate_duration(entry.takeoff, entry.landing)
    data = {**entry.dict(), "duration": dur}
    try:
        supabase.table("flights").insert(data).execute()
        return {"status": "success", "duration": dur}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Insert failed: {str(e)}")

@app.delete("/api/delete_flight/{f_id}")
async def delete_f(f_id: int):
    """Видаляє конкретний запис із Журналу"""
    try:
        supabase.table("flights").delete().eq("id", f_id).execute()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- СТАТИЧНІ ФАЙЛИ ---

# Монтуємо папку з фронтендом
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
async def read_index():
    """Головна сторінка входу та форми"""
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/dashboard")
async def read_dashboard():
    """Сторінка Журналу польотів"""
    return FileResponse(os.path.join(FRONTEND_DIR, "dashboard.html"))
