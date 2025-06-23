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
    "arcTo": lambda args: f"A {args[0]} {args[1]} {args[2]} {args[3]} {args[4]} {args[5]} {args[6]}",
    "arcToRelative": lambda args: f"a {args[0]} {args[1]} {args[2]} {args[3]} {args[4]} {args[5]} {args[6]}",
    "close": lambda args: "Z"
}


def clean_arg(arg):
    return arg.strip().rstrip('f')


def extract_path_data(kotlin_code: str) -> str:
    lines = kotlin_code.splitlines()
    path_blocks = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if 'path(' in line:
            # Найти первую фигурную скобку
            while '{' not in line and i < n - 1:
                i += 1
                line = lines[i]
            if '{' in line:
                block_lines = []
                # Считаем вложенность фигурных скобок
                brace_level = line.count('{') - line.count('}')
                # Добавляем всё после первой {
                block_lines.append(line.split('{', 1)[1])
                i += 1
                while i < n and brace_level > 0:
                    l = lines[i]
                    brace_level += l.count('{') - l.count('}')
                    block_lines.append(l)
                    i += 1
                path_blocks.append('\n'.join(block_lines))
        else:
            i += 1
    print(f"DEBUG: Найдено блоков path: {len(path_blocks)}")
    for idx, block in enumerate(path_blocks):
        print(f"DEBUG: Блок {idx + 1}: {block[:200]}...")
    if path_blocks:
        print("=== ПОЛНЫЙ ПЕРВЫЙ БЛОК PATH ===")
        print(path_blocks[0])
        print("=== КОНЕЦ ПЕРВОГО БЛОКА ===")
    path_commands = []
    valid_commands = set(COMMAND_MAP.keys())

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
                    if block[i] == '(':
                        depth += 1
                    elif block[i] == ')':
                        depth -= 1
                    i += 1
                arg_str = block[arg_start:i - 1]
                if name in valid_commands:
                    args = [clean_arg(a) for a in arg_str.split(',') if a.strip()]
                    try:
                        svg_cmd = COMMAND_MAP[name](args)
                        path_commands.append(svg_cmd)
                    except Exception as e:
                        print(f"⚠️ Ошибка в команде {name} с аргументами {args}: {e}")
            else:
                i += 1

    for block in path_blocks:
        find_commands(block)
    return " ".join(path_commands)


def convert_to_svg(path_data: str, width: int = 24, height: int = 24) -> str:
    svg = Element('svg', xmlns="http://www.w3.org/2000/svg",
                  width=str(width), height=str(height),
                  viewBox=f"0 0 {width} {height}")
    SubElement(svg, 'path', d=path_data, fill="black")
    return parseString(tostring(svg)).toprettyxml()


def process_directory(input_dir: str, output_dir: str):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for filename in os.listdir(input_dir):
        if filename.endswith(".kt"):
            file_path = os.path.join(input_dir, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                kotlin_code = f.read()

            path_data = extract_path_data(kotlin_code)
            if not path_data.strip():
                print(f"⚠️ Пропущен пустой файл: {filename}")
                continue

            svg = convert_to_svg(path_data)
            output_file = os.path.join(output_dir, f"{os.path.splitext(filename)[0]}.svg")
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(svg)
            print(f"✅ SVG создан: {output_file}")


def main():
    input_dir = "vectors"  # Входная папка с .kt
    output_dir = "svg_output"  # Куда сохранить .svg

    process_directory(input_dir, output_dir)


if __name__ == "__main__":
    main()
