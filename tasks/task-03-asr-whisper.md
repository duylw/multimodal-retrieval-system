# Task 03: Xử lý Lời thoại (ASR) với faster-whisper và Lập chỉ mục Kép (BM25 + Dense)

## 1. Mục tiêu (What)
* Tách dải âm thanh từ video sang định dạng WAV 16kHz Mono.
* Sử dụng **Silero-VAD** (Voice Activity Detection) để lọc bỏ toàn bộ các đoạn im lặng hoặc chỉ có nhạc nền nhằm ngăn ngừa hiện tượng "bịa chữ" (hallucination) của Whisper.
* Phiên âm tiếng Việt chính xác kèm mốc thời gian bắt đầu và kết thúc (`start_sec`, `end_sec`) bằng mô hình **`faster-whisper`** (bản `large-v3-turbo` cấu hình `int8` trên GPU).
* Xây dựng chỉ mục tìm kiếm kép (Hybrid Search):
  * **Chỉ mục từ khóa (Lexical):** BM25 hoặc SQLite FTS5 cho các truy vấn khớp từ chính xác.
  * **Chỉ mục ngữ nghĩa (Dense):** Vector embedding bằng mô hình đa ngôn ngữ `bge-m3` để xử lý các từ đồng nghĩa (ví dụ: "giảm giá" khớp với "khuyến mãi", "thịt lợn" khớp với "thịt heo").
* Tự động xóa file WAV tạm sau khi phiên âm xong để bảo vệ dung lượng đĩa cứng 150GB.

---

## 2. Các bước thực hiện (How)

### Bước 2.1: Trích xuất Âm thanh và Lọc VAD
1. **Trích xuất Audio bằng ffmpeg:**
   * Sử dụng lệnh ngầm hoặc thư viện `av`:
     `ffmpeg -i input.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 temp.wav`
2. **Lọc khoảng lặng bằng Silero VAD:**
   * Chia audio thành các đoạn có tiếng người nói (speech segments).
   * Bỏ qua các đoạn không có tiếng nói để không phải chạy qua Whisper, tiết kiệm 30-50% thời gian xử lý.

### Bước 2.2: Phiên âm bằng faster-whisper
1. **Khởi tạo Whisper Turbo:**
   ```python
   from faster_whisper import WhisperModel
   model = WhisperModel("large-v3-turbo", device="cuda", compute_type="int8")
   ```
2. **Chạy phiên âm:**
   * Cấu hình ngôn ngữ tiếng Việt: `language="vi"`.
   * Trích xuất danh sách các câu: `[{start: 12.4, end: 16.8, text: "hôm nay chúng ta cùng vào bếp..."}]`.
3. **Lưu trữ vào SQLite:**
   * Bảng `transcripts`: `segment_id`, `video_id`, `start_sec`, `end_sec`, `text_raw`, `text_normalized`.
4. **Dọn dẹp đĩa:** Gọi `os.remove("temp.wav")` ngay sau khi ghi xong vào cơ sở dữ liệu.

### Bước 2.3: Lập Chỉ mục Kép cho Lời thoại
1. **Chỉ mục Từ khóa (BM25 / SQLite FTS5):**
   * Sử dụng SQLite FTS5 với tokenizer unicode61 (hỗ trợ tiếng Việt có dấu và không dấu).
2. **Chỉ mục Ngữ nghĩa (bge-m3):**
   * Chuyển từng đoạn câu thành vector 1024 chiều bằng mô hình `BAAI/bge-m3`.
   * Lưu các vector này vào một chỉ mục FAISS riêng: `data/indices/asr_bge_m3.index`.

---

## 3. Quy trình Kiểm thử (How to Test)

1. **Kiểm thử Phiên âm Đơn lẻ trên 1 Video có Giọng nói (3-5 phút):**
   * Chạy script: `python -m src.extractors.speech --video tests/sample_news.mp4`
   * Kiểm tra đầu ra:
     * File WAV tạm có bị xóa sạch sau khi xử lý không?
     * Mở các dòng văn bản ghi nhận trong SQLite: Tiếng Việt có chuẩn dấu không? Các danh từ riêng (tên địa danh, tên người) có bị sai lệch nghiêm trọng không?
     * So sánh thời điểm phát câu nói trong video thực tế với `start_sec` và `end_sec` xem sai số có dưới 1 giây không.
2. **Kiểm thử Tìm kiếm Thử nghiệm:**
   * Thử tìm từ khóa chính xác: `"khuyến mãi cuối tuần"` -> kiểm tra BM25 có trả về đúng đoạn MC nói không.
   * Thử tìm câu đồng nghĩa: `"cách tẩm gia vị"` -> kiểm tra bge-m3 có khớp với đoạn nói *"hướng dẫn ướp thịt"* không.
