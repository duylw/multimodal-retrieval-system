# Task 02: Trích xuất Vector Hình ảnh SigLIP2 và Lập Chỉ mục FAISS

## 1. Mục tiêu (What)
* Chuyển đổi toàn bộ ảnh keyframe thành các vector ngữ nghĩa (visual embeddings) bằng mô hình **SigLIP2** (thử nghiệm bản `so400m/384` với fallback sang `base-patch16-256` nếu quá tải VRAM).
* Tính toán thêm **Vector trung bình theo cảnh (Shot-level Average Embedding)** để đại diện cho toàn bộ ngữ cảnh của một cảnh quay.
* Lập chỉ mục tìm kiếm siêu nhanh bằng thư viện **FAISS** (`IndexFlatIP` - Inner Product với vector chuẩn hóa L2 tương đương Cosine Similarity).
* Xây dựng pipeline tra cứu văn bản sang hình ảnh (Text-to-Visual Search) hỗ trợ truy vấn tiếng Anh và tiếng Việt (qua module dịch).

---

## 2. Các bước thực hiện (How)

### Bước 2.1: Quản lý VRAM và Batch Inference
1. **Khởi tạo Mô hình:**
   * Sử dụng thư viện `transformers` với `torch.float16`:
     ```python
     from transformers import AutoModel, AutoProcessor
     model_name = "google/siglip2-so400m-patch14-384"  # Fallback: "google/siglip2-base-patch16-256"
     model = AutoModel.from_pretrained(model_name, torch_dtype=torch.float16).to("cuda")
     processor = AutoProcessor.from_pretrained(model_name)
     ```
2. **Cơ chế Batching an toàn:**
   * Đối với bản 400m: Cấu hình `batch_size = 4` hoặc `batch_size = 8`.
   * Đối với bản base: Cấu hình `batch_size = 16` hoặc `batch_size = 32`.
   * Luôn gọi `torch.cuda.empty_cache()` sau mỗi video để tránh tích tụ bộ nhớ rác.
3. **Chuẩn hóa Vector (L2 Normalization):**
   * Mọi vector trích xuất ra từ ảnh đều phải được chia cho độ dài L2: `vec = vec / np.linalg.norm(vec, axis=-1, keepdims=True)`.

### Bước 2.2: Tính Vector Trung bình Shot (Shot-level Pooling)
* Trong một shot có từ 2 đến 6 keyframe:
  * Lấy trung bình cộng của các vector keyframe trong shot.
  * Tiếp tục chuẩn hóa L2 cho vector trung bình này.
  * Lưu trữ cả vector từng keyframe và vector đại diện shot vào chỉ mục để tăng độ bền vững khi người dùng mô tả cả một chuỗi hành động.

### Bước 2.3: Xây dựng Chỉ mục FAISS
* Sử dụng cấu trúc `faiss.IndexFlatIP(embedding_dim)` (chỉ số tích vô hướng giữa 2 vector chuẩn hóa L2 chính là độ tương đồng Cosine).
* Lưu chỉ mục ra đĩa: `data/indices/visual_siglip2.index`.
* Xây dựng bảng ánh xạ `id_map.json` hoặc bảng SQLite `faiss_visual_map`:
  `faiss_id -> {video_id, shot_id, keyframe_id, timestamp_sec}`.

---

## 3. Quy trình Kiểm thử (How to Test)

1. **Đo đạc Tốc độ & Giám sát VRAM:**
   * Chạy script trích xuất trên 100 ảnh keyframe đầu tiên.
   * Quan sát qua lệnh `nvidia-smi` trong terminal:
     * Mức sử dụng VRAM đỉnh có vượt quá 3.5GB hay không?
     * Tốc độ xử lý đạt bao nhiêu ảnh/giây?
   * Tiêu chí đạt: VRAM an toàn dưới 3.2GB và tốc độ đạt tối thiểu từ 4-6 ảnh/giây (với bản 400m) hoặc trên 20 ảnh/giây (với bản base).
2. **Kiểm thử Truy vấn Ngữ nghĩa Đơn lẻ:**
   * Đưa vào câu truy vấn tiếng Anh mẫu:
     * Query: `"a close-up shot of chopping onions"`
     * Query: `"a red car turning left at crossroad"`
   * Thực hiện tìm kiếm Top 5 kết quả trong FAISS.
   * Hiển thị đường dẫn 5 ảnh trả về: Kiểm tra xem nội dung ảnh có đúng với câu mô tả không.
3. **Đánh giá Baseline Recall:**
   * Chạy script `evaluate.py` với nguồn truy xuất chỉ lấy từ kênh Visual SigLIP2.
   * Ghi lại chỉ số `Visual_Only_Recall@10` làm mốc so sánh (Baseline) cho đồ án.
