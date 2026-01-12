from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
import os
from dotenv import load_dotenv

# Імпортуємо наш блок логіки
from app.core.logic import calculate_duration

load_dotenv()

app = FastAPI(title="UAV Cabinet NextGen")

supabase: Client = create_client(
    os.environ.get("SUPABASE_URL"), 
    os.environ.get("SUPABASE_KEY")
)

class FlightEntry(BaseModel):
    date: str
    operator: str
    unit: str
    drone: str
    takeoff: str
    landing: str
    result: str = "Без ознак порушення"

@app.post("/add_flight")
async def add_flight(entry: FlightEntry):
    flight_time = calculate_duration(entry.takeoff, entry.landing)
    
    new_record = {
        **entry.dict(),
        "duration": flight_time
    }

    try:
        response = supabase.table("flights").insert(new_record).execute()
        return {"status": "success", "duration": flight_time}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
