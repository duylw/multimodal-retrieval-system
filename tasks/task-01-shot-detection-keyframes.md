# Task 01: Phân đoạn Cảnh (Shot Boundary Detection) và Chọn Keyframe Thích ứng

## 1. Mục tiêu (What)
* Phân đoạn video thành các cảnh quay liên tục (shots) bằng mô hình **TransNetV2** (hoặc `PySceneDetect` nếu cần phương án dự phòng nhẹ hơn).
* Xây dựng thuật toán **Chọn Keyframe thích ứng (Adaptive Keyframe Selection)**:
  * Không lấy cố định 1 frame mỗi N giây để tránh lãng phí ở cảnh tĩnh và bỏ sót ở cảnh động.
  * Shot ngắn (dưới 3 giây) hoặc ít chuyển động: Trích 1 keyframe ở giữa shot.
  * Shot dài hoặc có biến động lớn: Trích từ 2 đến tối đa 6 keyframe.
* Bộ lọc chất lượng ảnh: Loại bỏ frame quá tối/đen, frame bị mờ do chuyển động (motion blur bằng phương sai Laplacian) và các frame trùng lặp trong cùng shot.
* Lưu thông tin phân đoạn vào cơ sở dữ liệu `metadata.db` (SQLite).

---

## 2. Các bước thực hiện (How)

### Bước 2.1: Phân đoạn Cảnh bằng TransNetV2
* Đầu vào: Đường dẫn tệp video `.mp4`.
* Trích xuất danh sách các khoảng shot: `[(start_frame, end_frame, start_sec, end_sec), ...]`.
* Cơ chế lưu đệm (Caching): Lưu kết quả tách shot ra file JSON hoặc bảng SQLite `shots` để nếu chạy lại không cần decode video lần hai.

### Bước 2.2: Thuật toán Lọc và Chọn Keyframe
1. **Lấy frame ứng viên:**
   * Chia shot thành các khoảng đều nhau dựa theo thời lượng:
     * Dưới 3 giây: 1 frame ở vị trí 50% thời lượng.
     * 3 đến 8 giây: 2 frame ở vị trí 33% và 66%.
     * Trên 8 giây: Cứ mỗi 3-4 giây lấy 1 frame (tối đa 6 frame).
2. **Kiểm tra độ mờ (Blur Detection):**
   * Tính phương sai của toán tử Laplacian trên ảnh xám: `cv2.Laplacian(gray_frame, cv2.CV_64F).var()`.
   * Nếu giá trị nhỏ hơn ngưỡng (ví dụ: < 80.0), frame bị mờ -> tìm frame lân cận trong khoảng +/- 5 frame có độ nét cao nhất để thay thế.
3. **Kiểm tra ảnh tối/đen (Black/Blank Frame):**
   * Tính độ sáng trung bình của ảnh: `np.mean(gray_frame)`.
   * Nếu độ sáng < 15/255 -> bỏ qua frame.
4. **Kiểm tra trùng lặp (Deduplication):**
   * Tính khoảng cách Cosine hoặc tương đồng Histogram màu sắc giữa các frame trong cùng một shot.
   * Nếu độ tương đồng > 0.95 -> chỉ giữ lại 1 frame đại diện.

### Bước 2.3: Lưu trữ Ảnh và Metadata
* Lưu ảnh keyframe nén dạng JPEG chất lượng 85 (kích thước tối đa chiều dài 720px để tiết kiệm đĩa cứng) vào thư mục:
  `data/keyframes/{video_id}/shot_{shot_id}_frame_{frame_idx}.jpg`
* Ghi vào bảng `keyframes` trong SQLite:
  `keyframe_id`, `video_id`, `shot_id`, `timestamp_sec`, `file_path`, `is_shot_center`.

---

## 3. Quy trình Kiểm thử (How to Test)
1. **Kiểm thử Đơn vị trên 1 Video Ngắn (2-3 phút):**
   * Chạy script: `python -m src.extractors.shots --video tests/sample_cooking.mp4`
   * Kiểm tra đầu ra:
     * Số lượng shot được nhận diện có đúng với số lần chuyển cảnh thực tế của video không?
     * Mở thư mục ảnh keyframe vừa sinh ra: Kiểm tra xem có frame nào bị đen xì, nhòe mờ hay bị cắt giữa chừng 2 cảnh (dissolve) không.
2. **Đo đạc Tốc độ (Speed Benchmark):**
   * Đo thời gian xử lý: Tốc độ decode + tách shot phải đạt tối thiểu từ **60 đến 120 FPS** trên CPU/NVDEC.
   * Tiêu chí đạt: Video 3 phút (180 giây) xử lý xong trong dưới 15 giây.
