# Thuật ngữ Chuyên ngành và Cơ chế Hoạt động (Glossary & Conceptual Guide)

Tài liệu này giải thích chi tiết toàn bộ các khái niệm kỹ thuật, thuật toán và nguyên lý hoạt động của các mô hình trí tuệ nhân tạo được sử dụng trong hệ thống **Truy xuất Video Đa phương thức (Multimodal Video Retrieval)**.

---

## 1. Các Khái niệm Xử lý Video (Video Processing Concepts)

### 1.1. Frame (Khung hình)
* **Khái niệm:** Một video thực chất là một chuỗi các bức ảnh tĩnh được trình chiếu liên tục với tốc độ cao (thường từ 24, 30 đến 60 ảnh/giây - FPS). Mỗi bức ảnh tĩnh đó được gọi là một **Frame**.
* **Ý nghĩa:** Video 1 giờ ở tốc độ 30 FPS chứa khoảng 108.000 frames. Việc nạp toàn bộ các frame này vào mô hình AI sẽ làm tê liệt phần cứng, do đó ta cần kỹ thuật trích xuất chọn lọc.

### 1.2. Shot (Cảnh quay đơn)
* **Khái niệm:** Một **Shot** là một đoạn video liên tục được ghi lại bởi một góc máy quay duy nhất, không bị ngắt quãng từ lúc bấm máy bắt đầu đến khi dừng máy (hoặc chuyển góc quay).
* **Phân biệt Shot và Scene:**
  * *Shot (Cảnh đơn):* Chuyển góc nhìn từ người phỏng vấn sang người trả lời là 2 shots khác nhau.
  * *Scene (Phân cảnh):* Toàn bộ cuộc phỏng vấn diễn ra trong căn phòng đó là 1 scene (chứa nhiều shots).
* **Điểm cắt cảnh (Cut transition):** Góc máy thay đổi đột ngột từ frame trước sang frame sau (Hard cut).
* **Điểm mờ chồng (Dissolve / Fade transition):** Cảnh trước mờ dần đồng thời cảnh sau hiện dần lên (Soft transition), hai cảnh bị trộn màu trong 5-15 frames.

### 1.3. Keyframe (Khung hình đại diện)
* **Khái niệm:** Là một hoặc vài frame tiêu biểu được chọn ra để đại diện cho nội dung thị giác của cả một shot.
* **Vì sao không lấy đều đặn "1 frame mỗi 3 giây"?**
  * Trong một cảnh tĩnh (ví dụ: người ngồi đọc sách suốt 30 giây), lấy 10 frame sẽ lãng phí 9 frame giống hệt nhau.
  * Trong một cảnh động nhanh (ví dụ: pha rượt đuổi xe trong 3 giây), lấy 1 frame duy nhất sẽ bỏ sót khoảnh khắc va chạm.
  * Do đó, hệ thống áp dụng **Adaptive Keyframe Selection** (Chọn keyframe thích ứng): cảnh tĩnh lấy 1 frame trung tâm, cảnh nhiều biến động lấy 2-6 frames.

### 1.4. Laplacian Blur Detection (Lọc ảnh mờ)
* **Khái niệm:** Toán tử Laplacian là một phép đạo hàm bậc hai dùng để đo mức độ biến thiên cường độ sáng nhanh hay chậm trong bức ảnh.
* **Nguyên lý:** Ảnh sắc nét có ranh giới viền (edges) rất rõ, tạo ra giá trị phương sai Laplacian cao. Ảnh bị rung lắc, nhòe mờ chuyển động (motion blur) có viền phẳng, phương sai Laplacian rất thấp. Nhờ đó ta lọc bỏ được các frame hỏng trước khi đưa vào mô hình.

---

## 2. Các Mô hình AI và Cách thức Hoạt động (AI Models & Mechanisms)

### 2.1. TransNetV2 (Shot Boundary Detection)
* **Nhiệm vụ:** Tìm chính xác thời điểm bắt đầu và kết thúc của từng shot trong video.
* **Cách thức hoạt động:**
  * Không dùng các thuật toán cổ điển như so sánh histogram màu (dễ bị đánh lừa khi camera di chuyển hoặc đèn nhấp nháy).
  * TransNetV2 sử dụng mạng tích chập không gian - thời gian 3D (3D CNN) nhận đầu vào là một chuỗi các frame liên tiếp (ví dụ: 50-100 frame) để học sự biến đổi thị giác theo chiều thời gian.
  * Mô hình cho ra xác suất chuyển cảnh cho từng frame, nhận diện tốt cả điểm cắt dứt khoát (hard cut) lẫn điểm chuyển cảnh hòa tan (dissolve).

### 2.2. SigLIP2 (Mô hình Nền tảng Thị giác - Ngôn ngữ)
* **Khái niệm:** SigLIP2 (Sigmoid Loss for Language-Image Pre-training version 2) do Google phát triển, là thế hệ nâng cấp của kiến trúc CLIP (OpenAI).
* **Nhiệm vụ:** Ánh xạ một bức ảnh (Keyframe) và một câu văn bản (Query) vào cùng một **Không gian Vector Đa phương thức (Shared Multimodal Embedding Space)**.
* **Cách thức hoạt động:**
  * Mô hình gồm 2 nhánh: Nhánh xử lý ảnh (Vision Transformer - ViT) và nhánh xử lý chữ (Text Transformer).
  * Nhánh ảnh cắt bức ảnh 384x384 thành nhiều ô nhỏ (patches), biến ảnh thành một chuỗi token và đưa qua mạng Transformer để xuất ra một vector (ví dụ: 1152 chiều).
  * Nhánh văn bản mã hóa câu truy vấn thành một vector có cùng số chiều.
  * **Học đối sánh (Contrastive Learning) với hàm mất mát Sigmoid:** Khác với CLIP dùng hàm Softmax (đòi hỏi chuẩn hóa toàn bộ batch, tốn VRAM và nhạy cảm với batch size), SigLIP2 dùng hàm mất mát Sigmoid trên từng cặp (ảnh, chữ) độc lập. Nhờ đó, mô hình đạt độ chính xác cao hơn, hiểu sâu về chi tiết ngữ nghĩa và tiết kiệm tài nguyên tính toán hơn CLIP cũ.
* **Cơ chế so khớp:** Nếu bức ảnh và câu mô tả có cùng ý nghĩa, góc giữa hai vector sẽ rất nhỏ (độ tương đồng Cosine tiến gần về 1.0).

### 2.3. faster-whisper và Silero-VAD (Kênh Lời thoại ASR)
* **Whisper (OpenAI):** Kiến trúc Transformer dạng Sequence-to-Sequence (Encoder-Decoder) được huấn luyện trên hàng trăm nghìn giờ âm thanh đa ngôn ngữ để chuyển giọng nói thành văn bản kèm mốc thời gian.
* **faster-whisper:** Là phiên bản viết lại của Whisper bằng thư viện CTranslate2 (C++). Nó áp dụng kỹ thuật lượng hóa số nguyên (int8 quantization), giúp tốc độ nhận dạng nhanh hơn 4 lần so với bản gốc của OpenAI và giảm mức chiếm dụng VRAM từ 4GB xuống còn khoảng 1.5GB.
* **Silero-VAD (Voice Activity Detection):**
  * Mô hình lọc âm thanh cực nhẹ, dùng để phân loại đoạn audio nào có tiếng người nói, đoạn nào chỉ có tiếng gió, tiếng còi xe hoặc im lặng.
  * **Vì sao cần VAD?** Whisper có một nhược điểm cố hữu là hiện tượng "bịa chữ" (hallucination). Khi nạp vào một đoạn audio im lặng hoặc chỉ có tiếng rè rè kéo dài, Whisper thường tự suy diễn và sinh ra các câu lặp vô nghĩa (ví dụ: *"Cảm ơn các bạn đã theo dõi..."*). VAD giúp cắt bỏ các đoạn này trước khi gọi Whisper.

### 2.4. PaddleOCR (Kênh Chữ trên Màn hình)
* **Nhiệm vụ:** Phát hiện và đọc toàn bộ chữ tiếng Việt xuất hiện trong khung hình video (tiêu đề bản tin, biển báo, tên món ăn, bảng điểm).
* **Quy trình 2 bước của PaddleOCR:**
  1. *Text Detection (DBNet):* Quét toàn bộ bức ảnh để tìm các vùng chứa ký tự văn bản và tạo khung bao quanh (Bounding Box).
  2. *Text Recognition (SVTR / CRNN):* Cắt các vùng khung bao vừa tìm được và đưa qua mạng nhận dạng chuỗi ký tự theo thứ tự từ trái sang phải, có từ điển hỗ trợ đầy đủ bộ gõ tiếng Việt.
* **Vì sao chạy trên CPU?** Do mô hình OCR tương đối nhẹ và hỗ trợ xử lý song song đa tiến trình (multiprocessing) tốt trên CPU, việc chạy OCR trên CPU giúp giải phóng 100% tài nguyên card đồ họa GTX 1650 cho SigLIP2 và Whisper.

### 2.5. bge-m3 (Dense Text Embedding)
* **Khái niệm:** BAAI General Embedding Multi-lingual, Multi-functionality, Multi-granularity.
* **Nhiệm vụ:** Biến một đoạn văn bản tiếng Việt thành một vector ngữ nghĩa 1024 chiều.
* **Sự khác biệt với tìm kiếm từ khóa:**
  * Tìm kiếm truyền thống (FTS5 / BM25) chỉ tìm thấy kết quả nếu chữ gõ vào trùng khớp từng ký tự với chữ trong video (ví dụ: "giảm giá" không tìm thấy đoạn có chữ "khuyến mãi").
  * bge-m3 hiểu được ngữ nghĩa ngầm: Vector của từ "ô tô" và "xe hơi", "thịt lợn" và "thịt heo", "hạ giá" và "sale" sẽ nằm rất gần nhau trong không gian vector.

### 2.6. CLAP (Kênh Âm thanh Môi trường Phi ngôn ngữ)
* **Khái niệm:** Contrastive Language-Audio Pretraining.
* **Cách thức hoạt động:**
  * Giống như SigLIP2 kết nối Ảnh với Chữ, CLAP kết nối **Âm thanh tổng quát** với Chữ.
  * Sóng âm thanh (waveform) được biến đổi thành phổ âm (Spectrogram), sau đó đưa qua mạng Audio Transformer để trích xuất vector.
  * Mô hình cho phép tìm kiếm các âm thanh mà Whisper hoàn toàn "mù" như: tiếng nổ, tiếng mưa rơi rào rào, tiếng còi xe cứu thương, tiếng vỗ tay, tiếng đàn piano.

---

## 3. Các Khái niệm Truy xuất Thông tin và Tìm kiếm (Information Retrieval Concepts)

### 3.1. Vector Embedding (Vector Đặc trưng)
* **Khái niệm:** Là một mảng số thực một chiều (ví dụ: một dãy 768 hoặc 1152 con số) đại diện cho nội dung trừu tượng của một hình ảnh, đoạn âm thanh hoặc đoạn văn bản.
* **Nguyên lý không gian:** Trong không gian nhiều chiều, những đối tượng có nội dung hoặc ngữ cảnh tương tự nhau sẽ được mô hình gom lại gần nhau.

### 3.2. L2 Normalization (Chuẩn hóa L2)
* **Khái niệm:** Phép toán chia mỗi phần tử trong vector cho độ dài hình học (Euclidean norm) của chính nó, đưa độ dài của vector về đúng bằng 1.0.
* **Ý nghĩa:** Khi hai vector đã được chuẩn hóa L2, tích vô hướng (Inner Product) giữa chúng chính là độ tương đồng Cosine. Phép tính này cho phép các thư viện như FAISS tìm kiếm hàng triệu vector trong vài mili-giây.

### 3.3. FAISS (Facebook AI Similarity Search)
* **Khái niệm:** Thư viện mã nguồn mở chuyên dụng do Meta AI phát triển để tìm kiếm các vector tương đồng gần nhất (k-Nearest Neighbors - kNN) với tốc độ cực đại.
* **`IndexFlatIP`:** Cấu hình lập chỉ mục chuẩn xác 100% bằng cách tính tích vô hướng (Inner Product) mà không nén mất mát dữ liệu, cực kỳ phù hợp với quy mô từ 50.000 đến 200.000 keyframes của đồ án.

### 3.4. Lexical Search vs Dense Search
* **Lexical Search (Tìm kiếm từ vựng - BM25 / SQLite FTS5):** So khớp chính xác sự xuất hiện của từ khóa, tính điểm dựa trên tần suất xuất hiện của từ (TF) và mức độ hiếm của từ đó trong toàn bộ kho dữ liệu (IDF). Rất mạnh khi tìm tên riêng, mã số, địa danh cụ thể.
* **Dense Search (Tìm kiếm ngữ nghĩa - bge-m3 / FAISS):** So khớp dựa trên khoảng cách ngữ nghĩa giữa các vector. Rất mạnh khi người dùng diễn đạt câu hỏi theo nhiều cách đồng nghĩa khác nhau.
* **Hybrid Search (Tìm kiếm kết hợp):** Hệ thống kết hợp cả 2 phương thức trên để tận dụng ưu điểm của cả hai bên.

### 3.5. RRF - Reciprocal Rank Fusion (Hợp nhất theo Thứ hạng Nghịch đảo)
* **Vấn đề cần giải quyết:** Điểm Cosine của SigLIP2 nằm trong khoảng [0, 0.4], trong khi điểm BM25 của Whisper lại nằm trong khoảng [0, 30]. Nếu chỉ cộng điểm thông thường, kênh BM25 sẽ áp đảo hoàn toàn kênh hình ảnh.
* **Cách giải quyết của RRF:** Thay vì dùng điểm thô, RRF chỉ quan tâm đến **Thứ hạng (Rank)** của kết quả trong từng kênh:
  * Kết quả đứng thứ 1 trong kênh nào cũng đều có giá trị lớn.
  * Công thức tính điểm: `Điểm = Trọng số kênh / (60 + Thứ hạng)`.
  * Hạng 1 nhận điểm cao nhất, các hạng sau giảm dần. Sau đó cộng dồn điểm của các kênh lại.

### 3.6. Temporal Sliding Window (Cửa sổ Trượt Thời gian)
* **Vấn đề xẻ đôi sự kiện (Boundary Cut):** Nếu chia cứng video thành các đoạn 5 giây rời rạc: `[0-5s]`, `[5-10s]`. Một hành động diễn ra từ giây thứ 4 đến giây thứ 7 sẽ bị cắt làm đôi, mỗi nửa nhận điểm thấp và bị loại khỏi kết quả.
* **Giải pháp Cửa sổ trượt:** Tạo các cửa sổ có kích thước 5 giây nhưng dịch chuyển từng bước 2.5 giây (chồng lấn nhau 50%):
  * Cửa sổ 1: `[0.0 - 5.0s]`
  * Cửa sổ 2: `[2.5 - 7.5s]` (bao trọn vẹn hành động từ giây thứ 4 đến thứ 7)
  * Cửa sổ 3: `[5.0 - 10.0s]`
* Mọi kênh đóng góp điểm vào các cửa sổ trượt này. Đoạn nào được nhiều kênh cùng chỉ vào sẽ đạt điểm tích lũy cao nhất.

### 3.7. Temporal NMS (Non-Maximum Suppression theo Thời gian)
* **Khái niệm:** Sau khi tính điểm cửa sổ trượt, ta sẽ có rất nhiều ô thời gian liền kề nhau cùng có điểm cao (ví dụ: ô 2.5-7.5s, ô 5.0-10.0s, ô 7.5-12.5s).
* **Mục tiêu:** Thuật toán NMS sẽ gom cụm các ô liền kề này thành một khoảng thời gian duy nhất mạch lạc (ví dụ: `2.5s - 12.5s`) và chỉ giữ lại đỉnh điểm cao nhất, tránh trả về cho người dùng 5 kết quả trùng lặp trong cùng một cảnh.

### 3.8. Relevance Feedback (Phản hồi Tương tác - Thuật toán Rocchio)
* **Khái niệm:** Cho phép người dùng trực tiếp cải thiện kết quả tìm kiếm chỉ bằng một cú nhấp chuột.
* **Cách thức:**
  * Khi người dùng bấm nút *"Đúng cảnh này / Tìm cảnh tương tự"*, hệ thống lấy vector của frame đó (positive vector) cộng dồn vào vector câu hỏi ban đầu.
  * Khi người dùng bấm *"Sai cảnh này"*, hệ thống trừ bớt thành phần vector của frame sai (negative vector).
  * Vector câu hỏi mới được cập nhật ngay lập tức và tra cứu lại trong FAISS mà không cần người dùng phải gõ lại câu hỏi.

---

## 4. Các Chỉ số Đánh giá Đo lường (Evaluation Metrics)

### 4.1. Recall@K (Recall tại Top K)
* **Định nghĩa:** Tỷ lệ phần trăm các câu hỏi mà đáp án đúng (Ground Truth) xuất hiện trong số K kết quả đầu tiên trả về.
* **Ví dụ:** Thử nghiệm 40 câu hỏi, với `K = 10`:
  * Có 32 câu hỏi mà mốc thời gian đúng nằm trong Top 10 kết quả.
  * `Recall@10 = 32 / 40 = 80%`.
* Trong đồ án này ta đo đạc: `Recall@1`, `Recall@5` và `Recall@10`.

### 4.2. MRR (Mean Reciprocal Rank)
* **Định nghĩa:** Điểm trung bình của nghịch đảo vị trí xuất hiện đầu tiên của đáp án đúng.
* **Ví dụ:**
  * Câu 1: Đáp án đúng nằm ở vị trí số 1 -> Điểm = 1 / 1 = 1.0.
  * Câu 2: Đáp án đúng nằm ở vị trí số 2 -> Điểm = 1 / 2 = 0.5.
  * Câu 3: Đáp án đúng nằm ở vị trí số 4 -> Điểm = 1 / 4 = 0.25.
  * Câu 4: Không tìm thấy trong top kết quả -> Điểm = 0.
  * Điểm `MRR = (1.0 + 0.5 + 0.25 + 0) / 4 = 0.4375`.
* **Ý nghĩa:** MRR đánh giá hệ thống có đưa được câu trả lời đúng lên các vị trí cao nhất (Top 1, Top 2) hay không.

### 4.3. Dung sai Khớp mốc Thời gian (Hit Condition)
* Một kết quả dự đoán ở giây `T_pred` được tính là "Đoán trúng" (Hit) nếu rơi vào khoảng thời gian chuẩn của nhãn với sai số cho phép:
  `T_pred nằm trong đoạn [T_start - 5 giây, T_end + 5 giây]`.
* Hoặc tính theo chỉ số giao thoa thời gian IoU (Intersection over Union) giữa đoạn dự đoán và đoạn nhãn đạt từ 0.3 trở lên:
  `IoU = Thời lượng trùng nhau / Tổng thời lượng bao phủ cả hai đoạn`.

### 4.4. Ablation Study (Nghiên cứu Thành phần)
* **Khái niệm:** Là phương pháp thực nghiệm khoa học cốt lõi trong các bài báo khoa học và đồ án tốt nghiệp: Lần lượt tháo bỏ hoặc thêm vào từng thành phần của hệ thống để chứng minh thành phần đó thực sự có tác dụng, chứ không phải thêm vào cho có.
* **Bảng so sánh mẫu trong đồ án:**
  * Hệ thống chỉ dùng Visual SigLIP2 (Baseline): Recall@10 đạt 45%.
  * Thêm kênh Lời thoại Whisper (+ ASR): Recall@10 tăng lên 68% (+23%).
  * Thêm kênh Chữ màn hình (+ OCR): Recall@10 tăng lên 82% (+14%).
  * Thêm kênh Âm thanh (+ CLAP): Recall@10 đạt 88% (+6%).
  * Bảng này là bằng chứng thép bảo vệ điểm số của đồ án trước hội đồng phản biện.

---

## 5. Thuật ngữ Phần cứng & Kỹ thuật Hệ thống (Engineering Terms)

* **VRAM (Video RAM):** Bộ nhớ truy cập ngẫu nhiên nằm trên card đồ họa. Card GTX 1650 có 4GB VRAM. Toàn bộ trọng số mô hình khi chạy GPU và ảnh đầu vào đều chiếm dụng bộ nhớ này.
* **OOM (Out Of Memory):** Lỗi xảy ra khi dữ liệu nạp vào GPU vượt quá 4GB VRAM, làm ứng dụng sập ngay lập tức (`CUDA out of memory`).
* **FP16 / INT8 / FP32 (Định dạng Dữ liệu):**
  * `FP32 (Floating Point 32-bit):` Độ chính xác đơn mặc định, 1 số thực tốn 4 bytes.
  * `FP16 (Half Precision 16-bit):` Độ chính xác bán phần, 1 số thực tốn 2 bytes. Giảm 50% dung lượng VRAM so với FP32 mà chất lượng suy luận gần như không đổi.
  * `INT8 (Integer 8-bit):` Lượng hóa thành số nguyên 8-bit, 1 tham số chỉ tốn 1 byte. Giảm 75% bộ nhớ, được áp dụng trong faster-whisper.
* **NVDEC (NVIDIA Video Decoder):** Con chip chuyên dụng tích hợp sẵn trên card NVIDIA làm nhiệm vụ giải mã (decode) các định dạng nén video như H.264/H.265 bằng phần cứng siêu nhanh mà không gây tốn tài nguyên tính toán của nhân CUDA.
* **Checkpoint & Resume (Khả năng Phục hồi):** Cơ chế ghi nhận tiến độ vào cơ sở dữ liệu sau khi xử lý xong từng video. Nếu máy bị mất điện hoặc tắt giữa chừng ở video thứ 45, khi bật lại hệ thống sẽ kiểm tra database và tiếp tục từ video thứ 46, không phải chạy lại từ đầu.
