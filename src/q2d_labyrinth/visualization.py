from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .case import CaseConfig
from .solver import SolveResult


def _fmt_pressure(value: float) -> str:
    if abs(value) >= 1.0e6:
        return f"{value / 1.0e6:.3f} MPa"
    if abs(value) >= 1.0e3:
        return f"{value / 1.0e3:.1f} kPa"
    return f"{value:.1f} Pa"


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/simhei.ttf",
    ]
    for item in candidates:
        try:
            return ImageFont.truetype(item, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _center_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int] = (31, 41, 51),
) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text((xy[0] - w / 2, xy[1] - h / 2), text, font=font, fill=fill)


def _pressure_color(p: float, min_p: float, max_p: float) -> tuple[int, int, int]:
    ratio = (p - min_p) / max(max_p - min_p, 1.0)
    red = int(50 + 190 * ratio)
    blue = int(220 - 150 * ratio)
    green = int(105 + 50 * (1.0 - abs(ratio - 0.5) * 2.0))
    return red, green, blue


def _dashed_line(
    draw: ImageDraw.ImageDraw,
    start: tuple[float, float],
    end: tuple[float, float],
    fill: tuple[int, int, int],
    width: int = 2,
    dash: int = 8,
    gap: int = 6,
) -> None:
    x1, y1 = start
    x2, y2 = end
    length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    if length <= 0:
        return
    dx = (x2 - x1) / length
    dy = (y2 - y1) / length
    pos = 0.0
    while pos < length:
        seg_end = min(pos + dash, length)
        draw.line((x1 + dx * pos, y1 + dy * pos, x1 + dx * seg_end, y1 + dy * seg_end), fill=fill, width=width)
        pos += dash + gap


def write_geometry_pressure_png(case: CaseConfig, result: SolveResult, path: str | Path) -> None:
    """Draw a PNG axial section of the labyrinth seal with per-tooth pressures."""
    geometry = case.geometry
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    width = max(1300, 210 * geometry.tooth_count)
    height = 520
    margin_x = 80
    axis_y = 380
    shaft_h = 52
    casing_y = 105
    gap_h = 34
    tooth_h = 175
    tooth_tip_y = axis_y - shaft_h - gap_h
    tooth_root_y = tooth_tip_y - tooth_h
    cavity_top_y = tooth_root_y

    image = Image.new("RGB", (width, height), (247, 249, 251))
    draw = ImageDraw.Draw(image)
    title_font = _font(26, bold=True)
    label_font = _font(16, bold=True)
    small_font = _font(14)
    tiny_font = _font(13)

    length = geometry.total_length
    if length <= 0.0:
        length = geometry.tooth_count * geometry.tooth_width + max(0, geometry.tooth_count - 1) * geometry.cavity_length
    drawable_w = width - 2 * margin_x
    scale_x = drawable_w / max(length, 1.0e-12)

    def sx(x: float) -> float:
        return margin_x + x * scale_x

    min_p = min([item.p_down for item in result.teeth] + [case.boundary.outlet_pressure])
    max_p = max([item.p_up for item in result.teeth] + [case.boundary.inlet_pressure])

    draw.text((margin_x, 32), f"{result.case_name} - geometry and pressure distribution", font=title_font, fill=(31, 41, 51))
    draw.text(
        (margin_x, 66),
        f"Mass flow: {result.mass_flow:.6g} kg/s, max Mach: {result.max_mach:.3f}",
        font=small_font,
        fill=(82, 96, 109),
    )

    draw.rectangle((margin_x, casing_y, width - margin_x, cavity_top_y), fill=(217, 226, 236))
    draw.rectangle((margin_x, tooth_tip_y, width - margin_x, axis_y - shaft_h), fill=(232, 244, 253))
    draw.rectangle((margin_x, axis_y - shaft_h, width - margin_x, axis_y), fill=(154, 165, 177))
    draw.rectangle((margin_x, axis_y - shaft_h + 12, width - margin_x, axis_y), fill=(123, 135, 148))
    draw.line((margin_x, tooth_tip_y, width - margin_x, tooth_tip_y), fill=(82, 96, 109), width=2)
    _dashed_line(draw, (margin_x, axis_y - shaft_h), (width - margin_x, axis_y - shaft_h), fill=(82, 96, 109), width=2)
    draw.text((margin_x, axis_y + 18), "rotor / shaft", font=small_font, fill=(31, 41, 51))
    draw.text((width - margin_x - 145, tooth_tip_y - 24), "tooth tip line", font=tiny_font, fill=(82, 96, 109))
    draw.text((width - margin_x - 130, axis_y - shaft_h - 24), "shaft surface", font=tiny_font, fill=(82, 96, 109))
    draw.text((margin_x, tooth_tip_y + 58), f"Inlet {_fmt_pressure(case.boundary.inlet_pressure)}", font=label_font, fill=(31, 41, 51))

    x = geometry.inlet_length
    for idx, tooth in enumerate(result.teeth, start=1):
        tooth_x = sx(x)
        tooth_w = max(18.0, geometry.tooth_width * scale_x)
        color = _pressure_color(tooth.p_up, min_p, max_p)
        draw.rectangle(
            (tooth_x, tooth_root_y, tooth_x + tooth_w, tooth_tip_y),
            fill=color,
            outline=(51, 78, 104),
            width=2,
        )
        _center_text(draw, (tooth_x + tooth_w / 2, tooth_root_y - 22), f"Tooth {idx}", label_font)
        _center_text(draw, (tooth_x + tooth_w / 2, tooth_root_y + 48), "p up", small_font)
        _center_text(draw, (tooth_x + tooth_w / 2, tooth_root_y + 70), _fmt_pressure(tooth.p_up), small_font)
        _center_text(draw, (tooth_x + tooth_w / 2, tooth_root_y + 108), "p down", small_font)
        _center_text(draw, (tooth_x + tooth_w / 2, tooth_root_y + 130), _fmt_pressure(tooth.p_down), small_font)

        x += geometry.tooth_width
        if idx < geometry.tooth_count:
            cav_x = sx(x)
            cav_w = max(20.0, geometry.cavity_length * scale_x)
            draw.rectangle(
                (cav_x, tooth_tip_y, cav_x + cav_w, axis_y - shaft_h),
                fill=(215, 239, 255),
                outline=(159, 179, 200),
                width=1,
            )
            _center_text(draw, (cav_x + cav_w / 2, tooth_tip_y + 58), f"cavity {idx}", small_font)
            _center_text(draw, (cav_x + cav_w / 2, tooth_tip_y + 82), _fmt_pressure(tooth.p_down), small_font)
            x += geometry.cavity_length

    outlet_text = f"Outlet {_fmt_pressure(result.outlet_pressure_calculated)}"
    outlet_bbox = draw.textbbox((0, 0), outlet_text, font=label_font)
    draw.text((width - margin_x - (outlet_bbox[2] - outlet_bbox[0]), tooth_tip_y + 50), outlet_text, font=label_font, fill=(31, 41, 51))

    draw.line((margin_x, 440, width - margin_x, 440), fill=(82, 96, 109), width=2)
    draw.text((margin_x, 462), f"Total axial length: {geometry.total_length:.6g} m", font=tiny_font, fill=(82, 96, 109))
    draw.text((margin_x + 300, 462), f"Clearance: {geometry.clearance:.6g} m", font=tiny_font, fill=(82, 96, 109))
    draw.text((margin_x + 540, 462), f"Diameter: {geometry.diameter:.6g} m", font=tiny_font, fill=(82, 96, 109))
    draw.text(
        (margin_x, 490),
        "Color changes from low pressure blue to high pressure red. Pressure labels are written on the corresponding teeth and cavities.",
        font=tiny_font,
        fill=(82, 96, 109),
    )

    image.save(path, format="PNG")
