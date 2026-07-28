# VLC Signage — Phát video tự động, mỗi màn hình 1 nội dung

Bộ công cụ này cài **riêng trên từng máy tính/máy phát** gắn với 1 màn hình. Mỗi máy chạy độc lập, chỉ đọc nội dung từ thư mục media của chính nó (thư mục này bạn có thể đồng bộ từ máy trung tâm qua mạng LAN, USB, hoặc phần mềm đồng bộ file — xem phần "Gợi ý mở rộng" bên dưới).

## 1. Cài đặt yêu cầu

1. Cài **VLC Media Player** bản 64-bit: https://www.videolan.org/
2. Cài **Python 3.10+** cho Windows: https://www.python.org/ (khi cài, tích chọn "Add Python to PATH")
3. Mở Command Prompt tại thư mục chứa bộ file này, chạy:
   ```
   pip install watchdog requests
   ```

## 2. Cấu trúc file

```
vlc_signage/
├── common.py       # Hàm dùng chung, KHÔNG chỉnh sửa
├── launcher.pyw     # Chương trình chạy nền, tự khởi động VLC
├── settings.pyw     # Giao diện cấu hình — MỞ FILE NÀY ĐẦU TIÊN
├── config.atg       # File cấu hình AES-GCM, chỉ đọc được trên đúng máy
└── log.txt          # Log hoạt động (tự tạo khi chạy)
```

## 3. Cách dùng

1. Chạy `settings.pyw` (double-click hoặc chuột phải > Open with > Python).
2. Trong giao diện:
   - Chọn đường dẫn `vlc.exe` (thường là `C:\Program Files\VideoLAN\VLC\vlc.exe`)
   - Chọn thư mục chứa video/ảnh sẽ phát
   - Đặt thời gian hiển thị mỗi ảnh (giây)
   - Tick "Lặp lại toàn bộ playlist" nếu muốn phát vòng lặp liên tục
   - Tick "Khởi động cùng Windows" nếu muốn máy tự chạy phần mềm khi bật máy
   - Tick lịch tắt máy / khởi động lại nếu cần (VD: tắt 22:00, mở lại 06:00)
3. Nhấn **"Lưu & Áp dụng"**.
4. Nhấn **"Chạy thử VLC ngay"** để kiểm tra ngay không cần khởi động lại máy.

> ⚠️ Chức năng đặt lịch tắt/khởi động lại máy cần chạy `settings.pyw` với quyền **Administrator** (chuột phải > "Run as administrator") vì nó tạo Scheduled Task hệ thống.

## 4. Tự động làm mới playlist

Khi chương trình đang chạy (`launcher.pyw`), nếu bạn thêm/xoá/đổi tên file trong thư mục media, chương trình sẽ tự phát hiện (qua `watchdog`) và làm mới lại playlist trong VLC **mà không cần khởi động lại VLC** — thông qua VLC HTTP Interface (cổng mặc định `8080`).

## 5. Đồng bộ nội dung mỗi màn hình 1 nội dung khác nhau

Vì đây là bài toán nhiều máy phát độc lập:
- Mỗi máy set thư mục media riêng trong `settings.pyw`.
- Máy trung tâm (server) có thể đẩy nội dung xuống từng máy qua:
  - **Mạng LAN chia sẻ thư mục (SMB)**: máy trung tâm để nội dung trong `\\server\mancontent1`, `\\server\mancontent2`... mỗi máy phát trỏ thư mục media của mình về đúng share tương ứng.
  - Hoặc dùng công cụ đồng bộ như **rsync/robocopy** chạy theo lịch (Task Scheduler) để copy nội dung mới nhất từ server xuống ổ đĩa local từng máy — cách này ổn định hơn khi khoảng cách 300–500m vì không phụ thuộc kết nối SMB liên tục.

## 6. Khoảng cách 100–500m

Vì giải pháp này không truyền hình ảnh trực tiếp (không phải kéo dài cáp HDMI), khoảng cách giữa máy trung tâm và máy phát tại từng màn hình chỉ phụ thuộc vào **hạ tầng mạng** (Cat6 nối switch, hoặc cáp quang cho đoạn xa), không giới hạn bởi khoảng cách tín hiệu video như HDMI/DP thông thường.

## 7. Debug bằng VSCode (chi tiết, dùng Terminal)

Bộ file đã có sẵn `.vscode/launch.json` và `.vscode/settings.json`, không cần tự cấu hình lại.

### 7.1. Chuẩn bị môi trường (làm 1 lần)

1. Mở VSCode → **File > Open Folder...** → chọn đúng thư mục `vlc_signage` (không mở nhầm thư mục cha).
2. Cài extension **Python** (Microsoft) và **Pylance** nếu chưa có — vào tab Extensions (`Ctrl+Shift+X`), gõ "Python", cài bản của Microsoft.
3. Mở Terminal tích hợp: menu **Terminal > New Terminal**, hoặc phím tắt `` Ctrl+` `` (dấu backtick, nằm dưới phím Esc).
4. (Khuyến nghị) Tạo virtual environment riêng cho project để không lẫn với Python hệ thống:
   ```
   python -m venv .venv
   ```
   Sau khi tạo xong, VSCode thường tự hỏi *"Select Environment for this workspace?"* → chọn **Yes**, hoặc làm thủ công ở bước 5.
5. Chọn đúng interpreter: `Ctrl+Shift+P` → gõ **"Python: Select Interpreter"** → chọn interpreter có đường dẫn `.venv\Scripts\python.exe` (nếu vừa tạo venv) hoặc bản Python hệ thống bạn đã cài.
6. Terminal sẽ tự kích hoạt venv (thấy chữ `(.venv)` ở đầu dòng lệnh). Nếu chưa tự kích hoạt, chạy tay:
   ```
   .venv\Scripts\activate
   ```
7. Cài thư viện cần thiết ngay trong Terminal:
   ```
   pip install -r requirements.txt
   ```

### 7.2. Chạy trực tiếp bằng Terminal (không debug, chỉ để xem output nhanh)

Đây là cách nhanh nhất để kiểm tra lỗi cú pháp/logic mà không cần đặt breakpoint. Vì `.pyw` khi chạy qua lệnh `python` (thay vì double-click) vẫn hiện đầy đủ log/lỗi ngay trong Terminal:

```
python settings.pyw
```
hoặc
```
python launcher.pyw
```

- Mọi `print()`, exception (traceback), và lỗi cú pháp sẽ hiện trực tiếp trong Terminal.
- Nhấn `Ctrl+C` trong Terminal để dừng chương trình đang chạy.
- Đây là cách khác với chạy thật (double-click `.pyw` hoặc `.exe`) — khi đó KHÔNG có console nên lỗi chỉ nằm trong `log.txt`.

### 7.3. Debug có breakpoint (khuyên dùng khi cần dò lỗi kỹ)

1. Mở file `launcher.pyw` hoặc `settings.pyw` trong VSCode.
2. Click vào lề trái, ngay bên trái số dòng, tại dòng code muốn dừng lại kiểm tra — sẽ hiện 1 chấm đỏ (breakpoint).
   - Ví dụ hữu ích: đặt breakpoint tại dòng `args = build_vlc_args()` trong `launcher.pyw` để xem chính xác lệnh VLC sắp chạy là gì.
3. Vào tab **Run and Debug** ở thanh bên trái (icon hình tam giác có con bọ), hoặc `Ctrl+Shift+D`.
4. Ở dropdown trên cùng, chọn đúng cấu hình:
   - **"Debug: launcher.pyw (chạy VLC nền)"**
   - **"Debug: settings.pyw (giao diện cấu hình)"**
5. Nhấn `F5` (hoặc nút tam giác xanh) để bắt đầu debug.
6. Chương trình sẽ chạy và **tự dừng lại đúng dòng breakpoint**. Lúc này:
   - Vùng **VARIABLES** (thanh bên trái) hiện toàn bộ biến hiện tại và giá trị của chúng (vd xem `cfg` chứa gì, `args` là list gì).
   - Vùng **DEBUG CONSOLE** (tab dưới cùng, cạnh Terminal) cho phép gõ lệnh Python trực tiếp để kiểm tra ngay tại điểm dừng, ví dụ gõ `cfg["vlc_path"]` rồi Enter để xem giá trị.
   - Thanh công cụ debug nổi phía trên có các nút:
     - ▷ **Continue** (`F5`) — chạy tiếp tới breakpoint kế tiếp.
     - ↷ **Step Over** (`F10`) — chạy qua dòng hiện tại, không đi vào hàm được gọi.
     - ↓ **Step Into** (`F11`) — đi vào bên trong hàm đang gọi ở dòng hiện tại.
     - ↑ **Step Out** (`Shift+F11`) — thoát ra khỏi hàm hiện tại, về nơi gọi nó.
     - ⟲ **Restart** (`Ctrl+Shift+F5`) — chạy lại từ đầu.
     - ⬛ **Stop** (`Shift+F5`) — dừng hẳn phiên debug.

> **Vì sao vẫn thấy Terminal khi debug?** File `.vscode/launch.json` đã đặt `"console": "integratedTerminal"`, nghĩa là output của chương trình (kể cả `print`/log) sẽ hiện ngay trong tab **Terminal** như chạy bình thường, thay vì chỉ hiện trong Debug Console — tiện để xem log tuần tự trong lúc debug từng bước.

### 7.4. Kỹ thuật debug nâng cao hữu ích

- **Breakpoint có điều kiện**: chuột phải vào dấu chấm đỏ → **Edit Breakpoint** → nhập điều kiện, ví dụ `cfg["http_port"] == 8080` — chỉ dừng lại khi điều kiện đúng, rất hữu ích khi lỗi chỉ xảy ra ở 1 vòng lặp cụ thể (vd trong `watch_folder_polling()`).
- **Logpoint** (log mà không cần dừng chương trình): chuột phải vào lề trái → **Add Logpoint** → nhập nội dung muốn in ra, ví dụ `Da quet duoc {len(files)} file` — sẽ tự in ra Debug Console mỗi lần chạy qua dòng đó mà không làm dừng chương trình.
- **Xem log.txt song song lúc debug**: mở thêm 1 Terminal (`Ctrl+Shift+5` để tách đôi, hoặc nút "+" ở góc Terminal), chạy lệnh sau để tự cập nhật log liên tục giống `tail -f` trên Windows PowerShell:
  ```
  Get-Content .\log.txt -Wait -Tail 20
  ```
  (nếu Terminal của bạn là Command Prompt thay vì PowerShell, đổi Terminal profile: `Ctrl+Shift+P` → "Terminal: Select Default Profile" → chọn PowerShell)

### 7.5. Lỗi thường gặp khi debug trong VSCode

| Lỗi | Nguyên nhân | Cách sửa |
|---|---|---|
| `ModuleNotFoundError: No module named 'watchdog'` | Chưa cài thư viện, hoặc VSCode đang dùng sai interpreter | Chạy `pip install -r requirements.txt` trong đúng Terminal đang active venv; kiểm tra lại `Ctrl+Shift+P > Python: Select Interpreter` |
| Debug chạy nhưng không dừng ở breakpoint | Đang debug nhầm file (F5 chạy theo file đang mở, không phải file có breakpoint) | Đảm bảo đã chọn đúng cấu hình debug tương ứng ở dropdown trong tab Run and Debug |
| Terminal báo `python : The term 'python' is not recognized` | Python chưa được thêm vào PATH khi cài đặt | Cài lại Python, tích chọn **"Add Python to PATH"**, hoặc dùng `py` thay cho `python` trong Terminal |
| `settings.pyw` mở lên nhưng icon/banner không hiện | Đường dẫn tương đối bị lệch do chạy từ sai thư mục làm việc (cwd) | Đảm bảo mở đúng Folder gốc `vlc_signage` trong VSCode — `launch.json` đã set sẵn `"cwd": "${workspaceFolder}"` nên bình thường không gặp lỗi này nếu mở đúng folder |

**Xem log chi tiết:** dù chạy debug hay chạy thường, chương trình luôn ghi log vào file `log.txt` cùng thư mục — mở file này để xem chính xác lệnh VLC nào đã chạy và lỗi gì đã xảy ra.

## 8. Lỗi "VLC media player could not start / invalid command line options"

Lỗi này gần như luôn do 1 trong các nguyên nhân sau, đã được `launcher.pyw` bản mới tự kiểm tra và ghi log rõ nguyên nhân vào `log.txt`:

| Nguyên nhân | Cách kiểm tra |
|---|---|
| Sai đường dẫn `vlc.exe` trong cấu hình | Mở `settings.pyw`, bấm "Chọn..." lại đường dẫn vlc.exe cho đúng |
| Thư mục media rỗng hoặc không tồn tại | Kiểm tra đã có ít nhất 1 file ảnh/video hợp lệ trong thư mục đã chọn |
| Dùng option boolean sai cú pháp kiểu `--option=value` | Đã sửa trong bản code mới (bỏ `--play-and-exit=no`, `--no-qt-privacy-ask`) |
| Cổng HTTP interface (mặc định 8080) đang bị chương trình khác chiếm | Cần đổi cấu hình cổng trong mã nguồn/Settings rồi lưu lại; không chỉnh trực tiếp `config.atg` |

Sau khi sửa, chạy lại bằng **"Chạy thử VLC ngay"** trong `settings.pyw`, hoặc F5 debug `launcher.pyw` trong VSCode để xem log trực tiếp.

## 9. License & Chế độ dùng thử (Trial)

Chương trình kiểm tra License Key mỗi lần khởi động bằng cách đọc dữ liệu từ Google Sheet quản lý license.
Khi đang chạy, chương trình kiểm tra lại Google Sheet mỗi 60 giây. Thay đổi ngày hết hạn,
trạng thái khóa hoặc mã máy sẽ có hiệu lực mà không cần khởi động lại ứng dụng.

### 11.1. Thiết lập Google Sheet

Sheet quản lý: `ATG Play multi mornitor - License`
(https://docs.google.com/spreadsheets/d/1dsoD_Ljon4BNie2T3VCD51Vx2klJMbjqpbNHBRO8hRk/edit)

1. Mở tab đầu tiên (Sheet1), dòng 1 nhập đúng các tiêu đề cột sau:

   | LicenseKey | MaMay | TenKhachHang | TrangThai | NgayHetHan | ThoiGianOffline | GhiChu |
   |---|---|---|---|---|
   | ATG-2026-0001 | Cty ABC - Sảnh chính | Active | 31/12/2026 | Đã thanh toán |
   | ATG-2026-0002 | Cty XYZ | Blocked | | Nợ phí |

   - **LicenseKey**: mã cấp cho từng khách hàng/máy, tự đặt (vd `ATG-2026-0001`).
   - **MaMay**: mã tạo từ CPU ID + MAC + serial mainboard. Bắt buộc phải khớp.
   - **ThoiGianOffline**: số ngày máy được dùng cache khi không gọi được Google Sheet (0–365).
   - **TrangThai**: `Active` = còn dùng được, `Blocked` = khoá ngay lập tức. Để trống = coi như Active.
   - **NgayHetHan**: định dạng `dd/mm/yyyy`. Để trống = không giới hạn ngày hết hạn.
   - **TenKhachHang**, **GhiChu**: chỉ để quản lý nội bộ, không ảnh hưởng logic.

2. Bấm nút **Share** (Chia sẻ) ở góc trên bên phải Sheet → **Change to anyone with the link** → quyền **Viewer**.
   ⚠️ Bắt buộc phải làm bước này — nếu Sheet ở chế độ riêng tư, chương trình sẽ không đọc được dữ liệu và mọi máy sẽ chạy ở **chế độ dùng thử**.

### 11.2. Cấp License cho khách hàng

- Mở Settings, bấm **"Tạo & sao chép"** ở dòng Mã máy rồi dán vào cột `MaMay`.
- Thêm 1 dòng mới trong Sheet với `LicenseKey`, `MaMay` và `ThoiGianOffline`.
- Mở `settings.pyw` khi chạy mã nguồn hoặc `ATG_Signage.exe` ở bản phát hành, dán đúng `LicenseKey` đó vào ô **"License Key"**.
- Bấm **"Kiểm tra License"** để xác nhận ngay trong giao diện (hiện ✅ hợp lệ / ❌ lỗi kèm lý do cụ thể).
- Bấm **"Lưu & Áp dụng"** để lưu License Key vào `config.atg` đã mã hóa.

### 11.3. Chế độ dùng thử (Trial)

Nếu máy chưa được cấp License Key hợp lệ:

- Chương trình vẫn cho phép **chạy thử 2 phút** mỗi lần khởi động `launcher` (để khách hàng xem trước nội dung/chất lượng).
- Sau đúng 2 phút: VLC tự động dừng, hiện hộp thoại:
  > *"Phiên bản dùng thử đã kết thúc. Vui lòng liên hệ quản trị hệ thống để được hỗ trợ nâng cấp License."*

- Sau đó toàn bộ chương trình tự thoát.
- Muốn chạy lại (thêm 2 phút) phải mở `settings.pyw` → **"Chạy thử VLC ngay"**, hoặc khởi động lại `launcher`. Đây chỉ là chế độ xem thử ngắn, **không phù hợp để vận hành lâu dài** — cần License hợp lệ.

License đã hết hạn, bị khóa hoặc sai mã máy sẽ bị từ chối ngay, không được cấp thêm
phiên demo. Popup hiển thị điện thoại, email và website liên hệ quản trị.

### 11.4. Hoạt động khi mất mạng

Nếu máy không gọi được Google Sheet, chương trình dùng kết quả online gần nhất trong
`license_cache.atg`. Thời gian cho phép lấy riêng từ cột `ThoiGianOffline` của license đó.
Cache được mã hóa, buộc vào mã máy và có kiểm tra trường hợp lùi đồng hồ. Hết thời gian
offline, chương trình chuyển về chế độ dùng thử cho đến khi xác minh online thành công.

### 11.5. Đổi sang Sheet License khác

Nếu bạn dùng Google Sheet riêng thay vì sheet mẫu, mở `license_manager.py`, sửa 2 dòng:
```python
SHEET_ID = "..."   # lấy từ URL Sheet, đoạn giữa /d/ và /edit
SHEET_GID = "0"     # gid của tab chứa dữ liệu (xem trên URL khi mở đúng tab, phần #gid=...)
```

## 10. Logo / Icon / Banner (ATG Solution)

Thư mục `assets/` chứa bộ nhận diện cho app:

```
assets/
├── logo.png             # Logo gốc ATG Solution (1024x1024, nền trong suốt)
├── app_icon.ico           # Icon đa kích thước (16→256px) render lại từ logo.png, dùng làm icon cửa sổ app
├── banner.png             # Banner đầy đủ 1400x420 — dùng cho README, trang giới thiệu, splash
└── banner_header.png      # Banner thu nhỏ 680px — hiển thị ngay trong giao diện settings.pyw
```

- `settings.pyw` tự động dùng `app_icon.ico` làm icon cửa sổ (icon ở góc trên bên trái titlebar) và hiển thị `banner_header.png` ở đầu giao diện.
- Nếu bạn thay logo mới, chạy lại script `make_banner.py` để tạo lại banner, sau đó chạy lệnh dưới để tạo lại icon đa kích thước:
  ```
  pip install pillow
  python make_banner.py
  python -c "from PIL import Image; im = Image.open('assets/logo.png'); im.save('assets/app_icon.ico', sizes=[(s,s) for s in [16,24,32,48,64,128,256]])"
  ```

## 11. Build thành file .exe để triển khai (không lộ mã nguồn)

Đã có sẵn script build tự động, không cần tự gõ lệnh PyInstaller thủ công.

**Cách build (thực hiện trên máy Windows có cài Python):**

1. Mở Command Prompt tại thư mục dự án.
2. Cách 1 — chạy 1 lệnh duy nhất:
   ```
   build.bat
   ```
   (double-click file `build.bat` cũng được)
3. Cách 2 — chạy thủ công từng bước:
   ```
   pip install -r requirements.txt
   python build.py
   ```
4. Sau khi build xong, toàn bộ file cần triển khai nằm trong thư mục **`dist_release\`**:
   ```
   dist_release/
   └── ATG_Signage.exe  <- một file duy nhất, đã nhúng Settings, Launcher và assets
   ```
5. **Triển khai:** chỉ cần copy `ATG_Signage.exe` sang máy đích. Máy đích
   **không cần cài Python**. Mở EXE bình thường để cấu hình; phần mềm tự gọi chính
   EXE với tham số `--launcher` khi chạy VLC hoặc khởi động cùng Windows.

   Lần chạy đầu, mỗi máy tự tạo `config.atg` bằng khóa dẫn xuất từ phần cứng của chính máy.
   Không copy `config.atg` hoặc `license_cache.atg` giữa các máy.

### Lưu ý quan trọng về mức độ bảo mật

`--onefile` của PyInstaller đóng gói mã Python đã biên dịch (bytecode) vào trong file `.exe`, nên:
- ✅ Người dùng thông thường mở file sẽ **không thấy được mã nguồn**, không sửa được logic chương trình.
- ⚠️ Đây **không phải mã hoá tuyệt đối** — người có chuyên môn dùng công cụ như `pyinstxtractor` + `decompyle3` vẫn có thể trích xuất lại bytecode/mã gần giống bản gốc. PyInstaller giúp *che* mã nguồn khỏi người dùng phổ thông, không chống được kỹ sư ngược chuyên nghiệp.
- Nếu cần bảo vệ chặt hơn (mã nguồn có giá trị thương mại cao), có thể kết hợp thêm **PyArmor** (`pip install pyarmor`) để mã hoá bytecode trước khi build bằng PyInstaller — cho mức bảo vệ cao hơn đáng kể, đánh đổi bằng việc build phức tạp hơn. Nếu bạn cần, tôi có thể viết thêm bước này.
