# Vietnamese STT Web App

Flask web app chuyển ngữ âm thanh tiếng Việt bằng [faster-whisper](https://github.com/SYSTRAN/faster-whisper).  
Hỗ trợ **GPU (CUDA)** tự động — tốc độ nhanh hơn ~5-10x so với CPU.

## Tính năngh

- Upload audio (mp3, mp4, m4a, wav, ogg, flac, webm)
- Streaming transcript theo thời gian thực (SSE)
- Timeline view: hiển thị từng đoạn với timestamp
- Export DOCX
- Domain context: giúp Whisper nhận diện thuật ngữ chuyên ngành

## Yêu cầu hệ thống

| Thành phần | Tối thiểu | Khuyên dùng |
|---|---|---|
| Python | 3.10+ | 3.11 |
| RAM | 4 GB | 8 GB+ |
| GPU | Không bắt buộc | NVIDIA với CUDA 11.8+ |
| VRAM (GPU) | — | 4 GB+ (model large-v3 cần 6 GB) |

## Cài đặt

### 1. Clone repo

```bash
git clone https://github.com/yuHM1512/whisper_webapp.git
cd whisper_webapp
```

### 2. Tạo virtual environment

```bash
python -m venv venv
venv\Scripts\activate     # Windows
# source venv/bin/activate  # Linux/macOS
```

### 3. Cài thư viện

```bash
pip install -r requirements.txt
```

### 4. (Nếu dùng GPU) Cài CUDA runtime cho CTranslate2

Bước này chỉ cần nếu máy có GPU NVIDIA và muốn tăng tốc:

```bash
pip install ctranslate2 --extra-index-url https://download.pytorch.org/whl/cu118
```

Hoặc cài CUDA Toolkit 11.8+ từ [developer.nvidia.com/cuda-downloads](https://developer.nvidia.com/cuda-downloads).

App sẽ **tự phát hiện GPU** khi khởi động — không cần sửa code.

## Chạy

```bash
python app.py
```

Hoặc trên Windows dùng `run.bat` (double-click).

Mở trình duyệt: **http://localhost:5000**

## Chọn model Whisper

| Model | VRAM | Tốc độ (GPU) | Độ chính xác |
|---|---|---|---|
| tiny | ~1 GB | Rất nhanh | Thấp |
| base | ~1 GB | Nhanh | Trung bình |
| small | ~2 GB | Nhanh | Khá |
| medium | ~5 GB | Trung bình | Tốt |
| large-v3 | ~6 GB | Chậm hơn | Tốt nhất |

Khuyên dùng `large-v3` nếu máy có GPU ≥ 8 GB VRAM.

## Kiến trúc

```
whisper_webapp/
├── app.py              # Flask backend + SSE streaming
├── requirements.txt    # Dependencies
├── run.bat             # Windows launcher
└── templates/
    └── index.html      # UI (timeline view)
```
