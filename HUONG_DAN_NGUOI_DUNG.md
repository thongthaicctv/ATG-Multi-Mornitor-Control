# ATG Multi Mornitor Control

## Giới thiệu phần mềm

ATG Multi Mornitor Control là phần mềm trình chiếu nội dung quảng cáo và thông tin trên màn hình bằng
VLC Media Player. Phần mềm tự động phát liên tục các video và hình ảnh trong thư mục do
người dùng lựa chọn, phù hợp cho màn hình tại sảnh, cửa hàng, showroom, văn phòng, nhà
máy và các khu vực công cộng.

Mỗi máy tính vận hành độc lập và có thể sử dụng một thư mục nội dung riêng.

## Chức năng chính

- Phát tự động video và hình ảnh trong một thư mục.
- Phát toàn màn hình.
- Lặp lại toàn bộ danh sách nội dung.
- Tự cập nhật danh sách phát khi thêm, xóa hoặc thay đổi file trong thư mục media.
- Cho phép đặt thời gian hiển thị cho mỗi hình ảnh.
- Tự chạy cùng Windows nếu người dùng bật tùy chọn.
- Hỗ trợ đặt lịch tắt máy hoặc khởi động lại máy hằng ngày.
- Kiểm tra license trực tuyến và hỗ trợ hoạt động offline trong thời gian được cấp phép.
- Hiển thị mã máy để gửi cho đơn vị cung cấp khi đăng ký hoặc gia hạn license.

## Yêu cầu sử dụng

- Máy tính chạy Windows.
- Đã cài VLC Media Player.
- Đã cài LibreOffice nếu cần phát Word, Excel hoặc PowerPoint. Không cần cài Microsoft Office hoặc WPS Office.
- Có thư mục chứa video hoặc hình ảnh cần trình chiếu.
- Nên có kết nối Internet khi kích hoạt hoặc kiểm tra license.

Các định dạng phổ biến được hỗ trợ gồm MP4, AVI, MKV, MOV, WMV, JPG, JPEG, PNG,
BMP, GIF và WebP.

## Hướng dẫn sử dụng nhanh

### 1. Mở phần mềm

Chạy file `ATG Multi Mornitor Control V1.2.4.exe`.

Nếu Windows hiển thị cảnh báo bảo mật, chọn **More info** → **Run anyway** khi file
được nhận từ Công ty An Nguyên hoặc đơn vị triển khai được ủy quyền.

### 2. Chọn VLC

Tại dòng **Đường dẫn VLC (vlc.exe)**:

1. Nhấn **Chọn...**.
2. Chọn file `vlc.exe`.

Đường dẫn thường dùng:

```text
C:\Program Files\VideoLAN\VLC\vlc.exe
```

### 3. Chọn nội dung trình chiếu

Tại dòng **Thư mục nguồn**:

1. Nhấn **Chọn...**.
2. Chọn thư mục chứa video, hình ảnh, PDF, Word, Excel hoặc PowerPoint.

Tại dòng **Thư mục PLAY**, chọn một thư mục riêng để phần mềm lưu ảnh/video đã xử lý.
Không chọn PLAY trùng hoặc nằm bên trong thư mục nguồn.

File PDF và Office được tự chuyển từng trang thành PNG trước khi phát. Word, Excel và PowerPoint chỉ
được chuyển đổi bằng LibreOffice.

### Cài đặt và kiểm tra LibreOffice

1. Tải LibreOffice từ trang chính thức `https://www.libreoffice.org/download/download-libreoffice/`.
2. Cài đặt theo lựa chọn mặc định của chương trình cài đặt.
3. Trong ATG Multi Mornitor Control, nhấn **TỰ ĐỘNG TÌM** tại dòng **Đường dẫn LibreOffice**.
4. Nếu không tự tìm thấy, nhấn **CHỌN SOFFICE.EXE** và chọn một trong các đường dẫn thường dùng:

```text
C:\Program Files\LibreOffice\program\soffice.exe
C:\Program Files (x86)\LibreOffice\program\soffice.exe
```

5. Nhấn **KIỂM TRA**. Chỉ tiếp tục khi phần mềm báo **LibreOffice đã sẵn sàng**.

Không chọn `swriter.exe`, `scalc.exe` hoặc `simpress.exe`. Ảnh, video và PDF gốc vẫn đồng bộ được khi
chưa cài LibreOffice; riêng tài liệu Word, Excel và PowerPoint sẽ báo lỗi và giữ nguyên dữ liệu PLAY cũ.

Phần mềm sẽ phát các file hợp lệ trong thư mục theo thứ tự tên file. Có thể thêm số vào
đầu tên file để sắp xếp thứ tự, ví dụ:

```text
01_GioiThieu.mp4
02_SanPham.jpg
03_KhuyenMai.mp4
```

### 4. Chọn chế độ phát

- **Thời gian hiển thị mỗi ảnh:** nhập số giây muốn hiển thị một hình ảnh.
- **Lặp lại toàn bộ playlist:** bật để nội dung tự phát lại sau khi chạy hết.
- **Phát toàn màn hình:** bật để VLC phủ toàn bộ màn hình.
- **Phát nguyên ảnh:** giữ đúng tỷ lệ và toàn bộ nội dung ảnh/trang tài liệu.
- **Full màn hình – giữ đủ nội dung:** thu/phóng ảnh chính theo kiểu contain, không cắt chữ hoặc dữ liệu; phần trống được lấp bằng nền mờ đối với ảnh và nền trắng đối với tài liệu.

### 5. Nhập và kiểm tra license

Nếu đã được cấp License Key:

1. Nhập mã vào ô **License Key**.
2. Nhấn **Kiểm tra License**.
3. Chờ thông báo license hợp lệ.

Nếu chưa có license:

1. Nhấn **Tạo & sao chép** tại dòng Mã máy.
2. Gửi mã máy vừa sao chép cho đơn vị cung cấp phần mềm.
3. Sau khi nhận License Key, nhập mã và kiểm tra lại.

Máy chưa được cấp license có thể chạy thử trong 2 phút. Khi hết thời gian dùng thử,
phần mềm sẽ dừng và hiển thị thông tin liên hệ hỗ trợ.

### 6. Tùy chọn khởi động và lịch máy

- Bật **Khởi động cùng Windows** nếu muốn phần mềm tự phát nội dung sau khi đăng nhập
  Windows.
- Bật **Tự động TẮT máy lúc** và nhập giờ theo định dạng `HH:MM` nếu cần.
- Bật **Tự động KHỞI ĐỘNG LẠI lúc** và nhập giờ theo định dạng `HH:MM` nếu cần.

Ví dụ:

```text
22:00
```

Một số máy có thể yêu cầu mở phần mềm bằng quyền Administrator để lưu lịch tắt hoặc
khởi động lại.

### 7. Lưu và chạy

1. Nhấn **Lưu & Áp dụng** để lưu cấu hình.
2. Nhấn **Chạy thử VLC ngay** để bắt đầu trình chiếu.
3. Kiểm tra hình ảnh, âm thanh, thứ tự nội dung và chế độ toàn màn hình.

## Cập nhật nội dung trình chiếu

Khi phần mềm đang chạy, có thể sao chép thêm file mới hoặc xóa file cũ trong thư mục
media. Phần mềm sẽ tự nhận biết thay đổi và cập nhật danh sách phát.

Để hạn chế lỗi khi đang sao chép video dung lượng lớn:

1. Sao chép file vào một thư mục tạm.
2. Chờ sao chép hoàn tất.
3. Di chuyển file hoàn chỉnh vào thư mục media.

Không nên đổi tên hoặc xóa file đúng lúc VLC đang phát file đó.

## Xử lý nhanh một số lỗi

### Không mở được VLC

- Kiểm tra VLC đã được cài đặt.
- Mở Settings và chọn lại đúng file `vlc.exe`.

### Không có nội dung phát

- Kiểm tra đã chọn đúng thư mục media.
- Kiểm tra thư mục có video hoặc hình ảnh được hỗ trợ.
- Thử mở trực tiếp file bằng VLC để xác nhận file không bị lỗi.

### Nội dung không phát toàn màn hình

- Bật **Phát toàn màn hình**.
- Đóng VLC đang mở rồi nhấn **Chạy thử VLC ngay** lại.

### License không hợp lệ

- Kiểm tra License Key đã nhập đúng.
- Kiểm tra máy có kết nối Internet.
- Không sao chép file cấu hình hoặc license từ máy khác.
- Gửi Mã máy và ảnh thông báo lỗi cho bộ phận hỗ trợ.

## Thông tin hỗ trợ

**CÔNG TY TNHH CÔNG NGHỆ VÀ THƯƠNG MẠI AN NGUYÊN**

- Điện thoại: 0932 333 000
- Email: annguyentechcons@gmail.com
- Website: https://annguyen.pro/
- Camera Thái Nguyên: https://camerathainguyen.com/

**Trụ sở Hà Nội:** Số 66 Ngõ 328 đường Tây Mỗ, P. Tây Mỗ, TP Hà Nội, Việt Nam.

**Chi nhánh Thái Nguyên:** Số 202 đường Thống Nhất, P. Phan Đình Phùng,
T. Thái Nguyên.
