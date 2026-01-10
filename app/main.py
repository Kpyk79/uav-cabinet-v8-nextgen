from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv() # Завантажує секретні ключі з файлу .env

app = FastAPI(title="UAV Cabinet NextGen API")

# Налаштування зв'язку з базою
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# Модель даних (ваша валідація)
class FlightEntry(BaseModel):
    date: str
    operator: str
    unit: str
    drone: str
    takeoff: str
    landing: str
    result: str = "Без ознак порушення"

@app.get("/")
async def root():
    return {"message": "Система активована. Мозок працює!"}

@app.post("/add_flight")
async def add_flight(entry: FlightEntry):
    # Тут ми пізніше додамо ваш розумний розрахунок тривалості
    # Поки що просто відправляємо дані
    try:
        data = supabase.table("flights").insert(entry.dict()).execute()
        return {"status": "success", "data": data.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
