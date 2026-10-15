# Task 06: Giao diện Người dùng Web và Vòng lặp Phản hồi Tương tác (UI & Relevance Feedback)

## 1. Mục tiêu (What)
* Xây dựng giao diện web tìm kiếm trực quan, hiện đại bằng **FastAPI** (Backend) và **HTML/CSS/JavaScript thuần** (Frontend).
* Cho phép người dùng nhập truy vấn tiếng Việt, chọn lọc kênh tìm kiếm và xem kết quả xếp hạng.
* Trình phát video HTML5 thông minh: Hỗ trợ tua ngay lập tức đến đúng mốc thời gian (`currentTime = start_sec`) khi người dùng nhấp vào kết quả.
* Hiện thực hóa tính năng **Phản hồi Tương tác (Relevance Feedback)**:
  * Nút "Đúng cảnh này / Tìm cảnh tương tự" (Positive Feedback).
  * Nút "Bỏ qua cảnh này" (Negative Feedback).
  * Cập nhật lại vector truy vấn bằng thuật toán Rocchio đơn giản để tái xếp hạng (Re-ranking) kết quả ngay lập tức mà không cần nạp lại mô hình.

---

## 2. Các bước thực hiện (How)

### Bước 2.1: Xây dựng Backend API (FastAPI)
1. **Endpoint Tìm kiếm (`/api/search`):**
   * Nhận câu hỏi, tham số bộ lọc kênh và số lượng kết quả mong muốn (`top_k`).
   * Gọi bộ `search_engine.py` và trả về JSON danh sách kết quả kèm mốc thời gian, điểm số và thông tin các kênh khớp (Visual, ASR, OCR).
2. **Endpoint Phát Video Streaming (`/api/video/{video_id}`):**
   * Hỗ trợ chuẩn **HTTP 206 Partial Content (Range Requests)**: Cho phép trình duyệt tải từng phần video và tua tới bất kỳ giây nào mà không phải tải toàn bộ file video dung lượng lớn vào RAM.
3. **Endpoint Phản hồi Tương tác (`/api/feedback`):**
   * Nhận `query_vector`, danh sách `positive_keyframe_ids` và `negative_keyframe_ids`.
   * Cập nhật vector truy vấn theo công thức Rocchio:
     `new_vector = 1.0 * old_vector + 0.75 * avg(positive_vectors) - 0.25 * avg(negative_vectors)`
   * Chuẩn hóa L2 cho `new_vector` và truy vấn lại trong FAISS.

### Bước 2.2: Thiết kế Giao diện Người dùng (Frontend)
* **Thanh tìm kiếm:** Ô nhập văn bản nổi bật kèm gợi ý câu hỏi mẫu.
* **Bộ lọc đa phương thức:** Checkbox bật/tắt từng kênh: [x] Hình ảnh, [x] Lời thoại, [x] Chữ màn hình.
* **Khu vực kết quả:**
  * Hiển thị dạng lưới thẻ (Cards).
  * Mỗi thẻ gồm: Ảnh thu nhỏ (Thumbnail keyframe), Tên video, Mốc thời gian (ví dụ `02:15 - 02:28`), Huy hiệu các kênh đóng góp (ví dụ: `[Hình ảnh] [Lời thoại]`), Thanh điểm tin cậy.
  * Hai nút bấm thao tác nhanh: "Phát từ giây này" và "Tìm tương tự".
* **Khu vực phát video:** Khung video cố định bên cạnh hoặc mở dạng modal với thanh tiến trình hiển thị đúng đoạn đang xét.

---

## 3. Quy trình Kiểm thử (How to Test)

1. **Kiểm thử API Streaming:**
   * Sử dụng lệnh `curl` hoặc kiểm tra trên tab Network của trình duyệt: Gửi header `Range: bytes=0-1048576` tới `/api/video/test.mp4`.
   * Tiêu chí đạt: Server phản hồi HTTP Status `206 Partial Content` kèm dữ liệu nhị phân chính xác.
2. **Kiểm thử Độ trễ Phản hồi (Search Latency):**
   * Gửi truy vấn tìm kiếm từ giao diện.
   * Đo thời gian phản hồi: Toàn bộ quá trình từ lúc bấm nút Tìm kiếm đến khi các thẻ kết quả hiển thị trên màn hình phải **dưới 1.5 giây**.
3. **Kiểm thử Tính năng Phản hồi Tương tác (Feedback):**
   * Tìm kiếm câu hỏi: `"cảnh đường phố đông đúc ban ngày"`.
   * Giả sử kết quả top 3 có một cảnh ban đêm. Người dùng nhấn nút "Sai cảnh này" trên frame ban đêm và nhấn "Tìm tương tự" trên frame ban ngày.
   * Tiêu chí đạt: Danh sách kết quả mới cập nhật ngay lập tức và loại bỏ các cảnh ban đêm xuống dưới, đưa thêm nhiều cảnh ban ngày lên top đầu.
