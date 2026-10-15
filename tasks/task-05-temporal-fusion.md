# Task 05: Hợp nhất Đa phương thức trên Trục Thời gian (Multimodal Temporal Fusion)

## 1. Mục tiêu (What)
* Xây dựng bộ phân tích truy vấn tự động (Query Parser): Phân tách câu hỏi của người dùng thành các luồng tìm kiếm tương ứng cho từng kênh (Visual, ASR, OCR).
* Giải quyết triệt để vấn đề **lệch thang đo điểm số (Score Incompatibility)** giữa Cosine Similarity (SigLIP2, bge-m3) và điểm BM25/FTS5.
* Hiện thực hóa giải thuật **Gộp điểm trên trục thời gian bằng Cửa sổ trượt (Sliding Window Temporal Alignment)** có độ dài 5 giây và bước dịch 2.5 giây để triệt tiêu hiện tượng xẻ đôi sự kiện (boundary cut).
* Gom cụm các đoạn thời gian liền kề (Temporal Clustering / Non-Maximum Suppression) để xuất ra danh sách các khoảnh khắc tối ưu nhất.

---

## 2. Các bước thực hiện (How)

### Bước 2.1: Bộ Phân tách Truy vấn (Query Parser)
* Áp dụng quy tắc Rule-based kết hợp từ điển thực thể (độ trễ < 1ms):
  1. **Nhánh OCR:** Nếu câu hỏi chứa từ trong dấu ngoặc kép (ví dụ: *"tìm quán 'Phở Hòa'"*) hoặc chứa các từ khóa đặc trưng ("chữ", "bảng hiệu", "tỉ số", "giá cả") -> đưa cụm từ này vào truy vấn SQLite FTS5.
  2. **Nhánh Lời thoại (ASR):** Nếu câu hỏi chứa các mẫu câu ("nói về", "giải thích", "phỏng vấn", "hát", "đọc tin") -> trích xuất phần nội dung đưa vào tìm kiếm BM25 và bge-m3.
  3. **Nhánh Hình ảnh (Visual):** Sử dụng toàn bộ câu mô tả, dịch sang tiếng Anh (sử dụng thư viện dịch offline `deep-translator` hoặc `Argos Translate` chạy local) -> đưa vào trích xuất vector SigLIP2.

### Bước 2.2: Chuẩn hóa Điểm số (Score Normalization)
* Tuyệt đối không cộng trực tiếp điểm thô của các kênh.
* Sử dụng phương pháp **Hợp nhất theo Thứ hạng Nghịch đảo (Reciprocal Rank Fusion - RRF)** kết hợp trọng số kênh:
  * Với mỗi kênh (Visual, ASR, OCR), lấy ra Top-100 kết quả có thứ hạng từ 1 đến 100.
  * Điểm chuẩn hóa của một mốc thời gian từ kênh đó được tính theo công thức:
    `score = weight_channel / (60 + rank)`
    * Trọng số tham khảo: `weight_visual = 1.0`, `weight_asr = 1.2`, `weight_ocr = 1.5` (chữ khớp chính xác thường có độ tin cậy rất cao).

### Bước 2.3: Gộp Điểm trên Trục Thời gian (Sliding Window Fusion)
1. **Khởi tạo Lưới thời gian (Time Grid):**
   * Với mỗi video có kết quả ứng viên, chia dòng thời gian thành các cửa sổ trượt: Kích thước 5 giây, bước dịch 2.5 giây (chồng lấn 50%).
   * Ví dụ: `[0 - 5s]`, `[2.5 - 7.5s]`, `[5 - 10s]`, `[7.5 - 12.5s]`...
2. **Cộng dồn Điểm vào Cửa sổ:**
   * Mỗi kết quả trả về từ keyframe hoặc đoạn thoại sẽ rót điểm vào các cửa sổ trượt mà nó thuộc về.
   * Cửa sổ nào được **nhiều kênh đồng thời chỉ vào** (ví dụ: vừa có hình ảnh đĩa thịt, vừa có tiếng MC nói về món thịt) sẽ có điểm số cộng dồn cao đột biến.
3. **Gom cụm và Lọc cực đại cục bộ (Temporal NMS):**
   * Nếu các cửa sổ trượt liền kề đều có điểm cao, gộp chúng lại thành một khoảng thời gian duy nhất: `[start_min, end_max]`.
   * Trả về danh sách Top-20 khoảnh khắc có điểm cao nhất toàn hệ thống.

---

## 3. Quy trình Kiểm thử (How to Test)

1. **Kiểm thử Hàm Gộp Điểm với Dữ liệu Giả lập:**
   * Tạo 3 danh sách giả lập cho cùng 1 video dài 60 giây:
     * Kênh Visual chỉ vào giây 15 (điểm cosine 0.35)
     * Kênh ASR chỉ vào khoảng 12-18 giây (BM25 score 18.5)
     * Kênh OCR chỉ vào giây 45 (FTS5 match)
   * Chạy hàm `fuse_scores()`:
     * Đoạn `12-18s` phải vươn lên đứng Top 1 vì có sự đồng thuận của cả 2 kênh Visual và ASR.
     * Kiểm tra xem các cửa sổ có bị xé nhỏ thành các mẩu 1 giây hay đã được gộp thành một đoạn liền mạch.
2. **Chạy Thử nghiệm Toàn diện (Ablation Study):**
   * Chạy `python src/evaluation/evaluate.py` trên bộ `ground_truth.json` gồm 30-50 câu hỏi.
   * Lập bảng so sánh kết quả:
     * Cấu hình 1: Chỉ Visual (Baseline)
     * Cấu hình 2: Visual + ASR
     * Cấu hình 3: Visual + OCR
     * Cấu hình 4: Toàn diện (Visual + ASR + OCR)
   * Tiêu chí đạt: Cấu hình toàn diện phải cho kết quả `Recall@10` cao hơn ít nhất từ 15% đến 30% so với cấu hình chỉ dùng Visual.
