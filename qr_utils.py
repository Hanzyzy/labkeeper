"""LabKeeper — Static QR code generation (print + glue on tools)"""
import os
import qrcode
from PIL import Image, ImageDraw, ImageFont
from datetime_utils import get_config


def generate_qr_for_tool(tool_or_code) -> str:
    """Generate a PNG QR code that links to the public tool page,
    with the tool code clearly printed at the bottom of the image.
    Accepts either a Tool object or a string tool code.
    Returns the absolute path to the saved file.
    """
    if hasattr(tool_or_code, 'code'):
        tool_code = tool_or_code.code
    else:
        tool_code = str(tool_or_code)
    
    cfg = get_config()
    base = cfg.base_url.rstrip("/")
    url = f"{base}/tool/{tool_code}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    base_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    
    # Expand canvas height to render tool_code text at the bottom
    qw, qh = base_img.size
    banner_h = 44
    labeled_img = Image.new("RGB", (qw, qh + banner_h), "white")
    labeled_img.paste(base_img, (0, 0))

    draw = ImageDraw.Draw(labeled_img)
    
    # Load font or fallback
    font = None
    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except Exception:
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 22)
        except Exception:
            font = ImageFont.load_default()

    text = tool_code
    if hasattr(draw, 'textbbox') and font:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
    elif hasattr(draw, 'textsize') and font:
        tw, th = draw.textsize(text, font=font)
    else:
        tw, th = len(text) * 8, 16

    tx = (qw - tw) // 2
    ty = qh + (banner_h - th) // 2 - 2
    draw.text((tx, ty), text, fill="black", font=font)

    qr_dir = os.path.join("static", "qr_codes")
    os.makedirs(qr_dir, exist_ok=True)
    path = os.path.join(qr_dir, f"{tool_code}.png")
    labeled_img.save(path)
    return path


def qr_url_for_tool(tool_code: str) -> str:
    cfg = get_config()
    return f"{cfg.base_url.rstrip('/')}/tool/{tool_code}"
