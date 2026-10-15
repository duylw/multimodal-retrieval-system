# Tổng quan Dự án: Hệ thống Truy xuất Video Đa phương thức (Multimodal Video Moment Retrieval)

## 1. Phát biểu Bài toán (Problem Formulation)
Hệ thống giải quyết bài toán **Truy xuất khoảnh khắc trong video bằng ngôn ngữ tự nhiên (Natural Language Video Moment Retrieval)**:
* **Đầu vào (Input):**
  * Kho dữ liệu video ngoại tuyến: Khoảng 100GB video (tương đương 40-50 giờ video) thuộc nhiều chủ đề phong phú: thời sự, phóng sự, ẩm thực - nấu ăn, đời sống, vlog...
  * Truy vấn trực tuyến từ người dùng: Một câu mô tả bằng tiếng Việt tự nhiên (ví dụ: *"hướng dẫn ướp thịt bò trước khi xào"*, *"MC phỏng vấn người dân tại hiện trường vụ cháy"*, *"xe cứu thương bật còi hú chạy qua ngã tư"*).
* **Đầu ra (Output):**
  * Danh sách xếp hạng các khoảnh khắc khớp nhất gồm: **Tên video + Thời điểm bắt đầu (giây) + Thời điểm kết thúc (giây) + Điểm tin cậy (Confidence Score)**.
  * Cho phép người dùng nhấp trực tiếp vào kết quả để phát đúng giây tương ứng và xem ngữ cảnh xung quanh.

---

## 2. Tiêu chí Đánh giá Học thuật (Evaluation Metrics)
Để phục vụ đánh giá trong đồ án, hệ thống thiết lập bộ đánh giá tiêu chuẩn (Ground Truth Benchmark) gồm 30-50 truy vấn mẫu với nhãn thời gian chuẩn:
1. **Recall@K (với K = 1, 5, 10):** Tỷ lệ phần trăm các câu hỏi mà đáp án đúng nằm trong top K kết quả trả về.
2. **Mean Reciprocal Rank (MRR):** Điểm trung bình nghịch đảo thứ hạng của đáp án đúng đầu tiên.
3. **Tiêu chí Khớp đoạn (Hit Condition):** Một kết quả trả về ở giây T được coi là "Đoán trúng" (Hit) nếu:
   * Điểm T rơi vào khoảng thời gian của nhãn thật: `[Start_true - 5s, End_true + 5s]`.
   * Hoặc độ trùng khớp thời gian IoU (Intersection over Union) giữa đoạn dự đoán và đoạn nhãn đạt từ 0.3 trở lên.
4. **Ablation Study (Nghiên cứu thành phần):**
   * Chỉ Visual (SigLIP2)
   * Visual + ASR (Whisper)
   * Visual + OCR (PaddleOCR)
   * Kết hợp toàn bộ (Visual + ASR + OCR + CLAP)

---

## 3. Kiến trúc Đa phương thức (Multimodal Architecture)

Sơ đồ luồng xử lý không dùng Mermaid (biểu diễn ASCII):

```
PHASE OFFLINE (XỬ LÝ DỮ LIỆU & LẬP CHỈ MỤC)
[100GB Video Files]
        │
        ├─► [Video Decoder] ──► [TransNetV2: Tách Shot] ──► [Lọc & Chọn Keyframe thích ứng]
        │                                                           │
        │                                                           ▼
        │                                              [SigLIP2: Trích Vector Ảnh]
        │                                              + [Vector trung bình Shot]
        │                                                           │
        │                                                           ▼
        │                                              [FAISS Index: Visual]
        │
        ├─► [Audio Extractor (WAV 16kHz)] ──► [Silero VAD] ──► [faster-whisper int8]
        │                                                               │
        │                                                               ▼
        │                                              [Văn bản lời thoại kèm Timestamp]
        │                                                               │
        │                                          ┌────────────────────┴──────────────────┐
        │                                          ▼                                       ▼
        │                                 [BM25 Index (Lexical)]                  [bge-m3 Index (Dense)]
        │
        ├─► [Keyframe có chữ (Detector)] ──► [PaddleOCR tiếng Việt]
        │                                             │
        │                                             ▼
        │                                 [SQLite FTS5 Full-text Search]
        │
        └─► [Audio 10s chunks] ──► [CLAP Audio Event Embedding] ──► [FAISS Index: Audio]


PHASE ONLINE (XỬ LÝ TRUY VẤN & TÌM KIẾM THEO THỜI GIAN)
[Truy vấn tiếng Việt của người dùng]
        │
        ▼
[Bộ phân tách & Viết lại truy vấn] ── (Rule-based Regex + Fallback dịch tiếng Anh)
        │
        ├─► [Mô tả hình ảnh (Tiếng Anh)] ──► Tra FAISS SigLIP2 (Top 200)
        ├─► [Từ khóa lời thoại]         ──► Tra BM25 & bge-m3 ASR (Top 200)
        ├─► [Chữ / Tên riêng / Biển hiệu]──► Tra SQLite FTS5 OCR (Top 200)
        └─► [Âm thanh môi trường]        ──► Tra FAISS CLAP (Top 200)
        │
        ▼
[Chuẩn hóa điểm số: Min-Max / Reciprocal Rank Fusion (RRF)]
        │
        ▼
[Gộp điểm trên trục thời gian: Cửa sổ trượt 5 giây (Sliding Window)]
        │
        ▼
[Gom cụm các đoạn liền kề & Xếp hạng cuối cùng]
        │
        ▼
[Web UI: Hiển thị kết quả + Phát video + Phản hồi tương tác (Relevance Feedback)]
```

---

## 4. Cấu trúc Thư mục Đề xuất cho Codebase

```
d:/UIT/TX/doan/
│
├── AGENTS.md                  # Quy chuẩn persona, luật và giới hạn phần cứng của AI
├── PROJECT_OVERVIEW.md        # Tài liệu tổng quan dự án (file này)
├── TRACKING.md                # Bảng theo dõi tiến độ từng công việc
│
├── .agents/                   # Tùy biến và năng lực của AI Assistant
│   └── skills/                # Các kỹ năng kỹ thuật chạy theo cơ chế Progressive Disclosure
│       ├── video-benchmark-eval/
│       ├── vram-safe-embedding/
│       └── temporal-multimodal-fusion/
│
├── docs/                      # Tài liệu kỹ thuật và hướng dẫn quy trình
│   ├── GLOSSARY.md            # Từ điển thuật ngữ kỹ thuật và cơ chế các mô hình AI
│   └── GIT_GUIDELINES.md      # Quy chuẩn Git, conventional commits, làm việc nhóm
│
├── tasks/                     # Chi tiết từng gói công việc kỹ thuật
│   ├── task-00-environment-and-eval.md
│   ├── task-01-shot-detection-keyframes.md
│   ├── task-02-visual-siglip-faiss.md
│   ├── task-03-asr-whisper.md
│   ├── task-04-ocr-paddle.md
│   ├── task-05-temporal-fusion.md
│   ├── task-06-ui-and-feedback.md
│   └── task-07-audio-clap.md
│
├── configs/                   # File cấu hình tham số hệ thống
│   └── default_config.yaml    # Đường dẫn, ngưỡng cắt shot, model names, batch sizes
│
├── src/                       # Toàn bộ mã nguồn chính của hệ thống
│   ├── __init__.py
│   ├── pipeline.py            # Script điều phối toàn bộ luồng offline có resume
│   │
│   ├── extractors/            # Các module trích xuất đặc trưng
│   │   ├── __init__.py
│   │   ├── shots.py           # Tách shot bằng TransNetV2
│   │   ├── keyframes.py       # Lọc và chọn keyframe thích ứng
│   │   ├── visual.py          # Trích vector ảnh SigLIP2
│   │   ├── speech.py          # Silero VAD + faster-whisper
│   │   ├── ocr.py             # Lọc frame có chữ + PaddleOCR
│   │   └── audio_events.py    # CLAP trích vector âm thanh
│   │
│   ├── indexers/              # Quản lý cơ sở dữ liệu và chỉ mục
│   │   ├── __init__.py
│   │   ├── vector_index.py    # FAISS quản lý vector ảnh và âm thanh
│   │   ├── text_index.py      # SQLite FTS5 và BM25
│   │   └── metadata_db.py     # SQLite lưu thông tin video, shot, keyframe, timestamp
│   │
│   ├── retrieval/             # Xử lý truy vấn và thuật toán gộp điểm
│   │   ├── __init__.py
│   │   ├── query_parser.py    # Tách từ khóa, dịch tiếng Anh
│   │   ├── score_fusion.py    # Chuẩn hóa điểm (RRF / Min-Max) & Sliding Window
│   │   └── search_engine.py   # Bộ điều phối tìm kiếm tổng hợp
│   │
│   ├── evaluation/            # Bộ công cụ đánh giá khoa học
│   │   ├── __init__.py
│   │   ├── ground_truth.json  # 30-50 câu truy vấn kèm mốc thời gian chuẩn
│   │   └── evaluate.py        # Tính toán Recall@K, MRR, vẽ bảng ablation
│   │
│   └── ui/                    # Giao diện tìm kiếm trực quan
│       ├── app.py             # FastAPI / Web Server
│       └── static/            # Giao diện HTML/CSS/JS (Video player + Seekbar)
│
├── data/                      # Lưu trữ dữ liệu (được loại trừ trong .gitignore)
│   ├── raw_videos/            # 100GB video đầu vào
│   ├── keyframes/             # Ảnh keyframe đã trích xuất
│   ├── audio_temp/            # File âm thanh tạm (tự dọn dẹp sau khi trích ASR)
│   ├── indices/               # File chỉ mục FAISS (.index) và SQLite (.db)
│   └── checkpoints/           # File lưu tiến trình đã xử lý (đảm bảo resume)
├── pyproject.toml             # Quản lý cấu hình dự án và dependencies (uv)
└── .python-version            # Phiên bản Python được chỉ định cho uv
```
