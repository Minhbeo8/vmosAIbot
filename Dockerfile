# Bước 1: Chọn một "khung sườn" Python nhẹ và ổn định
# Chúng ta dùng phiên bản 3.11-slim để tối ưu kích thước
FROM python:3.11-slim

# Bước 2: Tạo một thư mục làm việc bên trong "chiếc hộp"
# Tất cả các file của bot sẽ nằm trong thư mục /app này
WORKDIR /app

# Bước 3: Sao chép "danh sách nguyên liệu" vào trước
# Đây là một mẹo để tăng tốc độ build trong tương lai
COPY requirements.txt .

# Bước 4: Cài đặt tất cả các "nguyên liệu" từ danh sách
# Lệnh này sẽ chạy "pip install" cho tất cả các thư viện
RUN pip install --no-cache-dir -r requirements.txt

# Bước 5: Sao chép toàn bộ "bản thiết kế" (code của bạn) vào hộp
# Dấu chấm đầu tiên đại diện cho tất cả file trong thư mục hiện tại của bạn
# Dấu chấm thứ hai đại diện cho thư mục làm việc /app bên trong hộp
COPY . .

# Bước 6: Đưa ra lệnh khởi động cuối cùng
# Khi WispByte chạy "chiếc hộp" này, nó sẽ thực thi lệnh "python bot.py"
CMD ["python", "bot.py"]
