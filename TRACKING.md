# TRACKING.md - Bảng Theo dõi Tiến độ Đồ án

> **Dự án:** Hệ thống Truy xuất Video Đa phương thức bằng Ngôn ngữ Tự nhiên (Multimodal Video Moment Retrieval)  
> **Sinh viên:** Nhóm đồ án UIT  
> **Cập nhật lần cuối:** 15/10/2026  
> **Môi trường thực thi:** GTX 1650 (4GB VRAM), RAM 16GB, Trống ~150GB Ổ D.

---

## 1. Trạng thái Tổng quan (Overall Status)

* **Giai đoạn hiện tại:** **Khởi tạo và Định hình Kiến trúc (Project Initialization & Planning)**
* **Tiến độ tổng thể:** `10%`
* **Công việc đang làm ngay lúc này:** Hoàn thành khung tài liệu kiến trúc, quy chuẩn hoạt động, phân rã task chi tiết và chuẩn bị môi trường chạy code.

---

## 2. Bảng Theo dõi Nhiệm vụ Chi tiết (Task Board)

| Mã Task | Tên Nhiệm vụ | Trọng tâm | Trạng thái | Tài liệu Chi tiết | Sản phẩm Đầu ra (Deliverables) |
|---|---|---|---|---|---|
| **Task 00** | Thiết lập Môi trường & Bộ Eval | Cài đặt venv với uv, CUDA, `ground_truth.json`, script tính Recall@K, MRR | **Hoàn thành (Completed)** | [task-00](file:///d:/UIT/TX/doan/tasks/task-00-environment-and-eval.md) | `pyproject.toml`, `evaluate.py`, `ground_truth.json` |
| **Task 01** | Tách Cảnh & Chọn Keyframe | TransNetV2/SceneDetect, lọc ảnh mờ Laplacian, loại ảnh tối/trùng | **Hoàn thành (Completed)** | [task-01](file:///d:/UIT/TX/doan/tasks/task-01-shot-detection-keyframes.md) | `shots.py`, `keyframes.py`, bảng SQLite `shots` |
| **Task 01B** | Giao diện Debug Cảnh & Keyframe | FastAPI + Range 206, đồng bộ video timeline, hiển thị shot & keyframe | **Sẵn sàng thực hiện (Ready)** | [task-01b](file:///d:/UIT/TX/doan/tasks/task-01b-debug-ui-shots-keyframes.md) | `debug_server.py`, giao diện SPA debug video |
| **Task 02** | Visual SigLIP2 & FAISS | Trích vector SigLIP2, pooling theo shot, lập chỉ mục FAISS | **Chờ thực hiện (Pending)** | [task-02](file:///d:/UIT/TX/doan/tasks/task-02-visual-siglip-faiss.md) | `visual.py`, `visual_siglip2.index` |
| **Task 03** | Lời thoại Whisper & Hybrid Index | Silero VAD + faster-whisper int8, BM25 + bge-m3 dense | **Chờ thực hiện (Pending)** | [task-03](file:///d:/UIT/TX/doan/tasks/task-03-asr-whisper.md) | `speech.py`, bảng SQLite `transcripts`, `asr.index` |
| **Task 04** | Chữ Màn hình PaddleOCR | Bộ lọc frame có chữ, PaddleOCR tiếng Việt trên CPU, SQLite FTS5 | **Chờ thực hiện (Pending)** | [task-04](file:///d:/UIT/TX/doan/tasks/task-04-ocr-paddle.md) | `ocr.py`, bảng ảo SQLite `ocr_fts` |
| **Task 05** | Hợp nhất Đa phương thức | Query parser, chuẩn hóa điểm RRF, Sliding Window 5s | **Chờ thực hiện (Pending)** | [task-05](file:///d:/UIT/TX/doan/tasks/task-05-temporal-fusion.md) | `score_fusion.py`, `search_engine.py` |
| **Task 06** | Giao diện Web & Feedback | FastAPI, video stream Range 206, Rocchio relevance feedback | **Chờ thực hiện (Pending)** | [task-06](file:///d:/UIT/TX/doan/tasks/task-06-ui-and-feedback.md) | `app.py`, thư mục `static/` (HTML/CSS/JS) |
| **Task 07** | Âm thanh CLAP (Giai đoạn 2) | Cắt audio 10s, vector CLAP audio events, FAISS audio | **Dự phòng Giai đoạn 2** | [task-07](file:///d:/UIT/TX/doan/tasks/task-07-audio-clap.md) | `audio_events.py`, `audio_clap.index` |

---

## 3. Các Cột mốc Lớn (Milestones)

* [x] **Cột mốc 0: Định hình Kiến trúc & Tài liệu Dự án** (Hoàn thành 15/10/2026)
  * Thiết lập nguyên tắc làm việc và ràng buộc phần cứng: [AGENTS.md](file:///d:/UIT/TX/doan/AGENTS.md).
  * Định nghĩa bài toán và luồng xử lý tổng thể: [PROJECT_OVERVIEW.md](file:///d:/UIT/TX/doan/PROJECT_OVERVIEW.md).
  * Phân rã công việc thành các task rõ ràng kèm cách làm và kiểm thử: [tasks/](file:///d:/UIT/TX/doan/tasks).
* [ ] **Cột mốc 1: Baseline Tối thiểu (End-to-End Visual Only)**
  * Cài đặt môi trường, benchmark được tốc độ tách shot và SigLIP2 trên GTX 1650.
  * Hoàn thiện công cụ kiểm tra gỡ lỗi phân đoạn shot và trích xuất keyframe.
  * Tìm kiếm được khoảnh khắc bằng hình ảnh đơn thuần và đo `Recall@10` đầu tiên.
* [ ] **Cột mốc 2: Tích hợp Đa kênh Văn bản (ASR + OCR)**
  * Hoàn thành phiên âm Whisper tiếng Việt và đọc chữ PaddleOCR trên CPU.
  * Tạo chỉ mục kép và SQLite FTS5.
* [ ] **Cột mốc 3: Hợp nhất Thời gian & Đo lường Ablation Study**
  * Hoàn thành thuật toán Sliding Window và chuẩn hóa điểm RRF.
  * Xuất bảng báo cáo so sánh độ chính xác tăng thêm của từng kênh.
* [ ] **Cột mốc 4: Hoàn thiện Web UI & Bảo vệ Đồ án**
  * Hoàn thành giao diện tra cứu, phát video đúng giây và phản hồi tương tác.
  * Đóng gói mã nguồn và hoàn thiện báo cáo luận văn.

---

## 4. Nhật ký Hoạt động (Activity Log)

* **15/10/2026:**
  * Rà soát và đánh giá ý tưởng ban đầu trong [first_ideas.md](file:///d:/UIT/TX/doan/first_ideas.md).
  * Nhận diện các điểm nghẽn kỹ thuật: VRAM 4GB của GTX 1650, lệch thang đo điểm số giữa Cosine và BM25, hiện tượng xẻ đôi sự kiện trên trục thời gian.
  * Khởi tạo bộ tài liệu quy chuẩn: [AGENTS.md](file:///d:/UIT/TX/doan/AGENTS.md), [PROJECT_OVERVIEW.md](file:///d:/UIT/TX/doan/PROJECT_OVERVIEW.md), bảng theo dõi [TRACKING.md](file:///d:/UIT/TX/doan/TRACKING.md).
  * Viết chi tiết 8 tài liệu task từ [task-00](file:///d:/UIT/TX/doan/tasks/task-00-environment-and-eval.md) đến [task-07](file:///d:/UIT/TX/doan/tasks/task-07-audio-clap.md).
  * Bổ sung tài liệu từ điển thuật ngữ [docs/GLOSSARY.md](file:///d:/UIT/TX/doan/docs/GLOSSARY.md) và hướng dẫn Git [docs/GIT_GUIDELINES.md](file:///d:/UIT/TX/doan/docs/GIT_GUIDELINES.md).
  * Khởi tạo 3 workspace skills (`video-benchmark-eval`, `vram-safe-embedding`, `temporal-multimodal-fusion`) và tinh gọn [AGENTS.md](file:///d:/UIT/TX/doan/AGENTS.md) xuống còn 42 dòng.
  * Hoàn thành [Task 00](file:///d:/UIT/TX/doan/tasks/task-00-environment-and-eval.md): Cài đặt môi trường `uv`, PyTorch 2.5.1 CUDA 12.1 (GTX 1650 4GB), tập 20 truy vấn [ground_truth.json](file:///d:/UIT/TX/doan/data/ground_truth.json), và công cụ đo lường [evaluate.py](file:///d:/UIT/TX/doan/src/evaluation/evaluate.py).
  * Hoàn thành [Task 01](file:///d:/UIT/TX/doan/tasks/task-01-shot-detection-keyframes.md): Viết [metadata_db.py](file:///d:/UIT/TX/doan/src/indexers/metadata_db.py), [shots.py](file:///d:/UIT/TX/doan/src/extractors/shots.py) (292 shots trong 60s), và [keyframes.py](file:///d:/UIT/TX/doan/src/extractors/keyframes.py) (344 keyframes trong 25s, dung lượng ~18.8MB).
* **26/10/2026:**
  * Bổ sung [Task 01B](file:///d:/UIT/TX/doan/tasks/task-01b-debug-ui-shots-keyframes.md): Xây dựng giao diện Web debug trực quan hóa phân đoạn shot và danh sách keyframe theo dòng thời gian video.

---

## 5. Hành động Kế tiếp (Next Action)
* **Bắt tay vào thực hiện [Task 01B: Giao diện Debug và Trực quan hóa Cảnh quay & Keyframe](file:///d:/UIT/TX/doan/tasks/task-01b-debug-ui-shots-keyframes.md):**
  1. Viết server FastAPI [src/ui/debug_server.py](file:///d:/UIT/TX/doan/src/ui/debug_server.py) hỗ trợ API danh sách video, shots, keyframes và stream video HTTP 206 Partial Content.
  2. Viết giao diện Single-Page Application (HTML5/CSS3/Vanilla JS) với thanh timeline phân đoạn shot tương tác hai chiều với trình phát video.
  3. Kiểm thử trên video thực tế `L13_V001`.
