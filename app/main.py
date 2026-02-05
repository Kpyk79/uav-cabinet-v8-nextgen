import os
import httpx
import json
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Form, UploadFile, File, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv

# --- CONFIG & SETUP ---
load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app = FastAPI(title="UAV Command System v10.6")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8532620253:AAEY7ug33Ru6VS4EZeXQPqOPiMx3fB49y-Q")
TELEGRAM_CHAT_ID = "627363301"

URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")

if not URL or not KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env file")

supabase: Client = create_client(URL, KEY)

UNITS = [
    'впс "Кодима"', 'віпс "Загнітків"', 'віпс "Шершенці"', 'впс "Станіславка"', 
    'віпс "Тимкове"', 'віпс "Чорна"', 'впс "Окни"', 'віпс "Ткаченкове"', 
    'віпс "Гулянка"', 'віпс "Новосеменівка"', 'впс "Великокомарівка"', 
    'віпс "Павлівка"', 'впс "Велика Михайлівка"', 'віпс "Слов\'яносербка"', 
    'віпс "Гребеники"', 'впс "Степанівка"', 'віпс "Лучинське"', 
    'віпс "Кучурган"', 'віпс "Лиманське"', "Група ВОПРтаПБпПС"
]

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

# 1. Отримати оголошення
@app.get("/api/get_announcement")
async def get_announcement():
    res = supabase.table("app_settings").select("*").eq("id", 1).execute()
    if res.data:
        return res.data[0]
    return {"is_announcement_active": False, "announcement_text": ""}

# 2. Оновити оголошення
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

# 3. Отримати дрони підрозділу (ВИПРАВЛЕНО: Залишив версію з select("*"))
@app.get("/api/get_unit_drones")
async def get_unit_drones(unit: str = Query(...)):
    # Важливо брати *, щоб отримати ID та Status для адмінки флоту
    res = supabase.table("drones").select("*").eq("unit", unit).execute()
    return res.data

# 4. Оновити статус дрона
@app.post("/api/update_drone_status")
async def update_drone_status(data: StatusUpdate):
    try:
        res = supabase.table("drones").update({"status": data.status}).eq("id", data.id).execute()
        return {"status": "ok"}
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 5. Додати новий дрон
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

# 6. Видалити дрон
@app.delete("/api/delete_drone/{id}")
async def delete_drone(id: int):
    try:
        supabase.table("drones").delete().eq("id", id).execute()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 7. Додати політ
@app.post("/api/add_flight")
async def add_flight(entry: FlightEntry):
    try:
        data = entry.dict()
        data["duration"] = str(calculate_duration(entry.takeoff, entry.landing))
        if "id" in data: del data["id"]
        
        res = supabase.table("flights").insert(data).execute()
        return {"status": "success", "data": res.data}
    except Exception as e:
        print(f"Database Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 8. Телеграм публікація
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
        "flight_modes": ["Норма", "АТТІ"], 
        "results": ["Без ознак порушення", "Затримання", "Польоти не здійснювались"]
    }

@app.get("/api/get_my_flights")
async def get_my_flights(unit: str, operator: str):
    res = supabase.table("flights").select("*").eq("unit", unit).eq("operator", operator).order("id", desc=True).execute()
    return res.data

@app.get("/api/get_all_flights")
async def get_all_flights():
    res = supabase.table("flights").select("*").order("id", desc=True).execute()
    return res.data

@app.delete("/api/delete_flight/{id}")
async def delete_flight(id: int):
    supabase.table("flights").delete().eq("id", id).execute()
    return {"status": "deleted"}

# --- PAGE ROUTES ---

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

@app.get("/analytics")
async def read_analytics():
    return FileResponse(os.path.join(FRONTEND_DIR, "analytics.html"))

@app.get("/handbook")
async def read_handbook():
    return FileResponse(os.path.join(FRONTEND_DIR, "handbook.html"))

# ВИПРАВЛЕНО: залишено один правильний route
@app.get("/fleet")
async def read_fleet():
    return FileResponse(os.path.join(FRONTEND_DIR, "fleet_management.html"))

@app.get("/admin_analytics")
async def read_admin_analytics():
    return FileResponse(os.path.join(FRONTEND_DIR, "admin_analytics.html"))

@app.get("/xxx")
async def read_xxx():
    return FileResponse(os.path.join(FRONTEND_DIR, "xxx.html"))

# Підключаємо статику в кінці, щоб вона не перекривала API
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)

