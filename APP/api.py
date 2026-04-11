from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from research import research   # your function
from dotenv import load_dotenv
load_dotenv()
app = FastAPI()

class QueryRequest(BaseModel):
    query: str
    websites: Optional[List[str]] = None


@app.post("/research")
def run_research(request: QueryRequest):
    result = research(request.query, request.websites)
    return result