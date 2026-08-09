import os
import tempfile
from flask import Flask, request, jsonify, render_template_string
from wedge import process_mobile_input, CORRECTIONS
from video_analyzer import analyze_video, VideoAnalysisError

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

ALLOWED_EXTENSIONS = {"mp4", "mov", "avi", "m4v"}

API_DOCS_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GolfCoachNow API Documentation</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0d1117; color: #c9d1d9; line-height: 1.6; }
.container { max-width: 900px; margin: 0 auto; padding: 24px; }
h1 { color: #58a6ff; font-size: 28px; margin-bottom: 8px; }
h2 { color: #f0f6fc; font-size: 20px; margin: 32px 0 12px; padding-bottom: 8px; border-bottom: 1px solid #21262d; }
h3 { color: #58a6ff; font-size: 16px; margin: 20px 0 8px; }
.subtitle { color: #8b949e; font-size: 14px; margin-bottom: 24px; }
.badge { display: inline-block; padding: 4px 10px; border-radius: 4px; font-size: 12px; font-weight: 700; margin-right: 8px; font-family: monospace; }
.badge-get { background: #1f6feb33; color: #58a6ff; border: 1px solid #1f6feb; }
.badge-post { background: #23883533; color: #3fb950; border: 1px solid #238835; }
.endpoint { background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 16px; margin: 12px 0; }
.endpoint-url { font-family: monospace; color: #f0f6fc; font-size: 14px; }
pre { background: #161b22; border: 1px solid #21262d; border-radius: 6px; padding: 16px; overflow-x: auto; font-size: 13px; margin: 8px 0; }
code { font-family: 'SF Mono', 'Fira Code', monospace; color: #e6edf3; }
.inline-code { background: #21262d; padding: 2px 6px; border-radius: 3px; font-size: 13px; }
table { width: 100%; border-collapse: collapse; margin: 12px 0; }
th { text-align: left; padding: 8px 12px; background: #161b22; color: #8b949e; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #21262d; }
td { padding: 8px 12px; border-bottom: 1px solid #21262d; font-size: 14px; }
td code { color: #79c0ff; }
.try-it { background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 20px; margin: 16px 0; }
.try-it textarea { width: 100%; background: #0d1117; color: #c9d1d9; border: 1px solid #30363d; border-radius: 6px; padding: 12px; font-family: monospace; font-size: 13px; resize: vertical; min-height: 80px; }
.try-it button { background: #238636; color: #fff; border: none; padding: 8px 20px; border-radius: 6px; font-size: 14px; font-weight: 600; cursor: pointer; margin-top: 10px; }
.try-it button:hover { background: #2ea043; }
.try-it button:disabled { background: #21262d; color: #484f58; cursor: wait; }
#response-output { margin-top: 12px; min-height: 60px; }
.status-dot { display: inline-block; width: 8px; height: 8px; background: #3fb950; border-radius: 50%; margin-right: 6px; }
.header-bar { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; margin-bottom: 24px; }
.status-badge { font-size: 12px; color: #3fb950; background: #23883520; padding: 4px 10px; border-radius: 12px; border: 1px solid #23883550; }
.fault-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 8px; margin: 12px 0; }
.fault-item { background: #161b22; border: 1px solid #21262d; border-radius: 6px; padding: 10px 12px; }
.fault-key { color: #79c0ff; font-family: monospace; font-size: 13px; }
.fault-desc { color: #8b949e; font-size: 12px; margin-top: 4px; }
.base-url { background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 12px 16px; font-family: monospace; font-size: 15px; color: #58a6ff; margin: 12px 0; }
</style>
</head>
<body>
<div class="container">

<div class="header-bar">
  <div>
    <h1>GolfCoachNow API</h1>
    <p class="subtitle">Wedge Engine &mdash; Golf Swing Correction Service</p>
  </div>
  <span class="status-badge"><span class="status-dot"></span>Live</span>
</div>

<div class="base-url">https://golfcoachnow.pythonanywhere.com</div>

<h2>Endpoints</h2>

<div class="endpoint">
  <span class="badge badge-get">GET</span>
  <span class="endpoint-url">/</span>
  <p style="color:#8b949e; margin-top:8px; font-size:14px;">Health check &mdash; returns API status.</p>
  <h3>Response</h3>
  <pre><code>{
  "status": "ok",
  "service": "GolfCoachNow API"
}</code></pre>
</div>

<div class="endpoint">
  <span class="badge badge-post">POST</span>
  <span class="endpoint-url">/upload</span>
  <p style="color:#8b949e; margin-top:8px; font-size:14px;">Upload a golf swing video for analysis. Returns the dominant fault and coaching correction.</p>

  <h3>Request</h3>
  <p style="color:#8b949e; font-size:13px;">Content-Type: <code class="inline-code">multipart/form-data</code></p>
  <table>
    <tr><th>Field</th><th>Type</th><th>Description</th></tr>
    <tr><td><code>file</code></td><td>File</td><td>Video file (.mp4, .mov, .avi, .m4v). Max 16 MB.</td></tr>
  </table>

  <h3>cURL Example</h3>
  <pre><code>curl -X POST https://golfcoachnow.pythonanywhere.com/upload \\
  -F "file=@swing.mp4"</code></pre>

  <h3>Response</h3>
  <pre><code>{
  "rep": 1,
  "dominant_fault": "open_clubface",
  "correction": "If the face is open, strengthen your lead-hand grip and square the face earlier.",
  "normalized_scores": {
    "open_clubface": 1.0,
    "casting": 0.75,
    "sway": 0.375
  },
  "status": "ok"
}</code></pre>
</div>

<div class="endpoint">
  <span class="badge badge-post">POST</span>
  <span class="endpoint-url">/wedge</span>
  <p style="color:#8b949e; margin-top:8px; font-size:14px;">Analyze pre-computed swing fault scores and return the dominant fault with a coaching correction.</p>

  <h3>Request Body</h3>
  <pre><code>{
  "data": {
    "open_clubface": 0.8,
    "casting": 0.6,
    "sway": 0.3
  }
}</code></pre>
  <p style="color:#8b949e; font-size:13px; margin-top:4px;">
    <code class="inline-code">data</code> &mdash; dictionary of fault keys mapped to severity scores (0.0 &ndash; 1.0).
  </p>

  <h3>Response</h3>
  <pre><code>{
  "rep": 1,
  "dominant_fault": "open_clubface",
  "correction": "If the face is open, strengthen your lead-hand grip and square the face earlier.",
  "normalized_scores": {
    "open_clubface": 1.0,
    "casting": 0.75,
    "sway": 0.375
  },
  "status": "ok"
}</code></pre>

  <h3>Response Fields</h3>
  <table>
    <tr><th>Field</th><th>Type</th><th>Description</th></tr>
    <tr><td><code>rep</code></td><td>Integer</td><td>Incrementing rep counter (resets on server restart)</td></tr>
    <tr><td><code>dominant_fault</code></td><td>String</td><td>Highest-scoring fault after normalization</td></tr>
    <tr><td><code>correction</code></td><td>String</td><td>Human-readable coaching correction cue</td></tr>
    <tr><td><code>normalized_scores</code></td><td>Object</td><td>All submitted faults normalized to 0.0&ndash;1.0</td></tr>
    <tr><td><code>status</code></td><td>String</td><td>Always "ok" on success</td></tr>
  </table>
</div>

<h2>Try It Live</h2>
<div class="try-it">
  <label style="font-size:14px; color:#8b949e; display:block; margin-bottom:6px;">Request Body (JSON):</label>
  <textarea id="request-body">{
  "data": {
    "open_clubface": 0.8,
    "casting": 0.6,
    "sway": 0.3
  }
}</textarea>
  <button id="send-btn" onclick="sendRequest()">Send POST /wedge</button>
  <div id="response-output"></div>
</div>

<h2>Available Fault Keys</h2>
<p style="color:#8b949e; font-size:14px; margin-bottom:12px;">20 deterministic correction cues. Pass any combination as keys in the <code class="inline-code">data</code> object.</p>
<div class="fault-grid">
  {% for key, desc in faults %}
  <div class="fault-item">
    <div class="fault-key">{{ key }}</div>
    <div class="fault-desc">{{ desc }}</div>
  </div>
  {% endfor %}
</div>

<h2>cURL Examples</h2>
<pre><code># Health check
curl https://golfcoachnow.pythonanywhere.com/

# Upload a swing video
curl -X POST https://golfcoachnow.pythonanywhere.com/upload \\
  -F "file=@swing.mp4"

# Send pre-computed fault scores
curl -X POST https://golfcoachnow.pythonanywhere.com/wedge \\
  -H "Content-Type: application/json" \\
  -d '{"data":{"open_clubface":0.8,"casting":0.6,"sway":0.3}}'</code></pre>

<h2>Integration</h2>
<table>
  <tr><th>Client</th><th>Endpoint</th><th>Config</th></tr>
  <tr><td>iOS App (Swift)</td><td><code>/upload</code></td><td><code>APIConfig.baseURL</code> in APIClient.swift</td></tr>
  <tr><td>Desktop Wrapper (Python)</td><td><code>/upload</code></td><td><code>API_URL</code> in main.py</td></tr>
</table>

<div style="margin-top:40px; padding-top:16px; border-top:1px solid #21262d; color:#484f58; font-size:12px;">
  GolfCoachNow API &middot; Hosted on PythonAnywhere
</div>

</div>

<script>
async function sendRequest() {
  const btn = document.getElementById('send-btn');
  const output = document.getElementById('response-output');
  const body = document.getElementById('request-body').value;
  btn.disabled = true;
  btn.textContent = 'Sending...';
  output.innerHTML = '<pre style="color:#8b949e"><code>Loading...</code></pre>';
  try {
    const res = await fetch('/wedge', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: body
    });
    const data = await res.json();
    output.innerHTML = '<pre><code>' + JSON.stringify(data, null, 2) + '</code></pre>';
  } catch(e) {
    output.innerHTML = '<pre style="color:#f85149"><code>Error: ' + e.message + '</code></pre>';
  }
  btn.disabled = false;
  btn.textContent = 'Send POST /wedge';
}
</script>
</body>
</html>
"""


def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.post("/upload")
def upload_video():
    if "file" not in request.files:
        return jsonify({"error": "No file provided", "status": "error"}), 400

    file = request.files["file"]
    if not file.filename or not _allowed_file(file.filename):
        return jsonify({
            "error": "Invalid file type. Accepted: mp4, mov, avi, m4v",
            "status": "error",
        }), 400

    ext = file.filename.rsplit(".", 1)[1].lower()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix="." + ext)
    tmp_path = tmp.name
    try:
        file.save(tmp_path)
        tmp.close()
        scores = analyze_video(tmp_path)
        result = process_mobile_input(scores)
        return jsonify(result)
    except VideoAnalysisError as e:
        return jsonify({"error": str(e), "status": "error"}), 400
    except Exception as e:
        return jsonify({"error": "Video analysis failed", "status": "error"}), 500
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@app.post("/wedge")
def run_wedge():
    data = request.get_json()
    swing_data = data.get("data", {})
    result = process_mobile_input(swing_data)
    return jsonify(result)


@app.get("/")
def health():
    return jsonify({"status": "ok", "service": "GolfCoachNow API"})


@app.get("/docs")
def docs():
    faults = [(k, v) for k, v in CORRECTIONS.items()]
    return render_template_string(API_DOCS_HTML, faults=faults)
