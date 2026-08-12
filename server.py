import json
import os
import tempfile
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
from wedge import process_mobile_input as wedge_process, CORRECTIONS as WEDGE_CORRECTIONS
from putt import process_mobile_input as putt_process, CORRECTIONS as PUTT_CORRECTIONS
from chip import process_mobile_input as chip_process, CORRECTIONS as CHIP_CORRECTIONS
from video_analyzer import analyze_video, VideoAnalysisError
from talk import process_talk

try:
    from payments.routes import router as payments_router
    from payments.db import get_session
    from payments.entitlement import check_entitlement, record_usage
    from payments.models import AnalyticsEvent, RepResult
    from sqlalchemy.orm import Session
    from sqlalchemy import func, select
    _has_payments = True
except ImportError:
    payments_router = None
    _has_payments = False

app = FastAPI(
    title="GolfCoachNow API",
    description="Golf Coaching Platform — Swing, Putt, and Short Game Analysis",
    version="3.0.0",
)

MODULE_ENGINES = {
    "swing": wedge_process,
    "putt": putt_process,
    "short_game": chip_process,
}

VALID_MODULES = frozenset(MODULE_ENGINES.keys())

if payments_router is not None:
    app.include_router(payments_router)

ALLOWED_EXTENSIONS = {"mp4", "mov", "avi", "m4v"}
MAX_FILE_SIZE = 16 * 1024 * 1024


class SwingData(BaseModel):
    data: dict
    device_id: str = ""


class TalkRequest(BaseModel):
    text: str
    module: str = "swing"
    device_id: str = ""


class AnalyticsEventRequest(BaseModel):
    device_id: str
    event_name: str
    module: Optional[str] = None
    platform: Optional[str] = None
    payload: Optional[dict] = None


@app.get("/")
def health():
    return {"status": "ok", "service": "GolfCoachNow API"}


@app.get("/entitlement")
def get_entitlement(
    device_id: str = Query(...),
    module: str = Query("swing"),
):
    if module not in VALID_MODULES:
        raise HTTPException(400, f"Invalid module. Options: {', '.join(VALID_MODULES)}")

    if not _has_payments:
        return {
            "allowed": True,
            "is_subscriber": False,
            "reps_used": 0,
            "reps_remaining": -1,
            "daily_limit": -1,
        }

    db = next(get_session())
    try:
        status = check_entitlement(db, device_id, module)
        return {
            "allowed": status.allowed,
            "is_subscriber": status.is_subscriber,
            "reps_used": status.reps_used,
            "reps_remaining": status.reps_remaining,
            "daily_limit": status.daily_limit,
        }
    finally:
        db.close()


def _save_result(device_id: str, module: str, result: dict):
    if not _has_payments or not device_id:
        return
    fault = result.get("dominant_fault")
    if not fault:
        return
    db = next(get_session())
    try:
        db.add(RepResult(
            device_id=device_id,
            module=module,
            dominant_fault=fault,
            correction=result.get("correction") or "",
            scores_json=json.dumps(result.get("normalized_scores", {})),
        ))
        db.commit()
    finally:
        db.close()


def _check_and_record(device_id: str, module: str):
    if not _has_payments:
        return
    if not device_id:
        raise HTTPException(400, "device_id is required")
    db = next(get_session())
    try:
        status = record_usage(db, device_id, module)
        if not status.allowed:
            raise HTTPException(
                403,
                {
                    "error": "daily_limit_reached",
                    "message": f"You have used all {status.daily_limit} free reps for {module} today. Subscribe for unlimited access.",
                    "reps_used": status.reps_used,
                    "daily_limit": status.daily_limit,
                },
            )
    finally:
        db.close()


@app.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    module: str = "swing",
    device_id: str = "",
):
    if module not in VALID_MODULES:
        raise HTTPException(400, f"Invalid module. Options: {', '.join(VALID_MODULES)}")

    _check_and_record(device_id, module)

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
        engine = MODULE_ENGINES.get(module, wedge_process)
        result = engine(scores)
        _save_result(device_id, module, result)
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
    _check_and_record(swing.device_id, "swing")
    result = wedge_process(swing.data)
    _save_result(swing.device_id, "swing", result)
    return result


@app.post("/putt")
def run_putt(swing: SwingData):
    _check_and_record(swing.device_id, "putt")
    result = putt_process(swing.data)
    _save_result(swing.device_id, "putt", result)
    return result


@app.post("/short-game")
def run_short_game(swing: SwingData):
    _check_and_record(swing.device_id, "short_game")
    result = chip_process(swing.data)
    _save_result(swing.device_id, "short_game", result)
    return result


@app.post("/talk")
def talk_mode(req: TalkRequest):
    if req.module not in VALID_MODULES:
        raise HTTPException(400, f"Invalid module. Options: {', '.join(VALID_MODULES)}")
    _check_and_record(req.device_id, req.module)
    return process_talk(req.text, req.module)


@app.post("/analytics/event")
def track_event(event: AnalyticsEventRequest):
    if not _has_payments:
        return {"status": "ok"}

    db = next(get_session())
    try:
        db.add(AnalyticsEvent(
            device_id=event.device_id,
            event_name=event.event_name,
            module=event.module,
            platform=event.platform,
            payload=json.dumps(event.payload) if event.payload else None,
        ))
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()


@app.post("/analytics/batch")
def track_events_batch(events: list[AnalyticsEventRequest]):
    if not _has_payments:
        return {"status": "ok", "count": len(events)}

    db = next(get_session())
    try:
        for event in events:
            db.add(AnalyticsEvent(
                device_id=event.device_id,
                event_name=event.event_name,
                module=event.module,
                platform=event.platform,
                payload=json.dumps(event.payload) if event.payload else None,
            ))
        db.commit()
        return {"status": "ok", "count": len(events)}
    finally:
        db.close()


@app.get("/analytics/summary")
def analytics_summary(days: int = Query(7, ge=1, le=90)):
    if not _has_payments:
        return {"error": "analytics not available"}

    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    db = next(get_session())
    try:
        events_by_name = db.execute(
            select(AnalyticsEvent.event_name, func.count())
            .where(AnalyticsEvent.created_at >= cutoff)
            .group_by(AnalyticsEvent.event_name)
        ).all()

        events_by_module = db.execute(
            select(AnalyticsEvent.module, func.count())
            .where(AnalyticsEvent.created_at >= cutoff, AnalyticsEvent.module.isnot(None))
            .group_by(AnalyticsEvent.module)
        ).all()

        unique_devices = db.scalar(
            select(func.count(func.distinct(AnalyticsEvent.device_id)))
            .where(AnalyticsEvent.created_at >= cutoff)
        )

        total_events = db.scalar(
            select(func.count()).select_from(AnalyticsEvent)
            .where(AnalyticsEvent.created_at >= cutoff)
        )

        return {
            "period_days": days,
            "total_events": total_events or 0,
            "unique_devices": unique_devices or 0,
            "events_by_name": {name: count for name, count in events_by_name},
            "events_by_module": {mod: count for mod, count in events_by_module},
        }
    finally:
        db.close()


@app.get("/performance/history")
def performance_history(
    device_id: str = Query(...),
    module: str = Query("swing"),
    limit: int = Query(20, ge=1, le=100),
):
    if not _has_payments:
        return {"results": []}

    db = next(get_session())
    try:
        results = db.execute(
            select(RepResult)
            .where(RepResult.device_id == device_id, RepResult.module == module)
            .order_by(RepResult.created_at.desc())
            .limit(limit)
        ).scalars().all()

        return {
            "device_id": device_id,
            "module": module,
            "count": len(results),
            "results": [
                {
                    "id": r.id,
                    "dominant_fault": r.dominant_fault,
                    "correction": r.correction,
                    "scores": json.loads(r.scores_json),
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in results
            ],
        }
    finally:
        db.close()


@app.get("/performance/trends")
def performance_trends(
    device_id: str = Query(...),
    module: str = Query("swing"),
    days: int = Query(30, ge=1, le=90),
):
    if not _has_payments:
        return {"trends": {}}

    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    db = next(get_session())
    try:
        fault_counts = db.execute(
            select(RepResult.dominant_fault, func.count())
            .where(
                RepResult.device_id == device_id,
                RepResult.module == module,
                RepResult.created_at >= cutoff,
            )
            .group_by(RepResult.dominant_fault)
            .order_by(func.count().desc())
        ).all()

        total_reps = db.scalar(
            select(func.count()).select_from(RepResult)
            .where(
                RepResult.device_id == device_id,
                RepResult.module == module,
                RepResult.created_at >= cutoff,
            )
        )

        return {
            "device_id": device_id,
            "module": module,
            "period_days": days,
            "total_reps": total_reps or 0,
            "fault_frequency": {fault: count for fault, count in fault_counts},
            "top_fault": fault_counts[0][0] if fault_counts else None,
        }
    finally:
        db.close()


@app.get("/performance/stats")
def performance_stats(device_id: str = Query(...)):
    if not _has_payments:
        return {"modules": {}}

    db = next(get_session())
    try:
        module_counts = db.execute(
            select(RepResult.module, func.count())
            .where(RepResult.device_id == device_id)
            .group_by(RepResult.module)
        ).all()

        modules = {}
        for mod, count in module_counts:
            top_fault_row = db.execute(
                select(RepResult.dominant_fault, func.count().label("cnt"))
                .where(RepResult.device_id == device_id, RepResult.module == mod)
                .group_by(RepResult.dominant_fault)
                .order_by(func.count().desc())
                .limit(1)
            ).first()

            last_rep = db.execute(
                select(RepResult.created_at)
                .where(RepResult.device_id == device_id, RepResult.module == mod)
                .order_by(RepResult.created_at.desc())
                .limit(1)
            ).scalar()

            modules[mod] = {
                "total_reps": count,
                "top_fault": top_fault_row[0] if top_fault_row else None,
                "last_rep_at": last_rep.isoformat() if last_rep else None,
            }

        return {
            "device_id": device_id,
            "modules": modules,
            "total_reps": sum(c for _, c in module_counts),
        }
    finally:
        db.close()
