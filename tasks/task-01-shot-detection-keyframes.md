# Task 01: Phân đoạn Cảnh (Shot Boundary Detection) và Chọn Keyframe Thích ứng

## 1. Mục tiêu (What)
* Phân đoạn video thành các cảnh quay liên tục (shots) bằng mô hình **TransNetV2** (hoặc `PySceneDetect` nếu cần phương án dự phòng nhẹ hơn).
* **Xử lý chuẩn hóa FPS đa dạng (FPS Normalization):**
  * Tương thích với mọi định dạng FPS đầu vào (24, 25, 30, 50, 60 FPS).
  * Chuẩn hóa tốc độ quét cảnh về mức an toàn 25 FPS để giảm 50% thời gian xử lý trên video 60 FPS mà không giảm độ chính xác.
* **Xây dựng thuật toán Chọn Keyframe thích ứng theo Thời gian Thực (Time-based Adaptive Keyframe Selection):**
  * Lấy mẫu dựa trên độ dài thời gian thực của shot (seconds), độc lập hoàn toàn với số lượng frame.
  * Shot ngắn (dưới 3 giây) hoặc ít biến động: Trích 1 keyframe ở giữa shot (50% thời lượng).
  * Shot trung bình (3 đến 8 giây): Trích 2 keyframe ở 33% và 66% thời lượng.
  * Shot dài hoặc nhiều biến động (trên 8 giây): Cứ mỗi 3-4 giây lấy 1 frame (tối đa 6 frame).
  * Đảm bảo tổng số lượng keyframe toàn bộ 100GB video luôn giữ ở ngưỡng an toàn **60.000 - 80.000 ảnh**, không bị đội dung lượng khi gặp video FPS cao.
* **Bộ lọc chất lượng ảnh:**
  * Loại bỏ frame quá tối/đen (độ sáng trung bình < 15/255).
  * Loại bỏ frame bị nhòe mờ chuyển động (motion blur bằng phương sai Laplacian < 80.0) và tìm frame nét lân cận thay thế.
  * Loại bỏ frame trùng lặp trong cùng một shot (độ tương đồng màu > 0.95).
* Lưu thông tin phân đoạn và metadata ảnh vào cơ sở dữ liệu `metadata.db` (SQLite).

---

## 2. Các bước thực hiện (How)

### Bước 2.1: Chuẩn hóa FPS và Giải mã Video Tối ưu
1. **Nguyên tắc Quản trị theo Trục Thời gian Thực (Time-based Indexing):**
   * Đọc metadata của video để lấy chính xác thông số `fps = cap.get(cv2.CAP_PROP_FPS)`.
   * Mọi mốc thời gian đều được tính bằng giây thực tế: `timestamp_sec = frame_idx / fps`.
   * Không dùng số thứ tự frame (`frame_idx`) làm định danh tìm kiếm vì video 25 FPS và 60 FPS có frame count khác nhau hoàn toàn ở cùng một giây.
2. **Kỹ thuật Frame-skipping cho Video FPS Cao khi Tách Cảnh:**
   * TransNetV2 hoạt động tối ưu ở dải 25 - 30 FPS.
   * Nếu video đầu vào có `fps > 30` (ví dụ 50 hoặc 60 FPS):
     * Tính bước nhảy khung hình: `stride = round(fps / 25.0)`.
     * Chỉ nạp các frame cách nhau một khoảng `stride` vào TransNetV2.
     * Quy đổi kết quả index về lại giây chuẩn xác: `shot_start_sec = (sampled_idx * stride) / fps`.
     * Tiết kiệm 50% thời gian suy luận của mô hình trên các video tốc độ cao.
3. **Giải mã Tăng tốc Phần cứng (Hardware Decoding):**
   * Ưu tiên sử dụng PyAV với giải mã phần cứng NVDEC trên card GTX 1650 khi khả dụng để đạt tốc độ giải mã từ 300 đến 600 FPS.

### Bước 2.2: Thuật toán Chọn Keyframe Thích ứng theo Giây (Time-Interval Sampling)
1. **Lấy frame ứng viên theo độ dài thời gian thực (`duration_sec = end_sec - start_sec`):**
   * `duration_sec < 3.0`: Trích 1 frame tại `start_sec + 0.5 * duration_sec`.
   * `3.0 <= duration_sec <= 8.0`: Trích 2 frame tại `start_sec + 0.33 * duration_sec` và `start_sec + 0.66 * duration_sec`.
   * `duration_sec > 8.0`: Lấy mẫu đều đặn mỗi 3.5 giây một frame (tối đa không quá 6 frame cho một shot).
   * **Lợi ích:** Dù video quay ở 25 FPS hay 60 FPS, số lượng ảnh keyframe trích xuất ra của cùng một cảnh quay là hoàn toàn như nhau.
2. **Bộ lọc Kiểm tra Độ mờ (Laplacian Blur Detection):**
   * Tính phương sai của toán tử Laplacian trên ảnh xám: `cv2.Laplacian(gray_frame, cv2.CV_64F).var()`.
   * Nếu điểm nét < 80.0 (frame bị rung tay, nhòe mờ) -> Quét tìm trong phạm vi thời gian cộng trừ 0.2 giây xung quanh để chọn frame có độ nét cao nhất thay thế.
3. **Bộ lọc Kiểm tra Ảnh Tối/Đen:**
   * Tính độ sáng trung bình: `np.mean(gray_frame)`. Nếu < 15/255 -> Bỏ qua frame.
4. **Bộ lọc Trùng lặp (Deduplication):**
   * So sánh histogram màu HSV giữa các frame trong cùng một shot. Nếu độ tương đồng > 0.95 -> Chỉ giữ lại 1 frame tiêu biểu.

### Bước 2.3: Lưu trữ Ảnh và Ghi nhận Metadata vào SQLite
* Lưu ảnh keyframe nén dạng JPEG chất lượng 85, chiều dài tối đa 720px để bảo vệ đĩa cứng 150GB:
  `data/keyframes/{video_id}/shot_{shot_id}_t{timestamp_sec:.2f}.jpg`
* Bảng SQLite `shots`:
  `shot_id`, `video_id`, `start_frame`, `end_frame`, `start_sec`, `end_sec`, `duration_sec`, `fps`.
* Bảng SQLite `keyframes`:
  `keyframe_id`, `video_id`, `shot_id`, `timestamp_sec`, `file_path`, `is_shot_center`, `blur_score`.
* Đánh dấu cờ `processed` cho video trong bảng `processed_videos` để đảm bảo khả năng resume nếu bị gián đoạn.

---

## 3. Quy trình Kiểm thử (How to Test)

1. **Kiểm thử Đồng bộ Thời gian với Video Mẫu `L13_V001.mp4` (25 FPS):**
   * Chạy script kiểm thử: `python -m src.extractors.shots --video data/raw_videos/L13_V001.mp4`
   * Kiểm tra đầu ra:
     * Tốc độ quét cảnh TransNetV2 đạt trên 100 FPS.
     * Mọi mốc thời gian `start_sec` và `end_sec` tính ra đều khớp chính xác với hình ảnh khi mở video kiểm tra thực tế.
2. **Kiểm thử Quy tắc Chống Bùng nổ Keyframe:**
   * Giả lập video 25 FPS và 60 FPS có cùng thời lượng 10 giây.
   * Kiểm tra: Số lượng keyframe sinh ra ở cả hai video phải bằng nhau (tối đa 2-3 frame), chứng minh thuật toán không bị phụ thuộc vào FPS.
3. **Kiểm tra Chất lượng Ảnh Keyframe Trích xuất:**
   * Mở trực quan thư mục ảnh: Không có frame nào bị đen xì, mờ nhòe do camera lia nhanh, hoặc bị cắt giữa chừng khi chuyển cảnh.
