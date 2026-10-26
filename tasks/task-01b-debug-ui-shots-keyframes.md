# Task 01B: Giao diện Debug & Trực quan hóa Cảnh quay và Keyframe (Shot & Keyframe Inspection UI)

## 1. Mục tiêu (What)
* Xây dựng một giao diện web nội bộ (Internal Debug Web UI) gọn nhẹ, trực quan, phục vụ mục đích kiểm tra, gỡ lỗi và đánh giá chất lượng phân đoạn video:
  * **Chọn video:** Cho phép lựa chọn bất kỳ video nào đã qua tiền xử lý trong cơ sở dữ liệu `metadata.db`.
  * **Phát video với Range 206:** Tải trực tiếp file video gốc từ máy tính (`data/raw_videos/{video_id}.mp4`), hỗ trợ tua mượt theo từng khung hình và mốc giây.
  * **Trực quan hóa Dòng thời gian Cảnh quay (Interactive Shot Timeline):** Hiển thị thanh tiến trình video phân mảnh theo các shot với màu sắc phân biệt, cho biết shot bắt đầu từ đâu, kết thúc khi nào và độ dài bao nhiêu giây.
  * **Hiển thị Keyframe trong từng Shot:** Liệt kê đầy đủ các keyframe thuộc về từng shot kèm ảnh thumbnail, mốc giây (`timestamp_sec`), nhãn trích xuất (`Center` hay `Dynamic`), và độ nét Laplacian (`blur_score`).
  * **Đồng bộ hai chiều (Two-Way Synchronization):**
    * Click vào một shot trên timeline hoặc danh sách -> Video tự động nhảy đến `start_sec` của shot đó.
    * Click vào một keyframe thumbnail -> Video tự động nhảy đến đúng `timestamp_sec` của keyframe đó.
    * Khi video đang phát (Play) -> Shot và Keyframe tương ứng với thời điểm hiện tại sẽ tự động được làm nổi bật (Highlight) và cuộn vào tầm nhìn (Auto-scroll).
* Đảm bảo tiêu tốn **0MB VRAM** (hoạt động thuần túy trên CPU/RAM thông qua Web Server chuẩn) để không ảnh hưởng đến phần cứng GTX 1650.

---

## 2. Kiến trúc & Thiết kế Kỹ thuật (How)

### 2.1. Backend Server (`src/ui/debug_server.py`)
Sử dụng **FastAPI** cùng `uvicorn` để cung cấp các API RESTful tốc độ cao:
* `GET /api/videos`: Truy vấn bảng `videos` và `checkpoints` từ `metadata.db` để trả về danh sách các video đã hoàn thành phân đoạn shot.
* `GET /api/videos/{video_id}/shots`: Truy vấn bảng `shots` và `keyframes`, gom nhóm theo cấu trúc:
  ```json
  [
    {
      "shot_id": 1,
      "start_sec": 0.0,
      "end_sec": 16.6,
      "duration_sec": 16.6,
      "keyframes": [
        {"keyframe_id": 1, "timestamp_sec": 3.32, "is_center": false, "blur_score": 417.7, "image_url": "/api/keyframes/L13_V001/shot_0001_t0003.32.jpg"},
        {"keyframe_id": 2, "timestamp_sec": 6.64, "is_center": true, "blur_score": 606.6, "image_url": "/api/keyframes/L13_V001/shot_0001_t0006.64.jpg"}
      ]
    }
  ]
  ```
* `GET /api/stream/{video_id}`: Stream tệp video gốc `.mp4` từ `data/raw_videos/` có xử lý HTTP Header `Range` (HTTP 206 Partial Content), cho phép trình duyệt tua tức thì mà không cần nạp toàn bộ video dung lượng lớn vào RAM.
* `GET /api/keyframes/{video_id}/{filename}`: Phục vụ tệp ảnh keyframe trực tiếp từ `data/keyframes/{video_id}/`.
* `GET /`: Phục vụ tệp HTML Single-Page Application (SPA).

### 2.2. Frontend Web Interface (`src/ui/templates/debug.html` & `src/ui/static/`)
Xây dựng bằng HTML5, CSS3 (Dark Theme chuẩn) và Vanilla JavaScript:
* **Header Bar:**
  * Dropdown chọn Video ID (`L13_V001`, `L13_V002`, ...).
  * Thẻ tóm tắt thông số: Tổng số Shot, Tổng số Keyframe, Thời lượng (Duration), Tốc độ khung hình (FPS).
* **Main Left Pane (Khu vực Trình phát & Dòng thời gian):**
  * Video Player HTML5 với thanh điều khiển mượt mà.
  * **Interactive Shot Bar (Mini Timeline):** Nằm ngay dưới video, chia tỷ lệ chiều rộng theo tổng thời lượng video. Mỗi shot là một block màu, khi rê chuột hiển thị thông tin tooltip, khi click sẽ tua video tới vị trí shot.
  * Bộ nút điều hướng nhanh: `[|<< Shot Trước]` `[Shot Tiếp Theo >>]` `[Nhảy đến Keyframe Chính]`.
* **Main Right Pane (Danh sách Thẻ Shot & Keyframe cuộn được):**
  * Danh sách phân trang hoặc cuộn vô tận các Shot cards.
  * Thẻ Shot hiển thị: `Shot #{id}: {start_sec}s - {end_sec}s ({duration_sec}s)`.
  * Lưới thu nhỏ chứa các Keyframe của shot đó kèm nhãn `CENTER` hoặc `SAMPLE` và điểm độ nét `blur`.
  * Trạng thái `is-active`: Khi video đang phát đến mốc giây nằm trong shot nào, thẻ shot đó sẽ phát sáng viền và tự động cuộn vào giữa màn hình.

---

## 3. Sơ đồ Luồng Hoạt động (ASCII Diagram)

```
[Trình duyệt Web (Local Browser)]
       │
       ├─► (1) GET /api/videos ──────────► [FastAPI Server] ──► [metadata.db] (Đọc video đã xử lý)
       │
       ├─► (2) GET /api/videos/{id}/shots ─► [FastAPI Server] ──► [metadata.db] (Gộp Shot + Keyframe)
       │
       ├─► (3) GET /api/stream/{id} ──────► [FastAPI Server] ──► [data/raw_videos/{id}.mp4] (Stream Range 206)
       │
       └─► (4) GET /api/keyframes/... ────► [FastAPI Server] ──► [data/keyframes/{id}/*.jpg]
```

---

## 4. Kế hoạch Kiểm thử & Tiêu chí Nghiệm thu (Acceptance Criteria)

* [ ] Khởi chạy máy chủ nhanh chóng qua lệnh: `uv run python -m src.ui.debug_server` (hoặc script CLI).
* [ ] Tự động nhận diện video `L13_V001` (đã hoàn thành trong Task 01 với 292 shot và 344 keyframe).
* [ ] Video chạy trơn tru, tua mượt mà không bị nghẽn mạng hay tràn RAM.
* [ ] Nhấp vào shot bất kỳ trên thanh timeline hoặc danh sách -> Video nhảy chính xác đến giây bắt đầu của shot.
* [ ] Nhấp vào keyframe bất kỳ -> Video nhảy chính xác đến giây của keyframe và hình ảnh trên video khớp với ảnh thumbnail keyframe.
* [ ] Mức chiếm dụng GPU VRAM là 0MB; CPU tải dưới 10% khi stream.

---

## 5. Sản phẩm Đầu ra (Deliverables)
1. Mã nguồn Backend: `src/ui/debug_server.py`.
2. Mã nguồn Frontend: `src/ui/static/debug.html`, `src/ui/static/debug.css`, `src/ui/static/debug.js` (hoặc gói gọn trong single template tối ưu).
3. Hướng dẫn chạy và gỡ lỗi trong tài liệu.
