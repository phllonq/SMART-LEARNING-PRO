# PRODUCT SPECIFICATION — SMART LEARNING PRO
## Nền Tảng Học Tập Thông Minh Cho Học Sinh THCS & THPT Việt Nam

---

## 1. TỔNG QUAN SẢN PHẨM (PRODUCT OVERVIEW)

- **Tên sản phẩm**: SMART LEARNING PRO
- **Sứ mệnh**: Không chỉ cho học sinh biết mình làm sai ở đâu, mà phải giúp học sinh hiểu sâu **tại sao sai**, **lỗ hổng tư duy nằm ở khái niệm nào**, và **làm thế nào để khắc phục và tiến bộ vượt bậc**.
- **Đối tượng người dùng mục tiêu**:
  1. **Học sinh THCS (Lớp 6 - 9) & THPT (Lớp 10 - 12)**: Cần công cụ học tập có hệ thống, luyện thi định kỳ, giải thích bài chi tiết và gia sư AI đồng hành 24/7.
  2. **Giáo viên bộ môn & Chủ nhiệm**: Cần quản lý lớp học, ngân hàng câu hỏi, tạo bài kiểm tra, chấm tự động và theo dõi độ hổng kiến thức của từng học sinh.
  3. **Quản trị viên nhà trường / Hệ thống (Admin)**: Quản lý người dùng, chương trình môn học, giám sát chi phí AI và hệ thống.

---

## 2. CÁC MÔN HỌC & CHƯƠNG TRÌNH GDPT VIỆT NAM

Hệ thống hỗ trợ cấu trúc phân cấp: **Khối Lớp (Grade) -> Môn Học (Subject) -> Chương (Chapter) -> Chủ Đề (Topic) -> Bài Học (Lesson)**.

Danh mục môn học cốt lõi:
- **Khoa học tự nhiên & Toán**:
  - Toán học (Đại số, Hình học, Giải tích) - Hỗ trợ công thức KaTeX
  - Vật lí (Cơ, Nhiệt, Điện, Quang, Hạt nhân)
  - Hóa học (Hóa vô cơ, Hóa hữu cơ, Phản ứng hóa học)
  - Sinh học (Di truyền, Tiến hóa, Sinh thái học)
- **Khoa học xã hội & Ngôn ngữ**:
  - Tiếng Anh (Ngữ pháp, Từ vựng, Đọc hiểu, Nghe)
  - Ngữ văn (Văn học trung đại, hiện đại, Đọc hiểu, Nghị luận xã hội)
  - Lịch sử & Địa lí (Lịch sử Việt Nam, Thế giới, Địa lí tự nhiên & kinh tế)
- **Công nghệ & Tin học**:
  - Tin học (Lập trình, Thuật toán, Cơ sở dữ liệu)

---

## 3. CHÂN DUNG NGƯỜI DÙNG & HÀNH VI (USER PERSONAS)

### Persona 1: Học sinh (Nguyễn Văn An - Lớp 11 chuyên Toán - Tin)
- **Nỗi đau**: Làm bài tập trắc nghiệm trên mạng chỉ có đáp án A/B/C/D hoặc lời giải sơ sài; khi không hiểu thì không có ai hỏi ngay; hay quên công thức và lặp lại cùng một lỗi sai.
- **Mong muốn**: Được làm bài thi thử có bấm giờ, nộp bài có điểm ngay, câu nào sai được gia sư AI chỉ rõ: "Em đã nhầm công thức giữa đạo hàm hàm hợp và đạo hàm tích", sau đó gợi ý ngay 3 câu tương tự để làm lại.

### Persona 2: Giáo viên (Cô Trần Thị Mai - Giáo viên Vật lí THPT)
- **Nỗi đau**: Mất nhiều thời gian chấm bài trắc nghiệm giấy hoặc nhập điểm thủ công; khó biết được cả lớp đang yếu nhất ở chương nào (ví dụ: Dao động điều hòa hay Sóng ánh sáng).
- **Mong muốn**: Có ngân hàng câu hỏi chuẩn, tạo đề thi trong 5 phút, giao bài tập về nhà theo hạn chót, xem biểu đồ nhiệt (heatmap) độ hổng kiến thức của cả lớp để giảng lại trên lớp.

### Persona 3: Quản trị viên (Admin - Ban Giám hiệu / Quản trị hệ thống)
- **Nỗi đau**: Khó kiểm soát chất lượng nội dung và tài nguyên hệ thống; chi phí API AI có thể tăng vọt nếu không có cơ chế giới hạn và audit.
- **Mong muốn**: Bảng điều khiển giám sát toàn diện người dùng, lượt thi, số token và chi phí Gemini API, nhật ký bảo mật (audit log).

---

## 4. MA TRẬN TÍNH NĂNG CHI TIẾT (FEATURE MATRIX)

### 4.1. Cổng Thông Tin Công Khai (Public Portal)
1. **Landing Page**: Giới thiệu giá trị cốt lõi, minh họa tính năng AI Tutor, phản hồi học sinh, thống kê bài thi.
2. **Khám Phá Môn Học (Subject Catalog)**: Danh sách môn học theo lớp 6 đến 12, đề cương tóm tắt.
3. **Tính Năng (Features)**: Giới thiệu chi tiết giải bài từng bước, phân tích lỗi sai, lộ trình thích ứng.
4. **Hỏi Đáp (FAQ) & Liên Hệ (Contact)**: Hỗ trợ người dùng, chính sách học tập.
5. **Xác Thực (Authentication)**: Đăng ký tài khoản (chọn vai trò Học sinh/Giáo viên), Đăng nhập bảo mật JWT Cookie.

### 4.2. Cổng Học Sinh (Student Portal)
1. **Dashboard Thông Minh**:
   - Điểm trung bình và xu hướng tiến bộ (Recharts).
   - Khóa học đang học dở dang & bài tập sắp đến hạn.
   - Nhiệm vụ học tập hàng ngày (Daily Quests).
   - Chuỗi ngày học tập (Learning Streak) & Điểm kinh nghiệm (XP/Level).
   - Radar đồ thị: Điểm mạnh / điểm yếu theo từng chủ đề.
2. **Học Tập & Bài Giảng (Course & Lesson Viewer)**:
   - Cây mục lục: Khối lớp -> Môn học -> Chương -> Chủ đề -> Bài học.
   - Trình đọc bài giảng phong phú: Nội dung Markdown, công thức KaTeX ($$E=mc^2$$), video bài giảng nhúng, sơ đồ tư duy.
   - Bookmark tài liệu & ghi chú cá nhân.
3. **Không Gian Luyện Tập (Practice Workspace)**:
   - 6 dạng câu hỏi: Trắc nghiệm 1 đáp án, nhiều đáp án, Đúng/Sai, Điền từ ngắn, Câu hỏi số học, Tự luận.
   - Nhận phản hồi tức thì sau khi trả lời từng câu (Instant feedback mode).
4. **Phòng Thi Trực Tuyến (Examination Room)**:
   - Đồng hồ đếm ngược đồng bộ server-client.
   - Bảng điều hướng câu hỏi (Question Palette): Trạng thái Đã trả lời, Chưa trả lời, Đánh dấu xem lại.
   - Tự động lưu đáp án sau mỗi lần chọn (Autosave).
   - Tự động nộp bài khi hết giờ (Auto-submit on timeout).
   - Xác nhận trước khi nộp bài thủ công.
5. **Trung Tâm Phân Tích Lỗi Sai (Wrong Answer Analysis Studio)**:
   - Danh sách các câu làm sai trong bài thi/luyện tập.
   - Thẻ AI Diagnostics: Lỗi thuộc loại gì (Nhầm khái niệm / Tính toán sai / Đọc thiếu dữ kiện).
   - Hướng dẫn tư duy từng bước (Step-by-step reasoning).
   - Nút "Luyện tập câu tương tự" sinh ra bởi AI.
6. **Trợ Lý Gia Sư AI Tutor (Gemini Powered)**:
   - Khung chat đồng hành xuyên suốt quá trình học.
   - Chế độ Socratic: Không cho sẵn đáp án mà đặt câu hỏi gợi mở để học sinh tự tìm ra cách giải.
   - Giải thích công thức và ví dụ tương tự.

### 4.3. Cổng Giáo Viên (Teacher Portal)
1. **Teacher Dashboard**: Tổng quan số lớp, số học sinh, số bài tập đang mở, tỷ lệ nộp bài.
2. **Quản Lý Lớp Học (Classroom Management)**: Tạo lớp, mã mời tham gia (Class code), danh sách thành viên.
3. **Ngân Hàng Câu Hỏi (Question Bank)**:
   - Lọc theo môn, lớp, độ khó (Nhận biết, Thông hiểu, Vận dụng, Vận dụng cao), định dạng câu hỏi.
   - Trình soạn thảo câu hỏi hỗ trợ KaTeX, hình ảnh minh họa, lời giải chi tiết.
4. **Tạo Đề Thi & Giao Bài (Exam Builder & Assignments)**:
   - Tạo đề ngẫu nhiên từ ngân hàng hoặc chọn thủ công từng câu.
   - Cài đặt: Thời gian làm bài, số lần làm tối đa, xáo trộn câu hỏi, xáo trộn đáp án, thời điểm xem lời giải.
   - Giao bài tập cho cả lớp hoặc nhóm học sinh kèm hạn nộp (Deadline).
5. **Sổ Điểm & Báo Cáo Phân Tích (Gradebook & Learning Analytics)**:
   - Thống kê phân phổ điểm (Histogram), điểm trung bình, độ lệch chuẩn.
   - Báo cáo câu hỏi có tỷ lệ sai cao nhất lớp để giáo viên ôn tập lại.

### 4.4. Cổng Quản Trị Hệ Thống (Admin Portal)
1. **Quản Trị Người Dùng & Phân Quyền (RBAC)**:
   - Danh sách người dùng, kích hoạt/vô hiệu hóa tài khoản, gán vai trò: STUDENT, TEACHER, ADMIN.
2. **Quản Trị Danh Mục Chương Trình Học**:
   - Thêm/sửa/xóa Khối lớp, Môn học, Chương, Chủ đề.
3. **Cấu Hình & Giám Sát AI (AI Monitoring)**:
   - Cấu hình model Gemini (`gemini-1.5-flash`, `gemini-1.5-pro`).
   - Theo dõi số lượng request, số token tiêu thụ, ước tính chi phí API theo ngày/tháng.
4. **Nhật Ký Hệ Thống (Audit Logs)**: Ghi nhận mọi thao tác đăng nhập, sửa điểm, cấp quyền.
