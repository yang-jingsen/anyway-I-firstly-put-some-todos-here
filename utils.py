from kivy.uix.widget import Widget

from defines import DEBUG
from kivy.core.text import Label as CoreLabel

def log(text, color, debug=DEBUG):
    color_codes = {
        "red": "\033[31m",  # error
        "green": "\033[32m",  # drawing operation
        "yellow": "\033[33m",  # file operation
        "blue": "\033[34m",
        "magenta": "\033[35m",
        "cyan": "\033[36m",
        "white": "\033[37m",
        "reset": "\033[0m"  # 用来重置颜色
    }
    if debug:
        # 设置颜色和打印文本
        colored_text = f"{color_codes.get(color, color_codes['reset'])}{text}{color_codes['reset']}"
        print(colored_text)

def hex_to_rgba(hex_str):
    hex_str = hex_str.lstrip('#')
    r = int(hex_str[0:2], 16) / 255.0
    g = int(hex_str[2:4], 16) / 255.0
    b = int(hex_str[4:6], 16) / 255.0
    return (r, g, b, 1)


def rgb_to_hex(rgb):
    r, g, b, _ = rgb
    return '#{:02X}{:02X}{:02X}'.format(int(r * 255), int(g * 255), int(b * 255))


def get_fitted_text(text, max_width, font_size, font_name):
    label = CoreLabel(text=text, font_size=font_size, font_name=font_name)
    label.refresh()
    if label.texture.width <= max_width:
        return text
    while label.texture.width > max_width and len(text) > 0:
        text = text[:-1]
        label.name = text + "..."
        label.refresh()
    return label.name


def get_absolute_pos(widget):
    x, y = widget.x, widget.y
    parent = widget.parent
    while parent:
        if isinstance(parent, Widget):  # 确保遍历的是 Widget 或布局
            x += parent.x
            y += parent.y
            parent = parent.parent
        else:
            break
    return x, y

def log_position(instance):
    # 获取组件的位置并打印
    pos = get_absolute_pos(instance)
    log(f"Component absolute position: {pos}", "green")