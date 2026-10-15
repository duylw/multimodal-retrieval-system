# Bản chốt: hệ thống tìm cảnh trong video bằng ngôn ngữ tự nhiên
thật.

## 1. Bài toán

Bạn có khoảng 100GB video (tầm 40–50 giờ). Bạn gõ một câu tiếng Việt như "người đàn ông áo đỏ đi xe máy dưới mưa" hoặc "đoạn MC nói về khuyến mãi cuối tuần", và hệ thống trả về **video + giây thứ mấy**.

Có hai việc khác nhau:
1. **Offline**: chạy một lần qua đêm để "đọc hiểu" toàn bộ video và lập mục lục.
2. **Online**: mỗi câu hỏi tra mục lục trong dưới 5 giây.

Cách hình dung dễ nhất là coi mỗi video như một cuốn sách và lập **bốn mục lục khác nhau**: mục lục theo hình ảnh, theo lời thoại, theo chữ trên màn hình, theo âm thanh. Khi bạn hỏi, hệ thống tra cả bốn mục lục rồi xem chỗ nào được nhiều mục lục "đồng ý" nhất.

## 2. Kiến trúc chốt

```
VIDEO ─► Decode 1 lần ─► TransNetV2 (tách shot) ─► chọn keyframe
                                │
        ┌───────────────────────┼─────────────────────────┬──────────────────┐
        ▼                       ▼                         ▼                  ▼
 [HÌNH] SigLIP2          [LỜI] faster-whisper       [CHỮ] OCR          [ÂM THANH] CLAP
  → FAISS                 + VAD → BM25 + bge-m3     → SQLite FTS5      → FAISS (phase 2)
        └───────────────────────┴────────────┬────────────┴──────────────────┘
                                             ▼
                        SQLite: metadata (tên file, ngày quay, thư mục...)

QUERY ─► Viết lại query (LLM nhỏ, CPU) ─► Tra 4 kênh ─► Gộp điểm trên trục thời gian
      ─► Gom nhóm ─► UI (click phát đúng giây) ─► Feedback "đúng/sai" → tìm lại
```

## 3. Từng khối làm gì và vì sao chọn

| Khối | Làm gì | Vì sao |
|---|---|---|
| **TransNetV2** | Tìm điểm cắt cảnh, kể cả dissolve | Rất nhẹ, chính xác hơn so sánh histogram. Lấy frame ở giữa shot để tránh frame bị trộn hai cảnh. |
| **Chọn keyframe** | Shot tĩnh lấy 1 frame, shot nhiều biến động lấy tối đa 6. Bỏ frame đen, mờ, trùng. | Không dùng "1 frame mỗi N giây" vì sẽ lãng phí ở cảnh tĩnh và bỏ sót ở cảnh động. |
| **SigLIP2 so400m/384** | Biến mỗi keyframe thành một vector. Câu hỏi cũng thành vector và so khớp. | Đây là kênh duy nhất hiểu "nội dung hình ảnh" mà không cần ai nói hay viết gì. SigLIP2 mạnh hơn CLIP cũ. |
| **Vector trung bình theo shot** | Lưu thêm một vector đại diện cho cả shot | Gần như miễn phí, giúp câu hỏi mô tả cả cảnh chứ không chỉ một khoảnh khắc. |
| **faster-whisper + VAD** | Chuyển lời nói thành chữ, bỏ đoạn im lặng | VAD giảm lỗi "bịa chữ" lúc im lặng. Kiểm tra video có phụ đề sẵn không, nếu có thì dùng luôn và bỏ qua Whisper. |
| **OCR (detector trước)** | Chỉ đọc chữ ở frame có chữ | Chữ trên màn hình (biển hiệu, tên người, tỉ số, tiêu đề) là thứ embedding xử lý tệ nhất mà OCR xử lý tốt nhất. Chạy trên **CPU song song** với stage GPU nên gần như không tốn thêm thời gian. |
| **bge-m3** | Embedding cho lời thoại và chữ OCR | Hiểu tiếng Việt, nên "khuyến mãi" khớp được với "giảm giá" và "sale". |
| **CLAP (audio event)** | Gán nhãn âm thanh 10 giây một: tiếng nổ, còi xe, vỗ tay, nhạc, mưa | Kênh duy nhất xử lý âm thanh không phải lời nói, mà Whisper hoàn toàn mù. Rất nhẹ. Làm ở phase 2. |
| **Metadata** | Tên file, thư mục, ngày quay, GPS | Chi 
- Reranker văn bản: đây là bước "nếu cần" sau khi đo.

## 4. Phần truy vấn

1. **Viết lại query**: LLM nhỏ (Qwen2.5 1.5B hoặc 3B, q4, chạy CPU, mất khoảng 3–10 giây, có cache) tách câu hỏi thành phần mô tả hình ảnh (dịch sang tiếng Anh cho SigLIP), phần trong ngoặc kép hoặc tên riêng (đưa vào OCR), phần "ai đó nói..." (đưa vào ASR). Nếu muốn nhanh hơn, dùng quy tắc đơn giản thay LLM.
2. **Tra bốn kênh**, mỗi kênh lấy top-200.
3. **Gộp điểm trên trục thời gian**: chia mỗi video thành các ô 5 giây. Mỗi kênh cho điểm vào ô tương ứng (ASR và âm thanh vốn là khoảng thời gian nên rơi vào nhiều ô). Cộng điểm có trọng số, **ô nào nhiều kênh cùng chỉ vào thì lên đầu**. Tôi chọn cách này thay vì lan điểm sang keyframe vì cả bốn kênh đều "nói chuyện" bằng thời gian, nên công thức đơn giản và dễ debug.
4. **Gom nhóm**: các ô liền kề trong cùng video gộp thành một kết quả, tránh trả về 10 cảnh giống nhau.
5. **Câu hỏi nhiều bước** ("mở cửa rồi bước ra đường"): tìm riêng từng sự kiện rồi ghép cặp trong cùng video theo thứ tự thời gian, cách nhau dưới 60 giây.
6. **Feedback**: bạn đánh dấu vài frame đúng/sai thì hệ thống điều chỉnh vector truy vấn và tìm lại. Có thêm nút "tìm cảnh tương tự" và tìm bằng ảnh upload. Đây là phần bù lại việc bỏ VLM rerank: thay vì máy tự đoán, người dùng chỉ hướng bằng một cú click.

Ở thời điểm truy vấn, hầu hết model đủ nhẹ để chạy CPU, nên GPU gần như rảnh và không lo hết VRAM.

## 5. Ước tính chi phí

Giả sử khoảng 45 giờ video và khoảng 80k keyframe.

| Giai đoạn | Chạy trên | Thời gian ước tính |
|---|---|---|
| Decode + tách shot + chọn keyframe | NVDEC/CPU | 2–5h |
| SigLIP2 so400m/384 | GPU | 4–6h |
| Whisper large-v3-turbo (int8) | GPU | 4–9h |
| OCR | CPU, chạy song song | 2–4h |
| CLAP + bge-m3 + dựng index | GPU/CPU | ~1h |
| **Tổng thời gian thực** | | **~12–20h, tức 1–2 đêm** |

- **Ổ đĩa**: khoảng 2–5GB cho keyframe, vector và database. Thư mục tạm tối đa vài GB mỗi video, xoá sau khi xử lý xong.
- **RAM**: đỉnh khoảng 6–8GB. Bạn cho tôi biết máy có 16GB không nhé.
- **Tiền**: 0 đồng, điện khoảng 1,5–2,5 kWh (dưới 10 nghìn đồng).
- **Mỗi truy vấn**: tra cứu dưới 0,1 giây. Bước viết lại query là phần chậm nhất, tổng khoảng 3–10 giây.

Nếu SigLIP so400m/384 benchmark ra chậm hơn 6 ảnh/giây rõ rệt, hạ xuống SigLIP2 large-patch16-256 (nhanh hơn khoảng 3 lần, giảm chất lượng ít). Nếu Whisper turbo nhận dạng tiếng Việt chưa ổn, thử PhoWhisper trên mẫu 10 phút trước khi quyết định.

## 6. Điểm yếu còn lại sau khi bỏ caption và VLM

Tôi nói thẳng để bạn biết hệ thống sẽ làm kém ở đâu:
- **Đếm, phủ định, quan hệ không gian** ("hai người", "không có xe", "con mèo trên bàn"): SigLIP yếu ở những thứ này. Cách giảm: feedback ở bước 6 và chia nhỏ câu hỏi thành các sự kiện.
- **Hành động** ("đang nhảy" so với "đang đứng"): ảnh tĩnh thiếu thông tin chuyển động. Cách giảm: vector trung bình theo shot, và âm thanh phụ trợ. Nếu vẫn yếu, thử thêm video-text model (ViCLIP) sau này.
- **Vật rất nhỏ trong khung hình**: ảnh bị thu về 384px nên chi tiết nhỏ mất. Cách giảm: nếu eval cho thấy vấn đề này nặng thì mới cắt ô (tile) cho các shot liên quan.

Quyết định thêm gì tiếp theo nên dựa vào bộ eval chứ không dựa vào cảm giác.

## 7. Thứ tự build

1. **Viết bộ eval trước**: 30–50 câu hỏi thật kèm đáp án (video và thời điểm ±2 giây). Đo Recall@10 và MRR.
2. **Lõi**: tách shot, keyframe, SigLIP2, FAISS, UI. Ra baseline.
3. **Thêm lần lượt ASR, rồi OCR, rồi CLAP**, chạy lại eval sau mỗi kênh. Kênh nào không tăng Recall thì bỏ.
4. **Viết lại query, gộp điểm theo thời gian, câu hỏi nhiều bước, feedback.**
5. Chỉ khi eval chỉ ra điểm yếu cụ thể mới thêm face, detection hay tile.

Cho tôi biết **video của bạn thuộc loại nào** (tin tức, phim, vlog, thể thao, giám sát...), **RAM** và **dung lượng ổ trống**. Tôi sẽ chốt tham số cụ thể, bỏ kênh nào không cần, rồi viết code bắt đầu từ `run_pipeline.py` (có resume), `shots.py`, `keyframes.py`, `embed.py` và khung eval.