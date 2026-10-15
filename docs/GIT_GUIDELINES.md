# Hướng dẫn Quản lý Git và Quy trình Làm việc Nhóm (Git & Collaboration Guidelines)

Tài liệu này quy định chuẩn mực làm việc với Git cho toàn bộ thành viên nhóm thực hiện đồ án tốt nghiệp về **Truy xuất video đa phương thức**.

---

## 1. Nguyên tắc Cốt lõi (Core Principles)

1. **Tuyệt đối không commit dữ liệu nặng vào Git:**
   * Không commit video (`.mp4`, `.mkv`, `.avi`).
   * Không commit ảnh keyframe (`.jpg`, `.png`).
   * Không commit cơ sở dữ liệu (`.db`, `.sqlite`) và chỉ mục (`.index`).
   * Không commit file trọng số mô hình (`.pt`, `.bin`, `.safetensors`, `.onnx`).
   * Tất cả các định dạng trên đã được cấu hình trong [.gitignore](file:///d:/UIT/TX/doan/.gitignore).
2. **Kiểm tra trạng thái trước khi commit:**
   * Luôn gõ lệnh `git status` trước khi thêm file để chắc chắn không vô tình đưa file rác hoặc file dữ liệu vào Git.
3. **Commit nhỏ và có ý nghĩa (Atomic Commits):**
   * Mỗi commit chỉ giải quyết một phần việc cụ thể (ví dụ: xong một hàm lọc ảnh mờ, hoặc xong một model dataclass).
   * Không dồn toàn bộ code của cả tuần vào một commit duy nhất dạng *"update code"* hay *"fix bug"*.
4. **Không dùng biểu tượng cảm xúc (No Emojis / Icons):**
   * Không dùng các ký tự icon trong commit message. Sử dụng chữ thuần túy theo chuẩn Conventional Commits.

---

## 2. Chiến lược Phân nhánh (Branching Strategy)

Sơ đồ phân nhánh khuyến nghị cho nhóm đồ án:

```
main (Nhánh chính thức, code ổn định, đã pass qua bộ eval)
 │
 ├── feat/task-00-eval (Nhánh làm môi trường và bộ benchmark)
 ├── feat/task-01-shots (Nhánh làm tách shot và trích keyframe)
 ├── feat/task-02-visual (Nhánh làm embedding SigLIP2 và FAISS)
 ├── feat/task-03-speech (Nhánh làm ASR Whisper)
 ├── feat/task-04-ocr (Nhánh làm PaddleOCR)
 └── fix/vram-leak-siglip (Nhánh sửa lỗi phát sinh)
```

### Quy tắc đặt tên nhánh:
* Tính năng mới theo task: `feat/task-XX-<ten-ngan-gon>`
  * Ví dụ: `feat/task-01-shots`, `feat/task-03-whisper-asr`
* Sửa lỗi: `fix/<ten-loi>`
  * Ví dụ: `fix/sqlite-lock`, `fix/empty-audio-crash`
* Cập nhật tài liệu: `docs/<noi-dung>`
  * Ví dụ: `docs/project-overview`, `docs/tracking-update`

---

## 3. Quy chuẩn Viết Commit Message (Conventional Commits)

Toàn bộ commit message bắt buộc **viết 100% bằng tiếng Anh**, theo cấu trúc chuẩn:

```
<type>(<scope>): <mô tả ngắn gọn bằng thể mệnh lệnh>

[Tùy chọn: Thân commit giải thích lý do kỹ thuật nếu thay đổi phức tạp]
```

### A. Các Type thông dụng:
* `feat`: Bổ sung tính năng mới hoặc module mới.
* `fix`: Sửa lỗi logic, sửa bug, giải quyết memory leak.
* `refactor`: Tái cấu trúc mã nguồn (sắp xếp lại code mà không thay đổi tính năng).
* `perf`: Cải thiện hiệu năng xử lý (tăng tốc độ FPS, giảm VRAM).
* `test`: Thêm hoặc cập nhật kịch bản kiểm thử, thêm file ground truth.
* `docs`: Cập nhật tài liệu (markdown, hướng dẫn sử dụng).
* `chore`: Cấu hình môi trường, cập nhật `pyproject.toml`, `.gitignore`.

### B. Các Scope phù hợp với dự án:
* `shots`: Module tách cảnh và ranh giới video.
* `keyframes`: Module trích xuất và lọc keyframe thích ứng.
* `visual`: Module SigLIP2 và chỉ mục hình ảnh.
* `speech`: Module Whisper và phiên âm ASR.
* `ocr`: Module đọc chữ PaddleOCR và FTS5.
* `fusion`: Module gộp điểm thời gian và Sliding Window.
* `ui`: Giao diện người dùng web và video streaming.
* `eval`: Bộ benchmark, ground truth, script tính chỉ số.
* `config`: File cấu hình YAML và ConfigManager.

### C. Ví dụ Commit Chuẩn và Không chuẩn:

* **Chuẩn (Good):**
  * `feat(shots): implement adaptive keyframe selection with laplacian variance`
  * `feat(visual): add siglip2 batch extraction with fp16 vram safety`
  * `fix(speech): remove temporary wav files after whisper transcription`
  * `refactor(indexer): standardize base indexer interface for faiss`
  * `perf(ocr): add edge density pre-filter to skip non-text frames`
  * `docs(agents): update hardware constraints and git guidelines`

* **Không chuẩn (Bad - Cần tránh):**
  * `fix bug` *(Quá mơ hồ, không biết sửa bug gì)*
  * `update code hom nay` *(Dùng tiếng Việt, không theo chuẩn type/scope)*
  * `add feature and fixed some files` *(Gom nhiều việc không liên quan vào 1 commit)*
  * `:rocket: deploy app` *(Dùng icon emoji - vi phạm quy định)*

---

## 4. Kịch bản Làm việc Chung Hàng ngày (Step-by-Step Workflow)

### Kịch bản 1: Bắt đầu làm một Task mới
1. Chuyển về nhánh `main` và lấy code mới nhất về:
   ```powershell
   git checkout main
   git pull origin main
   ```
2. Tạo nhánh mới dựa trên mã task:
   ```powershell
   git checkout -b feat/task-01-shots
   ```
3. Tiến hành viết code trong nhánh này.

### Kịch bản 2: Khi hoàn thành một mẩu code hoặc một hàm
1. Kiểm tra trạng thái các file đã thay đổi:
   ```powershell
   git status
   ```
2. Chạy thử nghiệm unit test cục bộ (`python -m src.extractors.shots`) để chắc chắn code chạy không lỗi.
3. Thêm các file thay đổi vào staging:
   ```powershell
   git add src/extractors/shots.py configs/default_config.yaml
   ```
4. Tạo commit theo quy chuẩn:
   ```powershell
   git commit -m "feat(shots): add transnetv2 boundary detection with frame caching"
   ```

### Kịch bản 3: Đẩy nhánh lên Remote và Gộp vào `main`
1. Đẩy nhánh của bạn lên GitHub/GitLab:
   ```powershell
   git push origin feat/task-01-shots
   ```
2. Tạo **Pull Request (PR)** trên giao diện web (GitHub/GitLab) để người còn lại trong nhóm xem lại (Review code):
   * Tên PR: `[Task 01] Implement Shot Detection and Adaptive Keyframes`
   * Mô tả ngắn gọn: Đã test trên video mẫu, tốc độ đạt 80 FPS, VRAM an toàn.
3. Sau khi đồng nghiệp duyệt và xác nhận không có xung đột (conflict), nhấn **Merge** vào `main`.
4. Người ở máy khác chỉ cần `git checkout main` và `git pull origin main` là có đầy đủ code mới nhất.

### Kịch bản 4: Xử lý Xung đột Code (Merge Conflict)
Nếu bạn và bạn cùng nhóm lỡ sửa cùng một dòng trong file:
1. Khi `git merge` hoặc `git pull`, Git sẽ báo dòng bị conflict.
2. Mở file có conflict trong trình soạn thảo, Git sẽ đánh dấu đoạn `<<<<<<< HEAD` và `>>>>>>>`.
3. Bàn bạc với đồng đội để giữ lại đoạn code đúng nhất, xóa các dấu đánh dấu của Git.
4. Lưu file và commit lại:
   ```powershell
   git add <file_da_sua>
   git commit -m "fix(merge): resolve conflict in score_fusion.py"
   ```

---

## 5. Bảng Tra cứu Lệnh Git Thông dụng

| Lệnh | Ý nghĩa |
|---|---|
| `git status` | Xem trạng thái các file đang sửa đổi (luôn dùng trước khi add) |
| `git diff` | Xem chi tiết từng dòng code đã sửa đổi |
| `git branch -a` | Xem danh sách tất cả các nhánh cục bộ và trên remote |
| `git checkout -b <ten_nhanh>` | Tạo nhánh mới và chuyển sang nhánh đó ngay lập tức |
| `git checkout <ten_nhanh>` | Chuyển qua lại giữa các nhánh |
| `git pull origin main` | Kéo code mới nhất từ nhánh main trên server về máy |
| `git push origin <ten_nhanh>` | Đẩy nhánh hiện tại lên server |
| `git log -n 5 --oneline` | Xem lịch sử 5 commit gần nhất ngắn gọn trên 1 dòng |
