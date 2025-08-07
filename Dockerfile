# Sử dụng một hình ảnh Python chính thức làm nền tảng
FROM python:3.11-slim

# Thiết lập thư mục làm việc ĐÚNG VỚI YÊU CẦU CỦA WISPBYTE/PTERODACTYL
WORKDIR /home/container

# Sao chép file requirements.txt vào trước
COPY requirements.txt .

# Cài đặt tất cả các thư viện cần thiết
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ code còn lại của bot vào
COPY . .

# Lệnh để chạy bot khi container khởi động
CMD ["python", "bot.py"]
