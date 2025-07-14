#!/usr/bin/env python3

import os
import re
import argparse
from pathlib import Path
from typing import List, Tuple, Set

CODE_EXTENSIONS = {'.py'}
TEMPLATE_EXTENSIONS = {'.html', '.js'}
STYLESHEET_EXTENSIONS = {'.css'}
EXCLUDED_FILES = {'__init__.py', 'setup.py', 'main.py'}
DEFAULT_EXCLUDED_FOLDERS = {'__pycache__', 'migrations', 'management', 'obsolete', '.venv', 'venv', '.git', 'build', 'dist', 'docs', 'tests'}

STANDARD_MODULES = (
    'os.', 'sys.', 're.', 'pathlib.', 'argparse.', 'typing.', 'datetime.', 'json.',
    'logging.', 'collections.', 'time.', 'string.', 'random.', 'subprocess.'
)

def get_app_name(root_dir: str) -> str:
    return Path(root_dir).resolve().name

def load_gitignore_patterns(root_dir: str) -> Set[str]:
    patterns = set()
    gitignore = Path(root_dir) / '.gitignore'
    if gitignore.exists():
        with gitignore.open('r', encoding='utf-8') as f:
            for line in f:
                pattern = line.strip()
                if pattern and not pattern.startswith('#'):
                    patterns.add(pattern)
    return patterns

def is_ignored(path: Path, root_dir: Path, patterns: Set[str], excluded_dirs: Set[str], included_dirs: Set[str]) -> bool:
    relative_path = path.relative_to(root_dir)

    if included_dirs:
        if not any(part in included_dirs for part in relative_path.parts):
            return True

    if any(part in DEFAULT_EXCLUDED_FOLDERS.union(excluded_dirs) for part in relative_path.parts):
        return True

    if path.name in EXCLUDED_FILES:
        return True

    for pattern in patterns:
        try:
            if relative_path.match(pattern):
                return True
        except re.error:
            continue
    return False

def get_folder_structure(root_dir: str, ignore_patterns: Set[str], excluded_dirs: Set[str], included_dirs: Set[str]) -> str:
    structure = []
    for root, dirs, files in os.walk(root_dir):
        root_path = Path(root)
        if is_ignored(root_path, Path(root_dir), ignore_patterns, excluded_dirs, included_dirs):
            dirs[:] = []
            continue
        rel_root = root_path.relative_to(root_dir)
        level = len(rel_root.parts)
        indent = '  ' * level
        structure.append(f"{indent}- {root_path.name}/")
        sub_indent = '  ' * (level + 1)
        for f in sorted(files):
            file_path = root_path / f
            ext = file_path.suffix
            if (ext in CODE_EXTENSIONS or ext in TEMPLATE_EXTENSIONS) and not is_ignored(file_path, Path(root_dir), ignore_patterns, excluded_dirs, included_dirs):
                structure.append(f"{sub_indent}- {f}")
    return '\n'.join(structure)

def clean_imports_and_comments(code: str, keep_comments: bool = False) -> str:
    code = re.sub(r'""".*?"""', '', code, flags=re.DOTALL)
    code = re.sub(r"'''(.*?)'''", '', code, flags=re.DOTALL)
    lines = code.splitlines()
    cleaned = []
    for line in lines:
        if not keep_comments:
            line = re.sub(r'#.*', '', line)
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('import') or stripped.startswith('from'):
            if any(mod in stripped for mod in STANDARD_MODULES):
                continue
        cleaned.append(line.rstrip())
    return '\n'.join(cleaned)

def compact_python_code(code: str) -> str:
    lines = code.splitlines()
    cleaned = []
    previous_blank = False
    for line in lines:
        if line.strip() == '':
            if not previous_blank:
                cleaned.append('')
                previous_blank = True
        else:
            cleaned.append(line)
            previous_blank = False
    return '\n'.join(cleaned)

def summarize_functions_only(code: str) -> str:
    lines = code.splitlines()
    summarized = []
    inside_def = False
    called_funcs = set()

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('class '):
            summarized.append(line.rstrip())
            continue

        if stripped.startswith('def '):
            if inside_def and called_funcs:
                summarized[-1] += f"  # calling: {', '.join(sorted(called_funcs))}"
            summarized.append(line.rstrip() + ' pass')
            inside_def = True
            called_funcs.clear()
            continue

        if inside_def:
            matches = re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)\(', stripped)
            for func_name in matches:
                if func_name not in (
                    'self', 'super', 'range', 'len', 'print',
                    'dict', 'list', 'set', 'str', 'int', 'float', 'bool'
                ) and not any(func_name.startswith(p.rstrip('.')) for p in STANDARD_MODULES):
                    called_funcs.add(func_name)

            current_indent = len(line) - len(line.lstrip())
            if stripped and current_indent == 0:
                if called_funcs:
                    summarized[-1] += f"  # calling: {', '.join(sorted(called_funcs))}"
                inside_def = False
                summarized.append(line.rstrip())
            continue

        if stripped:
            summarized.append(line.rstrip())

    if inside_def and called_funcs:
        summarized[-1] += f"  # calling: {', '.join(sorted(called_funcs))}"

    return '\n'.join(summarized)

def summarize_django_models(code: str) -> str:
    model_blocks = []
    lines = code.splitlines()
    inside_model = False
    class_name = ''
    block = []

    for line in lines:
        stripped = line.strip()

        if stripped.startswith('class ') and '(models.Model)' in stripped:
            if block:
                model_blocks.append((class_name, block))
            class_name = stripped.split()[1].split('(')[0]
            block = [line]
            inside_model = True
            continue

        if inside_model:
            if stripped.startswith('class ') or stripped.startswith('def '):
                model_blocks.append((class_name, block))
                inside_model = False
                block = []
                continue
            block.append(line)

    if inside_model and block:
        model_blocks.append((class_name, block))

    field_map = {
        'CharField': 'Char',
        'TextField': 'Text',
        'IntegerField': 'Int',
        'BooleanField': 'Bool',
        'DateField': 'Date',
        'DateTimeField': 'DateTime',
        'ForeignKey': 'FK',
        'OneToOneField': 'One',
        'ManyToManyField': 'Many',
        'DecimalField': 'Dec',
        'FloatField': 'Float',
        'JSONField': 'JSON',
        'FileField': 'File',
        'ImageField': 'Image',
    }

    summary = []

    for name, block in model_blocks:
        summary.append(f"class {name}(models.Model):")
        for line in block[1:]:
            m = re.match(r'\s*(\w+)\s*=\s*models\.(\w+)\((.*?)\)', line)
            if m:
                field_name, field_type, field_args = m.groups()
                short = field_map.get(field_type, field_type)
                if short == 'FK':
                    fk_target = field_args.split(',')[0].strip()
                    summary.append(f"    {field_name:<10} = FK({fk_target})")
                else:
                    summary.append(f"    {field_name:<10} = {short}")
        summary.append("")
    return '\n'.join(summary)

def clean_code(code: str, summary_level: str = 'high', keep_comments: bool = False) -> str:
    if summary_level == 'none' and keep_comments:
        return code
    code = clean_imports_and_comments(code, keep_comments=keep_comments)
    code = compact_python_code(code)
    if summary_level == 'high':
        code = summarize_functions_only(code)
        return summarize_django_models(code)
    return code

def clean_html(content: str) -> str:
    content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
    content = re.sub(r'<style.*?>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r'\s+style=([\'"]).*?\1', '', content, flags=re.IGNORECASE)
    return "\n".join(line for line in content.splitlines() if line.strip())

def clean_javascript(content: str) -> str:
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    content = re.sub(r'//.*', '', content)
    content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
    return "\n".join(line for line in content.splitlines() if line.strip())

def collect_source_files(
    root_dir: str,
    ignore_patterns: Set[str],
    summary_level: str,
    include_templates: bool,
    keep_comments: bool,
    include_admin: bool,
    include_utils: bool,
    excluded_dirs: Set[str],
    included_dirs: Set[str]
) -> List[Tuple[str, str]]:
    sources: List[Tuple[str, str]] = []
    root_path_obj = Path(root_dir)

    for root, dirs, files in os.walk(root_dir):
        current_root_path = Path(root)
        dirs[:] = [d for d in dirs if not is_ignored(current_root_path / d, root_path_obj, ignore_patterns, excluded_dirs, included_dirs)]

        for f in sorted(files):
            file_path = current_root_path / f
            ext = file_path.suffix

            if is_ignored(file_path, root_path_obj, ignore_patterns, excluded_dirs, included_dirs):
                continue

            if ext in STYLESHEET_EXTENSIONS:
                continue

            if not include_admin and ext == '.py':
                if f.startswith('admin') or 'admin' in file_path.parts:
                    continue

            if not include_utils and (f == 'utils.py' or 'util' in file_path.parts):
                continue

            if ext in CODE_EXTENSIONS or (include_templates and ext in TEMPLATE_EXTENSIONS):
                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    if ext == '.py':
                        content = clean_code(content, summary_level=summary_level, keep_comments=keep_comments)
                    elif ext == '.html':
                        content = clean_html(content)
                    elif ext == '.js':
                        content = clean_javascript(content)

                    if content.strip():
                        rel_path = file_path.relative_to(root_path_obj)
                        sources.append((str(rel_path), content))
                except Exception as e:
                    print(f"Could not read or process file {file_path}: {e}")
                    continue

    return sorted(sources, key=lambda item: (0 if item[0].endswith('main.py') else 1, item[0]))

def write_markdown(output_file: str, app_name: str, sources: List[Tuple[str, str]], structure: str = None):
    with open(output_file, 'w', encoding='utf-8') as out:
        out.write(f'# Python Project Summary: {app_name}\n\n')
        if structure:
            out.write('## Folder Structure\n')
            out.write('```text\n')
            out.write(structure)
            out.write('\n```\n\n')
        out.write('---\n\n')
        for path, code in sources:
            out.write(f'### `{path}`\n')
            ext = Path(path).suffix
            lang = 'python' if ext == '.py' else 'html' if ext == '.html' else 'javascript'
            out.write(f'```{lang}\n{code.strip()}\n```\n\n')

def main():
    parser = argparse.ArgumentParser(description="Summarize a Python project into a Markdown file.")
    parser.add_argument('input_dir', help='Path to the project directory')
    parser.add_argument('-o', '--output_file', help='Output Markdown file name (in "docs" folder)')
    parser.add_argument('--include_structure', action='store_true', help='Include folder structure')
    parser.add_argument('--include_templates', action='store_true', help='Include .html and .js files')
    parser.add_argument('--summary', choices=['high', 'mid', 'none', 'model'], default='none', help='Python code summary level')
    parser.add_argument('--keep_comments', action='store_true', help='Keep Python comments if summary=none')
    parser.add_argument('--admin', action='store_true', dest='include_admin', help='Include Django admin files')
    parser.add_argument('--utils', action='store_true', dest='include_utils', help='Include utility modules')
    parser.add_argument('--exclude_dirs', nargs='*', default=[], help='Additional directories to exclude')
    parser.add_argument('--include_dirs', nargs='*', default=[], help='Only include files in these directories')
    parser.add_argument('--management', action='store_true', dest='include_management', help='Include the “management” folder (excluded by default)')

    args = parser.parse_args()

    app_name = get_app_name(args.input_dir)

    input_path = Path(args.input_dir).resolve()

    if args.output_file:
        output_file = Path(args.output_file)
        if not output_file.is_absolute():
            output_file = input_path / output_file.name
    else:
        output_file = input_path / f"src_{app_name}_{'original' if args.summary == 'none' else f'summary_{args.summary}'}.md"

    excluded_dirs = set(args.exclude_dirs)
    if not args.include_management:
        excluded_dirs.add('management')    
    included_dirs = set(args.include_dirs)
    ignore_patterns = load_gitignore_patterns(args.input_dir)

    structure = get_folder_structure(args.input_dir, ignore_patterns, excluded_dirs, included_dirs) if args.include_structure else None

    sources = collect_source_files(
        args.input_dir,
        ignore_patterns,
        summary_level=args.summary,
        include_templates=args.include_templates,
        keep_comments=args.keep_comments,
        include_admin=args.include_admin,
        include_utils=args.include_utils,
        excluded_dirs=excluded_dirs,
        included_dirs=included_dirs
    )

    write_markdown(output_file, app_name, sources, structure)
    print(f"✅ Project summary written to: {output_file.resolve().as_uri()}")

if __name__ == '__main__':
    main()