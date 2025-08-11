
# VMOS AI Bot

Một bot Discord mạnh mẽ để tạo ảnh AI, sử dụng nhiều tài khoản VMOS để tối ưu hóa việc sử dụng điểm và cung cấp các tùy chọn chuyên nghiệp.

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

### ✨ Tính Năng Nổi Bật

*   **Quản lý nhiều tài khoản:** Tự động chuyển đổi giữa các tài khoản VMOS khi một tài khoản hết điểm.
*   **Hàng đợi thông minh:** Xử lý các yêu cầu tạo ảnh một cách tuần tự, tránh quá tải và xung đột.
*   **Bộ đệm (Cache) thông minh:** Lưu lại kết quả của các prompt đã tạo. Nếu một yêu cầu giống hệt được gửi lại, bot sẽ trả về ảnh từ cache, **giúp tiết kiệm 1000 điểm** cho mỗi lần.
*   **Tùy chọn chuyên nghiệp:** Hỗ trợ đầy đủ các tùy chọn như `prompt`, `negative_prompt`, phong cách (style), tỷ lệ khung hình (aspect ratio), `guidance_scale` và `seed`.
*   **Giao diện Slash Command:** Tích hợp mượt mà với Discord thông qua các lệnh slash hiện đại.
*   **Dễ dàng quản lý:** Các lệnh dành riêng cho chủ bot để thêm, sửa, xóa và kiểm tra điểm của các tài khoản.
*   **Triển khai với Docker:** Đi kèm `Dockerfile` để dễ dàng đóng gói và triển khai.

### ⚙️ Cài Đặt và Cấu Hình

**Yêu cầu:**

*   Python 3.11+
*   Docker (Khuyến khích)

**Các bước cài đặt:**

1.  **Clone repository này:**
    ```bash
    git clone <URL_CỦA_REPO>
    cd vmosAIbot-main
    ```

2.  **Tạo file cấu hình `.env`:**
    Tạo một file có tên `.env` trong thư mục gốc của dự án với nội dung sau:
    ```env
    DISCORD_BOT_TOKEN="YOUR_DISCORD_BOT_TOKEN_HERE"
    OWNER_ID=YOUR_DISCORD_USER_ID_HERE
    ```
    *   `DISCORD_BOT_TOKEN`: Lấy từ [Discord Developer Portal](https://discord.com/developers/applications).
    *   `OWNER_ID`: ID người dùng Discord của bạn (bật chế độ Developer trong Discord, sau đó chuột phải vào tên của bạn và chọn "Copy User ID").

3.  **Cấu hình tài khoản VMOS:**
    Mở file `accounts.json` và chỉnh sửa hoặc thêm các tài khoản VMOS của bạn theo định dạng JSON sau. Bạn có thể thêm bao nhiêu tài khoản tùy ý.
    ```json
    [
      {
        "token": "TOKEN_TÀI_KHOẢN_1",
        "userId": "USER_ID_TÀI_KHOẢN_1",
        "description": "Mô tả cho tài khoản 1 (ví dụ: Tài khoản chính)"
      },
      {
        "token": "TOKEN_TÀI_KHOẢN_2",
        "userId": "USER_ID_TÀI_KHOẢN_2",
        "description": "Mô tả cho tài khoản 2 (ví dụ: Tài khoản phụ)"
      }
    ]
    ```

### 🚀 Khởi Chạy Bot

Có hai cách để chạy bot:

**Cách 1: Sử dụng Docker (Khuyến khích)**

Đây là cách dễ dàng và ổn định nhất để triển khai.

1.  **Build Docker image:**
    ```bash
    docker build -t vmos-ai-bot .
    ```

2.  **Chạy container:**
    ```bash
    docker run -d --restart always --env-file .env --name vmos-bot vmos-ai-bot
    ```

**Cách 2: Chạy trực tiếp với Python**

1.  **Cài đặt các thư viện cần thiết:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Chạy bot:**
    ```bash
    python bot.py
    ```

### 📋 Hướng Dẫn Sử Dụng (Lệnh)

**Lệnh cho người dùng:**

*   `/generate <prompt>`: Lệnh chính để tạo ảnh.
    *   `prompt` (bắt buộc): Mô tả hình ảnh bạn muốn tạo.
    *   `style` (tùy chọn): Chọn một phong cách nghệ thuật (Anime, Realistic, Cyberpunk, v.v.).
    *   `negative_prompt` (tùy chọn): Những thứ bạn không muốn xuất hiện trong ảnh.
    *   `aspect_ratio` (tùy chọn): Tỷ lệ khung hình (Vuông, Dọc, Ngang, ...).
    *   `guidance_scale` (tùy chọn): Mức độ bám sát prompt (thấp = sáng tạo, cao = bám sát). Mặc định là `7.5`.
    *   `seed` (tùy chọn): Dùng để tái tạo lại một ảnh cũ. `-1` là ngẫu nhiên.
*   `/queue`: Xem hàng đợi tạo ảnh hiện tại.
*   `/help`: Hiển thị thông tin trợ giúp về các lệnh.

**Lệnh dành cho chủ bot (Owner Only):**

*   `/points`: Kiểm tra số điểm còn lại của tất cả các tài khoản.
*   `/addaccount`: Thêm một tài khoản VMOS mới thông qua một form pop-up.
*   `/editaccount`: Chỉnh sửa thông tin của một tài khoản đã có.
*   `/removeaccount`: Xóa một tài khoản khỏi danh sách.

### 📜 Giấy Phép

Dự án này được cấp phép theo Giấy phép MIT. Xem file `LICENSE` để biết thêm chi tiết.
