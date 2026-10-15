# Task 00: Thiết lập Môi trường và Bộ Đánh giá Đo lường (Benchmark & Evaluation)

## 1. Mục tiêu (What)
* Thiết lập môi trường ảo Python 3.10 tương thích CUDA cho card đồ họa NVIDIA GeForce GTX 1650 (CUDA 11.8 hoặc 12.x).
* Cài đặt các gói thư viện cơ bản cần thiết cho dự án.
* Xây dựng bộ dữ liệu đánh giá chuẩn (Ground Truth Benchmark) gồm 30-50 câu truy vấn đa dạng (thời sự, phóng sự, nấu ăn...) kèm mốc thời gian đúng (video_id, start_sec, end_sec).
* Viết script đo lường tự động: Recall@1, Recall@5, Recall@10 và MRR (Mean Reciprocal Rank).

---

## 2. Các bước thực hiện (How)

### Bước 2.1: Khởi tạo Môi trường Ảo và Cài đặt Gói với uv
* Khởi tạo môi trường ảo với `uv`:
  ```powershell
  uv venv
  .\.venv\Scripts\Activate.ps1
  ```
* Quản lý gói thư viện qua `pyproject.toml`:
  * Cài đặt PyTorch hỗ trợ CUDA (GTX 1650 tương thích CUDA 11.8 hoặc 12.x):
    ```powershell
    uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
    ```
  * Thêm các thư viện xử lý và mô hình vào dự án:
    ```powershell
    uv add av opencv-python loguru pyyaml pydantic tqdm fastapi uvicorn
    uv add transformers accelerate sentence-transformers faster-whisper faiss-cpu
    ```
  * Chạy script kiểm tra: `uv run python -c "import torch; print(torch.cuda.is_available())"`
* Lưu ý: File `requirements.txt` ở thư mục gốc được dùng riêng cho việc dọn dẹp hệ thống, không dùng trong dự án. Toàn bộ dependency quản lý qua `pyproject.toml`.

### Bước 2.2: Thiết kế Tập Ground Truth (`data/ground_truth.json`)
* Chọn ngẫu nhiên 5-10 video mẫu đại diện (thời lượng 20-30 phút mỗi video).
* Xây dựng danh sách 30-50 câu hỏi tiếng Việt thuộc các nhóm:
  * **Nhóm 1 (Thuần hình ảnh):** "cận cảnh đĩa thịt bò xào ớt chuông", "người mặc áo vàng đi qua ngã tư".
  * **Nhóm 2 (Thuần lời thoại):** "phát thanh viên đọc bản tin giá vàng hôm nay", "đầu bếp nhắc nhở không nên nêm quá nhiều muối".
  * **Nhóm 3 (Chữ trên màn hình):** "bảng giá niêm yết của nhà hàng", "tỉ số trận đấu bóng đá hiển thị ở góc màn hình".
  * **Nhóm 4 (Đa phương thức kết hợp):** "người phỏng vấn cầm micro đứng trước tòa nhà UBND tỉnh".
* Định dạng tệp `ground_truth.json`:
  ```json
  [
    {
      "query_id": "q01",
      "query": "hướng dẫn ướp thịt bò trước khi xào",
      "video_file": "nau_an_01.mp4",
      "target_interval": [145.0, 180.0],
      "modality_expected": ["visual", "speech"]
    }
  ]
  ```

### Bước 2.3: Viết Script Đánh giá (`src/evaluation/evaluate.py`)
* Logic tính **Hit**: Một kết quả dự đoán với timestamp `t_pred` được tính là Hit nếu:
  * `t_pred >= (target_start - 5.0)` VÀ `t_pred <= (target_end + 5.0)`.
* Tính **Recall@K**: Tỷ lệ phần trăm câu hỏi có ít nhất 1 Hit trong Top-K kết quả.
* Tính **MRR (Mean Reciprocal Rank)**: Trung bình cộng của `1.0 / rank_first_hit` (nếu không có hit trong top danh sách, điểm là 0).

---

## 3. Quy trình Kiểm thử (How to Test)
1. **Kiểm tra GPU & PyTorch:**
   * Chạy lệnh kiểm tra `torch.cuda.is_available()` và in tên GPU `torch.cuda.get_device_name(0)`.
   * Tiêu chí đạt: Trả về `True` và hiển thị `GeForce GTX 1650`.
2. **Kiểm tra Script Đo lường (`evaluate.py`):**
   * Tạo một danh sách kết quả giả lập (dummy predictions): gồm 10 dự đoán cố ý đúng và 10 dự đoán sai lệch thời gian.
   * Chạy `python src/evaluation/evaluate.py --pred dummy_predictions.json --gt data/ground_truth.json`.
   * Tiêu chí đạt: Bảng kết quả in ra rõ ràng các chỉ số `Recall@1`, `Recall@5`, `Recall@10`, `MRR` không có lỗi chia cho 0 hay lỗi ngoại lệ.
