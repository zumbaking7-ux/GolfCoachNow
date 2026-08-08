from fastapi import FastAPI
from pydantic import BaseModel
from wedge import process_mobile_input

app = FastAPI()

class SwingData(BaseModel):
    data: dict

@app.post("/wedge")
def run_wedge(swing: SwingData):
    result = process_mobile_input(swing.data)
    return result
