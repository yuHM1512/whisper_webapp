"""
Vietnamese Speech-to-Text Web App
Flask + faster-whisper + SSE streaming
Timeline view only — speaker diarization to be added later (pyannote.audio)
"""

from flask import Flask, render_template, request, jsonify, Response, send_file
import os, json, threading, uuid, io
from datetime import datetime
from faster_whisper import WhisperModel
from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
import queue

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max upload

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Cache model in memory
_model_cache = {}
_model_lock = threading.Lock()

# SSE queues per task
_task_queues: dict[str, queue.Queue] = {}


def _detect_device():
    """Auto-detect GPU (CUDA). Falls back to CPU if no GPU found."""
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", "float16"
    except Exception:
        pass
    return "cpu", "int8"

_DEVICE, _COMPUTE_TYPE = _detect_device()
print(f"[*] Runtime device: {_DEVICE} / {_COMPUTE_TYPE}")


def get_model(size: str) -> WhisperModel:
    with _model_lock:
        if size not in _model_cache:
            print(f"[*] Loading model: {size} on {_DEVICE}...")
            _model_cache[size] = WhisperModel(size, device=_DEVICE, compute_type=_COMPUTE_TYPE)
            print(f"[*] Model {size} ready.")
        return _model_cache[size]


def run_transcription(task_id: str, filepath: str, model_size: str, initial_prompt: str = ''):
    q = _task_queues[task_id]
    try:
        q.put({'type': 'status', 'msg': f'Đang load model {model_size}...'})
        model = get_model(model_size)

        q.put({'type': 'status', 'msg': 'Đang phân tích audio...'})
        transcribe_kwargs = dict(
            language='vi',
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=300,
                speech_pad_ms=200,
            ),
        )
        if initial_prompt:
            transcribe_kwargs['initial_prompt'] = initial_prompt

        segments, info = model.transcribe(filepath, **transcribe_kwargs)

        q.put({
            'type': 'info',
            'duration': round(info.duration, 1),
            'language': info.language,
            'probability': round(info.language_probability, 2),
        })

        total_segments = 0
        for seg in segments:
            total_segments += 1
            q.put({
                'type': 'segment',
                'start': round(seg.start, 1),
                'end': round(seg.end, 1),
                'text': seg.text.strip(),
            })

        q.put({'type': 'done', 'total': total_segments})

    except Exception as e:
        q.put({'type': 'error', 'msg': str(e)})
    finally:
        # Clean up uploaded file after processing
        try:
            os.remove(filepath)
        except Exception:
            pass


# ── ROUTES ─────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'Empty filename'}), 400

    # Allowed audio formats
    allowed = {'.mp3', '.mp4', '.m4a', '.wav', '.ogg', '.flac', '.webm', '.mkv'}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        return jsonify({'error': f'Định dạng không hỗ trợ: {ext}'}), 400

    task_id = str(uuid.uuid4())
    safe_name = f"{task_id}{ext}"
    filepath = os.path.join(UPLOAD_FOLDER, safe_name)
    file.save(filepath)

    file_size = os.path.getsize(filepath)
    return jsonify({
        'task_id': task_id,
        'filename': file.filename,
        'size': file_size,
        'path': filepath,
    })


@app.route('/transcribe', methods=['POST'])
def transcribe():
    data = request.json or {}
    task_id = data.get('task_id')
    filepath = data.get('path')
    model_size = data.get('model', 'medium')
    initial_prompt = data.get('initial_prompt', '')

    if not task_id or not filepath or not os.path.exists(filepath):
        return jsonify({'error': 'Invalid task or file not found'}), 400

    q = queue.Queue()
    _task_queues[task_id] = q

    thread = threading.Thread(
        target=run_transcription,
        args=(task_id, filepath, model_size, initial_prompt),
        daemon=True,
    )
    thread.start()
    return jsonify({'task_id': task_id, 'started': True})


@app.route('/stream/<task_id>')
def stream(task_id):
    """Server-Sent Events: push transcript segments to browser in real-time."""
    def generate():
        q = _task_queues.get(task_id)
        if not q:
            yield f"data: {json.dumps({'type': 'error', 'msg': 'Task not found'})}\n\n"
            return

        # Keep connection alive with heartbeat
        while True:
            try:
                msg = q.get(timeout=30)
                yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                if msg['type'] in ('done', 'error'):
                    # Clean up queue
                    _task_queues.pop(task_id, None)
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        }
    )


@app.route('/export/docx', methods=['POST'])
def export_docx():
    data = request.json or {}
    segments = data.get('segments', [])
    filename = data.get('filename', 'transcript')

    doc = Document()

    # Page margins
    for section in doc.sections:
        section.top_margin    = Cm(2.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin   = Cm(3)
        section.right_margin  = Cm(2.5)

    # Title
    title = doc.add_heading('', level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run('TRANSCRIPT — PHIÊN CHUYỂN NGỮ')
    run.font.size = Pt(16)
    run.font.color.rgb = RGBColor(0x10, 0x25, 0x90)  # --blue

    # Meta info
    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta_run = meta.add_run(f'File: {filename}     Ngày: {datetime.now().strftime("%d/%m/%Y %H:%M")}     Đoạn: {len(segments)}')
    meta_run.font.size = Pt(9)
    meta_run.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)

    doc.add_paragraph()  # spacer

    # Segments
    for seg in segments:
        start = _fmt_time(seg.get('start', 0))
        end   = _fmt_time(seg.get('end', 0))
        text  = seg.get('text', '')

        p = doc.add_paragraph()
        # Timestamp chip
        ts_run = p.add_run(f'[{start} → {end}]  ')
        ts_run.font.size = Pt(9)
        ts_run.font.bold = True
        ts_run.font.color.rgb = RGBColor(0x10, 0x25, 0x90)
        # Text
        txt_run = p.add_run(text)
        txt_run.font.size = Pt(11)
        p.paragraph_format.space_after = Pt(6)

    # Save to buffer
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)

    safe_name = f"transcript_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        as_attachment=True,
        download_name=safe_name,
    )


def _fmt_time(sec: float) -> str:
    m = int(sec // 60)
    s = int(sec % 60)
    return f"{m}:{s:02d}"


@app.route('/models')
def list_models():
    available = list(_model_cache.keys())
    return jsonify({'loaded': available})


if __name__ == '__main__':
    print("=" * 50)
    print("  Vietnamese STT Web App")
    print("  http://localhost:5000")
    print("=" * 50)
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)
