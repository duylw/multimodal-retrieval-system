# Task 04: Trích xuất Chữ trên Màn hình (OCR) với PaddleOCR trên CPU

## 1. Mục tiêu (What)
* Đọc toàn bộ các chữ xuất hiện trên màn hình video: Tiêu đề chương trình, bảng tin tức chạy bên dưới (ticker), biển hiệu đường phố, tên món ăn, bảng nguyên liệu, tỉ số thể thao...
* Xây dựng bộ lọc phát hiện vùng có chữ (Text Presence Detector) để **loại bỏ 70-80% các frame không chứa văn bản**, giúp giảm thiểu tối đa thời gian chạy OCR.
* Chạy mô hình **PaddleOCR (tiếng Việt)** hoàn toàn trên **CPU đa luồng (Multi-threading)** song song với quá trình GPU xử lý tác vụ khác, không tốn thêm 1 MB VRAM nào.
* Lưu trữ văn bản nhận dạng được kèm mốc thời gian vào cơ sở dữ liệu SQLite FTS5 để hỗ trợ tìm kiếm toàn văn siêu tốc.

---

## 2. Các bước thực hiện (How)

### Bước 2.1: Bộ lọc Phát hiện Khung hình Chứa Chữ (Text Presence Filter)
* Chạy một thuật toán xử lý ảnh hình thái học (Morphological Operations) hoặc phát hiện cạnh (Canny / Sobel gradient) trên CPU:
  * Văn bản trên màn hình luôn tạo ra các vùng có mật độ cạnh đứng và biến thiên độ sáng cục bộ rất cao trong một khung hẹp (Text-like edge density).
  * Nếu mật độ vùng cạnh tập trung thấp hơn ngưỡng -> đánh dấu frame là `no_text` và bỏ qua, không gọi mô hình PaddleOCR.
  * Nhờ bước này, trong 80.000 keyframe, chỉ cần chạy OCR cho khoảng 15.000 - 25.000 keyframe thực sự có chữ.

### Bước 2.2: Nhận diện Chữ bằng PaddleOCR
1. **Khởi tạo PaddleOCR trên CPU:**
   ```python
   from paddleocr import PaddleOCR
   ocr_engine = PaddleOCR(use_angle_cls=True, lang='vi', use_gpu=False, show_log=False)
   ```
2. **Quy trình Nhận diện:**
   * Đầu vào: Ảnh keyframe.
   * Lọc kết quả: Chỉ giữ lại các từ/cụm từ có điểm tin cậy `confidence >= 0.65`.
   * Hậu xử lý văn bản: Loại bỏ các ký tự rác ngẫu nhiên (nhiễu), chuẩn hóa dấu tiếng Việt (ví dụ: "hoà" -> "hòa").
3. **Lưu trữ vào SQLite:**
   * Bảng `ocr_records`:
     `ocr_id`, `video_id`, `keyframe_id`, `timestamp_sec`, `text_detected`, `bbox`, `confidence`.

### Bước 2.3: Lập Chỉ mục Tìm kiếm Toàn văn (SQLite FTS5)
* Tạo bảng ảo FTS5 hỗ trợ tiếng Việt:
  ```sql
  CREATE VIRTUAL TABLE ocr_fts USING fts5(
      video_id UNINDEXED,
      timestamp_sec UNINDEXED,
      text_detected,
      tokenize = 'unicode61'
  );
  ```
* Bổ sung tính năng tìm kiếm gần đúng (Fuzzy Search / Prefix Search) cho các từ khóa gõ tắt hoặc bị OCR nhận diện thiếu 1-2 ký tự.

---

## 3. Quy trình Kiểm thử (How to Test)

1. **Kiểm thử Đơn vị trên 10 Frame Mẫu có Chữ:**
   * Lựa chọn 10 frame: gồm 5 frame có tiêu đề tin tức / bảng giá và 5 frame ngoại cảnh không có chữ.
   * Chạy script: `python -m src.extractors.ocr --test_frames`
   * Tiêu chí đạt:
     * Bộ lọc phải phân loại đúng 5 frame không có chữ (không tốn thời gian gọi OCR).
     * 5 frame có chữ phải nhận dạng đúng ít nhất 85% các từ vựng tiếng Việt có dấu.
2. **Đo đạc Tốc độ trên CPU:**
   * Đo thời gian trung bình xử lý 1 frame trên CPU: Mục tiêu dưới 150ms/frame đối với các frame có chữ và dưới 10ms đối với frame không có chữ.
3. **Kiểm thử Tìm kiếm Thực tế:**
   * Nhập vào câu hỏi tìm một biển hiệu hoặc bảng giá chỉ có trên hình ảnh (không ai đọc trong lời thoại).
   * Kiểm tra xem hệ thống có trả về chính xác giây xuất hiện của dòng chữ đó không.
