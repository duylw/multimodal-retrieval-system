# Task 07: Kênh Âm thanh Môi trường với Mô hình CLAP (Giai đoạn 2)

## 1. Mục tiêu (What)
* Bổ sung kênh nhận diện **Âm thanh phi ngôn ngữ (Audio Events)** bằng mô hình **CLAP (Contrastive Language-Audio Pretraining)**.
* Xử lý các hiện tượng âm thanh trong video mà mô hình ASR (Whisper) hoàn toàn bỏ sót: Tiếng còi xe cứu thương/cảnh sát, tiếng mưa rơi, tiếng sấm sét, tiếng vỗ tay của khán giả, tiếng nhạc cụ (piano, guitar), tiếng sôi xèo xèo của chảo dầu...
* Chia audio thành các đoạn 10 giây (10-second audio chunks) và trích xuất vector đặc trưng âm thanh.
* Lập chỉ mục FAISS riêng cho âm thanh và tích hợp kênh này vào bộ giải thuật gộp điểm trên trục thời gian.

---

## 2. Các bước thực hiện (How)

### Bước 2.1: Cắt Audio và Trích xuất Vector CLAP
1. **Khởi tạo Mô hình CLAP:**
   * Sử dụng thư viện `msclap` hoặc mô hình HuggingFace `laion/larger_clap_general`:
     ```python
     from transformers import ClapModel, ClapProcessor
     model = ClapModel.from_pretrained("laion/larger_clap_general").to("cuda")
     processor = ClapProcessor.from_pretrained("laion/larger_clap_general")
     ```
2. **Cắt đoạn 10 giây có gối đầu (Sliding Window Audio):**
   * Mỗi đoạn dài 10 giây, bước nhảy 5 giây (overlap 50%).
   * Trích xuất vector đặc trưng âm thanh 512 chiều và chuẩn hóa L2.
3. **Lưu trữ Metadata:**
   * Ghi vào bảng `audio_segments` trong SQLite:
     `segment_id`, `video_id`, `start_sec`, `end_sec`, `audio_clap_faiss_id`.

### Bước 2.2: Lập Chỉ mục và Tích hợp Tìm kiếm
* Lập chỉ mục `faiss.IndexFlatIP(512)` lưu tại `data/indices/audio_clap.index`.
* Xử lý truy vấn: Khi người dùng tìm kiếm những câu có từ chỉ âm thanh (ví dụ: *"tiếng còi xe"*, *"tiếng mưa rơi"*, *"tiếng vỗ tay"*), bộ dịch sẽ chuyển sang tiếng Anh (ví dụ: *"sound of car horn"*, *"heavy rain sound"*) và truy vấn trực tiếp vào chỉ mục CLAP.
* Gộp điểm: Đoạn âm thanh 10 giây sẽ rót điểm vào các ô thời gian tương ứng trong bộ gộp điểm thời gian (Task 05).

---

## 3. Quy trình Kiểm thử (How to Test)

1. **Kiểm thử Đơn lẻ với Âm thanh Mẫu:**
   * Trích xuất một đoạn audio 10 giây có tiếng còi xe và 1 đoạn chỉ có tiếng nói bình thường.
   * Chạy truy vấn với câu text: `"sound of ambulance siren"`.
   * Tiêu chí đạt: Điểm tương đồng của đoạn còi xe phải vượt trội rõ rệt so với đoạn nói chuyện thông thường.
2. **Đánh giá Đóng góp vào Bộ Benchmark:**
   * Lọc riêng các câu truy vấn thuộc nhóm âm thanh trong tập `ground_truth.json`.
   * So sánh `Recall@10` trước và sau khi bổ sung kênh CLAP:
     * Trước khi có CLAP (chỉ dùng Visual + ASR): Các câu hỏi âm thanh thường có điểm recall rất thấp.
     * Sau khi có CLAP: `Recall@10` trên nhóm câu hỏi âm thanh phải tăng ít nhất 40%.
