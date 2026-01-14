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

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app = FastAPI(title="UAV Command System v10.5")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIG ---
# ВАЖЛИВО: Отримайте новий токен у @BotFather після витоку!
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8532620253:AAEY7ug33Ru6VS4EZeXQPqOPiMx3fB49y-Q")
TELEGRAM_CHAT_ID = "627363301"

URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(URL, KEY)

UNITS = ['впс "Кодима"', 'віпс "Загнітків"', 'віпс "Шершенці"', 'впс "Станіславка"', 'віпс "Тимкове"', 'віпс "Чорна"', 'впс "Окни"', 'віпс "Ткаченкове"', 'віпс "Гулянка"', 'віпс "Новосеменівка"', 'впс "Великокомарівка"', 'віпс "Павлівка"', 'впс "Велика Михайлівка"', 'віпс "Слов\'яносербка"', 'віпс "Гребеники"', 'впс "Степанівка"', 'віпс "Лучинське"', 'віпс "Кучурган"', 'віпс "Лиманське"', "УПЗ"]

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

def calculate_duration(t1: str, t2: str):
    try:
        # Очищаємо вхідні дані від можливих пробілів
        t1, t2 = t1.strip(), t2.strip()
        fmt = "%H:%M"
        start = datetime.strptime(t1, fmt)
        end = datetime.strptime(t2, fmt)
        diff = (end - start).total_seconds() / 60
        if diff < 0: diff += 1440  # якщо політ через північ
        return int(diff)
    except Exception as e:
        print(f"Duration calculation error: {e}")
        return 0 # повертаємо 0 замість вильоту програми

# --- API ROUTES ---

@app.post("/api/add_flight")
async def add_flight(entry: FlightEntry):
    try:
        data = entry.dict()
        # Розраховуємо тривалість і перетворюємо в рядок для бази
        duration_val = calculate_duration(entry.takeoff, entry.landing)
        data["duration"] = str(duration_val)
        
        # Видаляємо ID, щоб Supabase використав свій Identity
        if "id" in data: del data["id"]
        
        res = supabase.table("flights").insert(data).execute()
        return {"status": "success", "data": res.data}
    except Exception as e:
        print(f"CRITICAL DATABASE ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/publish_with_telegram")
async def publish_report(report_text: str = Form(...), images: list[UploadFile] = File(None)):
    try:
        # 1. Надсилаємо текст
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                data={"chat_id": TELEGRAM_CHAT_ID, "text": report_text}
            )
            
            # 2. Надсилаємо фото, якщо вони є
            if images:
                for img in images:
                    img_content = await img.read()
                    await client.post(
                        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
                        data={"chat_id": TELEGRAM_CHAT_ID},
                        files={"photo": (img.filename, img_content)}
                    )
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/get_options")
async def get_options():
    return {
        "units": UNITS, 
        "weather": ["Нормальні", "Складні погодні умови", "Несприятливі погодні умови"], 
        "flight_modes": ["Норма", "Політ в АТТІ"], 
        "results": ["Без ознак порушення", "Затримання"]
    }

@app.get("/api/get_unit_drones")
async def get_unit_drones(unit: str):
    res = supabase.table("drones").select("model, serial_number").eq("unit", unit).execute()
    return res.data

@app.get("/api/get_my_flights")
async def get_my_flights(unit: str, operator: str):
    # Отримуємо всі польоти оператора, сортуємо за ID (останні зверху)
    res = supabase.table("flights").select("*").eq("unit", unit).eq("operator", operator).order("id", desc=True).execute()
    return res.data

@app.delete("/api/delete_flight/{id}")
async def delete_flight(id: int):
    supabase.table("flights").delete().eq("id", id).execute()
    return {"status": "deleted"}

# --- СТОРІНКИ ---

@app.get("/")
async def read_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/dashboard")
async def read_dashboard():
    return FileResponse(os.path.join(FRONTEND_DIR, "dashboard.html"))

@app.get("/request")
async def read_request():
    return FileResponse(os.path.join(FRONTEND_DIR, "request.html"))

@app.get("/admin")
async def read_admin():
    return FileResponse(os.path.join(FRONTEND_DIR, "admin.html"))

@app.get("/api/get_all_flights")
async def get_all_flights():
    # Отримуємо ВСІ записи без фільтрації по оператору
    res = supabase.table("flights").select("*").order("id", desc=True).execute()
    return res.data

# Підключення статики (CSS, JS)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
