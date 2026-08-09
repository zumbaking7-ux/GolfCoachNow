import os
import tempfile
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from wedge import process_mobile_input, CORRECTIONS
from video_analyzer import analyze_video, VideoAnalysisError

app = FastAPI(
    title="GolfCoachNow API",
    description="Wedge Engine — Golf Swing Correction Service",
    version="2.0.0",
)

ALLOWED_EXTENSIONS = {"mp4", "mov", "avi", "m4v"}
MAX_FILE_SIZE = 16 * 1024 * 1024


class SwingData(BaseModel):
    data: dict


@app.get("/")
def health():
    return {"status": "ok", "service": "GolfCoachNow API"}


@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "No file provided")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Invalid file type. Accepted: {', '.join(ALLOWED_EXTENSIONS)}")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(413, "File too large. Maximum 16MB")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix="." + ext)
    tmp_path = tmp.name
    try:
        tmp.write(contents)
        tmp.close()
        scores = analyze_video(tmp_path)
        result = process_mobile_input(scores)
        return result
    except VideoAnalysisError as e:
        raise HTTPException(400, str(e))
    except Exception:
        raise HTTPException(500, "Video analysis failed")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@app.post("/wedge")
def run_wedge(swing: SwingData):
    result = process_mobile_input(swing.data)
    return result
