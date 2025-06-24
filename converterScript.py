import re
import os
from xml.dom.minidom import parseString
from xml.etree.ElementTree import Element, SubElement, tostring

COMMAND_MAP = {
    "moveTo": lambda args: f"M {args[0]} {args[1]}",
    "moveToRelative": lambda args: f"m {args[0]} {args[1]}",
    "lineTo": lambda args: f"L {args[0]} {args[1]}",
    "lineToRelative": lambda args: f"l {args[0]} {args[1]}",
    "horizontalLineTo": lambda args: f"H {args[0]}",
    "horizontalLineToRelative": lambda args: f"h {args[0]}",
    "verticalLineTo": lambda args: f"V {args[0]}",
    "verticalLineToRelative": lambda args: f"v {args[0]}",
    "curveTo": lambda args: f"C {args[0]} {args[1]}, {args[2]} {args[3]}, {args[4]} {args[5]}",
    "curveToRelative": lambda args: f"c {args[0]} {args[1]}, {args[2]} {args[3]}, {args[4]} {args[5]}",
    "reflectiveCurveTo": lambda args: f"S {args[0]} {args[1]}, {args[2]} {args[3]}",
    "reflectiveCurveToRelative": lambda args: f"s {args[0]} {args[1]}, {args[2]} {args[3]}",
    "quadTo": lambda args: f"Q {args[0]} {args[1]}, {args[2]} {args[3]}",
    "quadToRelative": lambda args: f"q {args[0]} {args[1]}, {args[2]} {args[3]}",
    "reflectiveQuadTo": lambda args: f"T {args[0]} {args[1]}",
    "reflectiveQuadToRelative": lambda args: f"t {args[0]} {args[1]}",
    "arcTo": lambda args: (
        f"A {args[0]} {args[1]} 0 "
        f"{'1' if args[3].lower() == 'true' else '0'} "
        f"{'1' if args[4].lower() == 'true' else '0'} "
        f"{args[5]} {args[6]}"
    ),
    "arcToRelative": lambda args: (
        f"a {args[0]} {args[1]} 0 "
        f"{'1' if args[3].lower() == 'true' else '0'} "
        f"{'1' if args[4].lower() == 'true' else '0'} "
        f"{args[5]} {args[6]}"
    ),
    "close": lambda args: "Z"
}


def clean_arg(arg):
    return arg.strip().rstrip('f')


def extract_path_blocks(kotlin_code: str):
    """Возвращает список кортежей (params_str, path_body) для каждого path-блока."""
    blocks = []
    i = 0
    lines = kotlin_code.splitlines()
    n = len(lines)
    while i < n:
        line = lines[i]
        if 'path(' in line:
            # Собираем параметры path(...)
            params = []
            while '{' not in line:
                params.append(line)
                i += 1
                if i >= n:
                    break
                line = lines[i]
            if i >= n:
                break
            params.append(line.split('{', 1)[0])
            params_str = '\n'.join(params)
            # Собираем тело path {...} с учётом вложенных скобок
            block = []
            after_brace = line.split('{', 1)[1]
            block.append(after_brace)
            i += 1
            brace_level = 1
            while i < n and brace_level > 0:
                l = lines[i]
                brace_level += l.count('{')
                brace_level -= l.count('}')
                block.append(l)
                i += 1
            # Удаляем последнюю строку после закрывающей скобки
            if brace_level < 0 and block:
                block = block[:-1]
            blocks.append((params_str, '\n'.join(block).rsplit('}', 1)[0].strip()))
        else:
            i += 1
    # print(f'Найдено path-блоков: {len(blocks)}')
    return blocks


def parse_path_params(params_str):
    # fill
    fill = None
    alpha = None
    fill_found = False
    m = re.search(r'fill\s*=\s*SolidColor\(Color\(0x([0-9A-Fa-f]{8})\)\)', params_str)
    if m:
        hex_color = m.group(1)
        a = int(hex_color[0:2], 16) / 255
        fill = f"#{hex_color[2:]}"
        alpha = a
        fill_found = True
    elif re.search(r'fill\s*=\s*null', params_str) or re.search(r'fill\s*=\s*Color\.Transparent', params_str):
        fill = 'none'
        fill_found = True
    # fillAlpha
    fill_alpha = None
    m = re.search(r'fillAlpha\s*=\s*([\d.]+)f', params_str)
    if m:
        fill_alpha = float(m.group(1))
    # Итоговая прозрачность
    final_alpha = None
    if alpha is not None and fill_alpha is not None:
        final_alpha = alpha * fill_alpha
    elif alpha is not None:
        final_alpha = alpha
    elif fill_alpha is not None:
        final_alpha = fill_alpha
    # stroke
    stroke = None
    stroke_alpha = None
    stroke_width = None
    m = re.search(r'stroke\s*=\s*SolidColor\(Color\(0x([0-9A-Fa-f]{8})\)\)', params_str)
    if m:
        hex_color = m.group(1)
        a = int(hex_color[0:2], 16) / 255
        stroke = f"#{hex_color[2:]}"
        stroke_alpha = a
    elif re.search(r'stroke\s*=\s*null', params_str) or re.search(r'stroke\s*=\s*Color\.Transparent', params_str):
        stroke = 'none'
    m = re.search(r'strokeAlpha\s*=\s*([\d.]+)f', params_str)
    if m:
        stroke_alpha_val = float(m.group(1))
        if stroke_alpha is not None:
            stroke_alpha *= stroke_alpha_val
        else:
            stroke_alpha = stroke_alpha_val
    m = re.search(r'strokeLineWidth\s*=\s*([\d.]+)f', params_str)
    if m:
        stroke_width = float(m.group(1))
    # stroke cap/join
    stroke_linecap = None
    m = re.search(r'strokeLineCap\s*=\s*([A-Za-z]+)', params_str)
    if m:
        stroke_linecap = m.group(1).lower()
    stroke_linejoin = None
    m = re.search(r'strokeLineJoin\s*=\s*([A-Za-z]+)', params_str)
    if m:
        stroke_linejoin = m.group(1).lower()
    # fill-rule
    fill_rule = None
    m = re.search(r'pathFillType\s*=\s*([A-Za-z]+)', params_str)
    if m:
        if m.group(1).lower() == 'evenodd':
            fill_rule = 'evenodd'
        else:
            fill_rule = 'nonzero'
    # Если fill и stroke оба отсутствуют — теперь возвращаем значения по умолчанию
    if fill is None:
        fill = 'none'
    if stroke is None:
        stroke = 'none'
    # Если stroke есть, но stroke-width не задан — по умолчанию 1
    if stroke and stroke != 'none' and stroke_width is None:
        stroke_width = 1
    # DEBUG print
    print(f"PATH STYLE: fill={fill}, alpha={final_alpha}, stroke={stroke}, stroke_alpha={stroke_alpha}, stroke_width={stroke_width}, fill_rule={fill_rule}")
    return {
        "fill": fill if fill is not None else 'none',
        "alpha": final_alpha,
        "stroke": stroke if stroke is not None else 'none',
        "stroke_alpha": stroke_alpha,
        "stroke_width": stroke_width,
        "stroke_linecap": stroke_linecap,
        "stroke_linejoin": stroke_linejoin,
        "fill_rule": fill_rule
    }


def extract_vector_params(kotlin_code: str):
    # Извлекаем размеры
    width = height = viewbox_w = viewbox_h = None
    m = re.search(r'defaultWidth\s*=\s*([\d.]+)\.dp', kotlin_code)
    if m:
        width = float(m.group(1))
    m = re.search(r'defaultHeight\s*=\s*([\d.]+)\.dp', kotlin_code)
    if m:
        height = float(m.group(1))
    m = re.search(r'viewportWidth\s*=\s*([\d.]+)f', kotlin_code)
    if m:
        viewbox_w = float(m.group(1))
    m = re.search(r'viewportHeight\s*=\s*([\d.]+)f', kotlin_code)
    if m:
        viewbox_h = float(m.group(1))
    return {
        "width": width or 24,
        "height": height or 24,
        "viewbox_w": viewbox_w or width or 24,
        "viewbox_h": viewbox_h or height or 24,
    }


def parse_args_any(arg_str, expected_names, synonyms=None):
    arg_str = arg_str.replace('\n', ' ').replace('\r', ' ')
    arg_str = re.sub(r'\s+', ' ', arg_str)
    parts = []
    depth = 0
    current = ''
    for c in arg_str:
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
        if c == ',' and depth == 0:
            parts.append(current.strip())
            current = ''
        else:
            current += c
    if current.strip():
        parts.append(current.strip())
    args = {}
    for part in parts:
        if '=' in part:
            k, v = part.split('=', 1)
            args[k.strip()] = v.strip().strip('"')
        else:
            args[len(args)] = part.strip().strip('"')
    if synonyms:
        for syn, main in synonyms.items():
            if syn in args and main not in args:
                args[main] = args[syn]
    result = []
    for i, name in enumerate(expected_names):
        if name in args:
            result.append(args[name])
        elif i in args:
            result.append(args[i])
        else:
            result.append('0')  # Подставляем 0 вместо ''
    return result


def clean_svg_path(path_str):
    # Удаляем суффикс 'f' у чисел (например, 12.0f -> 12.0)
    path_str = re.sub(r'(\d+\.?\d*)f', r'\1', path_str)
    # Заменяем все запятые на пробелы (SVG не любит запятые между числами)
    path_str = path_str.replace(',', ' ')
    # Удаляем лишние пробелы
    path_str = re.sub(r'\s+', ' ', path_str)
    return path_str.strip()


def extract_path_data(block):
    path_commands = []
    valid_commands = set(COMMAND_MAP.keys())
    expected_args = {
        "moveTo": ["x", "y"],
        "moveToRelative": ["dx", "dy"],
        "lineTo": ["x", "y"],
        "lineToRelative": ["dx", "dy"],
        "horizontalLineTo": ["x"],
        "horizontalLineToRelative": ["dx"],
        "verticalLineTo": ["y"],
        "verticalLineToRelative": ["dy"],
        "curveTo": ["x1", "y1", "x2", "y2", "x3", "y3"],
        "curveToRelative": ["dx1", "dy1", "dx2", "dy2", "dx3", "dy3"],
        "reflectiveCurveTo": ["x2", "y2", "x3", "y3"],
        "reflectiveCurveToRelative": ["dx2", "dy2", "dx3", "dy3"],
        "quadTo": ["x1", "y1", "x2", "y2"],
        "quadToRelative": ["dx1", "dy1", "dx2", "dy2"],
        "reflectiveQuadTo": ["x", "y"],
        "reflectiveQuadToRelative": ["dx", "dy"],
        "arcTo": ["rx", "ry", "angle", "isMoreThanHalf", "isPositiveArc", "x1", "y1"],
        "arcToRelative": ["rx", "ry", "angle", "isMoreThanHalf", "isPositiveArc", "dx1", "dy1"],
        "close": []
    }
    arc_synonyms = {
        "a": "rx", "b": "ry", "theta": "angle",
        "horizontalEllipseRadius": "rx", "verticalEllipseRadius": "ry",
        "horizontalEllipsisRadius": "rx", "verticalEllipsisRadius": "ry",
        "dx1": "x1", "dy1": "y1", "dx": "dx1", "dy": "dy1"
    }
    def find_commands(block):
        i = 0
        n = len(block)
        while i < n:
            while i < n and not (block[i].isalpha() or block[i] == '_'):
                i += 1
            start = i
            while i < n and (block[i].isalpha() or block[i] == '_'):
                i += 1
            name = block[start:i]
            if not name:
                continue
            if i < n and block[i] == '(': 
                i += 1
                arg_start = i
                depth = 1
                while i < n and depth > 0:
                    if block[i] == '(': depth += 1
                    elif block[i] == ')': depth -= 1
                    i += 1
                arg_str = block[arg_start:i - 1]
                if name in valid_commands:
                    if name in expected_args:
                        synonyms = arc_synonyms if name in ["arcTo", "arcToRelative"] else None
                        args = parse_args_any(arg_str, expected_args[name], synonyms)
                        print(f"[SVG] {name}({', '.join(args)})")
                    else:
                        args = [clean_arg(a) for a in arg_str.split(',') if a.strip()]
                        print(f"[SVG] {name}({', '.join(args)})")
                    try:
                        svg_cmd = COMMAND_MAP[name](args)
                        path_commands.append(svg_cmd)
                    except Exception as e:
                        print(f"⚠️ Ошибка в команде {name} с аргументами {args}: {e}")
            else:
                i += 1
    find_commands(block)
    raw_path = " ".join(path_commands)
    return clean_svg_path(raw_path)


def convert_to_svg(paths, params):
    svg = Element('svg', xmlns="http://www.w3.org/2000/svg",
                  width=str(params["width"]), height=str(params["height"]),
                  viewBox=f"0 0 {params['viewbox_w']} {params['viewbox_h']}")
    for path_data, style in paths:
        if style is None:
            continue
        path_attribs = {"d": path_data}
        if style["fill"] is not None:
            path_attribs["fill"] = style["fill"]
        if style["alpha"] is not None and style["alpha"] < 1:
            path_attribs["fill-opacity"] = str(style["alpha"])
        if style["stroke"] is not None:
            path_attribs["stroke"] = style["stroke"]
        if style["stroke_alpha"] is not None and style["stroke_alpha"] < 1:
            path_attribs["stroke-opacity"] = str(style["stroke_alpha"])
        if style["stroke_width"] is not None:
            path_attribs["stroke-width"] = str(style["stroke_width"])
        if style["stroke_linecap"] is not None:
            path_attribs["stroke-linecap"] = style["stroke_linecap"]
        if style["stroke_linejoin"] is not None:
            path_attribs["stroke-linejoin"] = style["stroke_linejoin"]
        if style["fill_rule"] is not None:
            path_attribs["fill-rule"] = style["fill_rule"]
        SubElement(svg, 'path', **path_attribs)
    return parseString(tostring(svg)).toprettyxml()


def extract_named_vector_blocks(kotlin_code: str):
    """Возвращает список кортежей (vector_name, vector_block) для каждого ImageVector в файле."""
    results = []
    pattern = re.compile(r'val\s+Icons\.([A-Za-z0-9_]+)\.([A-Za-z0-9_]+):\s*ImageVector\s*by\s*lazy\s*\{', re.DOTALL)
    for match in pattern.finditer(kotlin_code):
        style, name = match.group(1), match.group(2)
        start = match.end()
        brace_level = 1
        i = start
        while i < len(kotlin_code) and brace_level > 0:
            if kotlin_code[i] == '{':
                brace_level += 1
            elif kotlin_code[i] == '}':
                brace_level -= 1
            i += 1
        block = kotlin_code[start:i-1]
        results.append((f"{style}_{name}", block))
    return results


def process_directory(input_dir: str, output_dir: str):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for filename in os.listdir(input_dir):
        if filename.endswith(".kt"):
            file_path = os.path.join(input_dir, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                kotlin_code = f.read()

            # Извлекаем все ImageVector-блоки (Rounded, Outlined, ...)
            named_blocks = extract_named_vector_blocks(kotlin_code)
            if not named_blocks:
                # Фоллбэк: если не найдено, работаем как раньше
                vector_params = extract_vector_params(kotlin_code)
                path_blocks = extract_path_blocks(kotlin_code)
                paths = []
                for params_str, block in path_blocks:
                    style = parse_path_params(params_str)
                    path_data = extract_path_data(block)
                    if not path_data.strip():
                        continue
                    paths.append((path_data, style))
                if not paths:
                    print(f"⚠️ Пропущен пустой файл: {filename}")
                    continue
                svg = convert_to_svg(paths, vector_params)
                output_file = os.path.join(output_dir, f"{os.path.splitext(filename)[0]}.svg")
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(svg)
                print(f"✅ SVG создан: {output_file}")
                continue

            for vector_name, vector_block in named_blocks:
                # Вытаскиваем параметры и path только из этого блока
                vector_params = extract_vector_params(vector_block)
                path_blocks = extract_path_blocks(vector_block)
                paths = []
                for params_str, block in path_blocks:
                    style = parse_path_params(params_str)
                    # Для Outlined: если нет stroke, делаем stroke чёрным, fill none
                    if style and vector_name.lower().startswith("outlined"):
                        if (not style["stroke"] or style["stroke"] == "none"):
                            style["stroke"] = "#000000"
                            style["stroke_width"] = 1
                        style["fill"] = "none"
                    path_data = extract_path_data(block)
                    if not path_data.strip():
                        continue
                    paths.append((path_data, style))
                if not paths:
                    print(f"⚠️ Пропущен пустой блок: {vector_name} в {filename}")
                    continue
                svg = convert_to_svg(paths, vector_params)
                output_file = os.path.join(output_dir, f"{os.path.splitext(filename)[0]}_{vector_name}.svg")
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(svg)
                print(f"✅ SVG создан: {output_file}")


def main():
    input_dir = "vectors"  # Входная папка с .kt
    output_dir = "svg_output"  # Куда сохранить .svg

    process_directory(input_dir, output_dir)


if __name__ == "__main__":
    main()
