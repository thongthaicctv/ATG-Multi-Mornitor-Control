from PIL import Image, ImageDraw, ImageFont, ImageFilter

LOGO_PATH = "/home/claude/vlc_signage/assets/logo.png"
OUT_PATH = "/home/claude/vlc_signage/assets/banner.png"

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

W, H = 1400, 420

# Nền gradient tối, ánh xanh-đỏ nhẹ đồng bộ với tông logo
bg = Image.new("RGB", (W, H), (14, 16, 22))
draw = ImageDraw.Draw(bg)
for x in range(W):
    t = x / W
    r = int(18 + 40 * (0.5 - abs(0.5 - t)) * 2 * 1.0 + 10)
    g = int(16 + 10 * t)
    b = int(26 + 60 * t)
    draw.line([(x, 0), (x, H)], fill=(r, g, b))

# Thêm chút vệt sáng chéo cho hiệu ứng cao cấp
overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
odraw = ImageDraw.Draw(overlay)
odraw.polygon([(W*0.55, 0), (W*0.75, 0), (W*0.45, H), (W*0.25, H)], fill=(255, 255, 255, 10))
odraw.polygon([(W*0.80, 0), (W*0.90, 0), (W*0.65, H), (W*0.55, H)], fill=(255, 255, 255, 6))
bg = Image.alpha_composite(bg.convert("RGBA"), overlay)

# Logo bên trái
logo = Image.open(LOGO_PATH).convert("RGBA")
logo_h = 300
ratio = logo_h / logo.height
logo = logo.resize((int(logo.width * ratio), logo_h), Image.LANCZOS)
logo_x, logo_y = 60, (H - logo_h) // 2
bg.paste(logo, (logo_x, logo_y), logo)

# Vùng chữ bên phải
text_x = logo_x + logo.width + 50

title_font = ImageFont.truetype(FONT_BOLD, 64)
subtitle_font = ImageFont.truetype(FONT_BOLD, 30)
tagline_font = ImageFont.truetype(FONT_REG, 24)

draw2 = ImageDraw.Draw(bg)

title = "ATG Multi Mornitor Control"
draw2.text((text_x, 110), title, font=title_font, fill=(255, 255, 255, 255))

subtitle = "Giải pháp phát nội dung đa màn hình"
draw2.text((text_x, 190), subtitle, font=subtitle_font, fill=(120, 190, 255, 255))

tagline = "Tự động hoá phát video/ảnh • Đồng bộ nhiều màn hình • by ATG Solution"
draw2.text((text_x, 240), tagline, font=tagline_font, fill=(200, 205, 215, 255))

# Đường kẻ nhấn dưới tiêu đề
draw2.rectangle([text_x, 285, text_x + 520, 289], fill=(220, 60, 50, 255))

bg.convert("RGB").save(OUT_PATH, quality=95)
print("Da tao banner:", OUT_PATH, bg.size)
