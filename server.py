import json
import os
import tempfile
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Query
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel, Field
from typing import Optional
from wedge import process_mobile_input as wedge_process, CORRECTIONS as WEDGE_CORRECTIONS
from putt import process_mobile_input as putt_process, CORRECTIONS as PUTT_CORRECTIONS
from chip import process_mobile_input as chip_process, CORRECTIONS as CHIP_CORRECTIONS
from video_analyzer import analyze_video, VideoAnalysisError
from talk import process_talk

try:
    from payments.routes import router as payments_router
    from payments.auth_routes import router as auth_router
    from payments.db import get_session
    from payments.entitlement import check_entitlement, record_usage
    from payments.models import AnalyticsEvent, RepResult
    from sqlalchemy.orm import Session
    from sqlalchemy import func, select
    _has_payments = True
except ImportError:
    payments_router = None
    auth_router = None
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
    app.include_router(auth_router)

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


_GO_STYLE = """*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#080d17;color:#e8f5e9;font-family:-apple-system,'SF Pro Display','Segoe UI',system-ui,sans-serif;
min-height:100vh;display:flex;align-items:center;justify-content:center;overflow-x:hidden}}
.go{{min-height:100vh;width:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;
padding:48px 24px 32px;position:relative;overflow:hidden}}
.go::before{{content:'';position:absolute;top:-120px;left:50%;transform:translateX(-50%);width:400px;height:400px;
background:radial-gradient(circle,rgba(34,197,94,0.3) 0%,transparent 70%);pointer-events:none;
animation:breathe 4s ease-in-out infinite}}
@keyframes breathe{{0%,100%{{opacity:.4;transform:translateX(-50%) scale(.9)}}50%{{opacity:.7;transform:translateX(-50%) scale(1.1)}}}}
.grid{{position:absolute;inset:0;background-image:linear-gradient(rgba(34,197,94,0.1) 1px,transparent 1px),
linear-gradient(90deg,rgba(34,197,94,0.1) 1px,transparent 1px);background-size:40px 40px;opacity:.4;pointer-events:none}}
.c{{position:relative;z-index:1;display:flex;flex-direction:column;align-items:center;max-width:340px;width:100%}}
.brand{{font-size:10px;letter-spacing:.25em;text-transform:uppercase;color:#22c55e;font-weight:700;margin-bottom:32px;opacity:.8}}
.icon{{width:88px;height:88px;border-radius:24px;background:#0f1729;border:1.5px solid rgba(34,197,94,0.1);
display:flex;align-items:center;justify-content:center;font-size:40px;margin-bottom:24px;
box-shadow:0 0 40px rgba(34,197,94,0.12),0 8px 32px rgba(0,0,0,0.3)}}
.mn{{font-size:13px;letter-spacing:.18em;text-transform:uppercase;color:#22c55e;font-weight:700;margin-bottom:8px}}
.mt{{font-size:32px;font-weight:800;letter-spacing:-0.02em;line-height:1.1;margin-bottom:12px;text-align:center}}
.md{{font-size:15px;color:#6b7280;text-align:center;line-height:1.5;margin-bottom:28px}}
.fs{{width:100%;display:flex;flex-direction:column;gap:10px;margin-bottom:32px}}
.f{{display:flex;align-items:center;gap:12px;padding:10px 14px;background:#0f1729;
border:1px solid rgba(34,197,94,0.1);border-radius:10px;font-size:13px;font-weight:500}}
.fd{{width:6px;height:6px;border-radius:50%;background:#22c55e;flex-shrink:0;box-shadow:0 0 6px rgba(34,197,94,0.3)}}
.cta{{display:block;width:100%;padding:16px 24px;background:#22c55e;color:#fff;font-size:16px;font-weight:700;
letter-spacing:.02em;border:none;border-radius:12px;text-decoration:none;text-align:center;cursor:pointer;
position:relative;overflow:hidden;box-shadow:0 4px 20px rgba(34,197,94,0.3),0 2px 8px rgba(0,0,0,0.2)}}
.cta::after{{content:'';position:absolute;top:0;left:-100%;width:100%;height:100%;
background:linear-gradient(90deg,transparent,rgba(255,255,255,0.15),transparent);animation:shimmer 3s ease-in-out infinite}}
@keyframes shimmer{{0%{{left:-100%}}50%{{left:100%}}100%{{left:100%}}}}
.dn{{margin-top:20px;font-size:12px;color:#374151;text-align:center;line-height:1.5}}
.dn a{{color:#22c55e;text-decoration:none;font-weight:600}}
.ft{{margin-top:28px;padding-top:20px;border-top:1px solid rgba(34,197,94,0.1);width:100%;
display:flex;justify-content:center;gap:16px;font-size:11px;color:#374151;letter-spacing:.04em}}
.sn{{color:#22c55e;font-weight:700}}"""

_GO_PAGE = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GolfCoachNow — {title}</title>
<style>""" + _GO_STYLE + """</style>
</head><body>
<div class="go"><div class="grid"></div>
<div class="c">
<div class="brand">GolfCoachNow</div>
<div class="icon">{icon}</div>
<div class="mn">{mode_label} Mode</div>
<div class="mt">{headline}</div>
<div class="md">{desc}</div>
<div class="fs">
<div class="f"><span class="fd"></span>{f1}</div>
<div class="f"><span class="fd"></span>{f2}</div>
<div class="f"><span class="fd"></span>{f3}</div>
</div>
<a class="cta" href="golfcoachnow://mode/{mode}">Launch {mode_label} Test →</a>
<div class="dn">Don't have the app?<br><a href="#">Download for iOS</a> · <a href="#">Download for Android</a></div>
<div class="ft"><span><span class="sn">20</span> faults tracked</span><span><span class="sn">3</span> free reps / day</span></div>
</div></div>
<script>setTimeout(function(){{window.location.href="golfcoachnow://mode/{mode}"}},300)</script>
</body></html>"""


@app.get("/go/swing", response_class=HTMLResponse)
def go_swing():
    return _GO_PAGE.format(
        title="Swing Test", icon="🏌️", mode_label="Swing", mode="swing",
        headline="Analyze Your<br>Full Swing",
        desc="AI-powered down-the-line analysis with real-time correction feedback.",
        f1="20 biomechanical checkpoints",
        f2="Grip, plane &amp; tempo analysis",
        f3="Instant correction with drill",
    )


@app.get("/go/putt", response_class=HTMLResponse)
def go_putt():
    return _GO_PAGE.format(
        title="Putt Test", icon="🎯", mode_label="Putt", mode="putt",
        headline="Master Your<br>Putting Stroke",
        desc="Precision stroke analysis — speed, alignment, and face control at impact.",
        f1="Speed &amp; distance calibration",
        f2="Face angle at impact",
        f3="Green reading confidence",
    )


@app.get("/go/short-game", response_class=HTMLResponse)
def go_short_game():
    return _GO_PAGE.format(
        title="Short Game Test", icon="⛳", mode_label="Short Game", mode="short_game",
        headline="Sharpen Your<br>Short Game",
        desc="Chipping and pitching analysis — contact, trajectory, and distance control.",
        f1="Contact quality detection",
        f2="Trajectory &amp; landing zone",
        f3="Club selection guidance",
    )
