from __future__ import annotations

import html
import re

COMMENT_CODE_NEWLINE = "\ue000"


def render_jira_markup(body: str) -> str:
    body = _preserve_code_macro_newlines(body)
    lines = body.splitlines() or [body]
    rendered_blocks = []
    current_table: list[str] = []
    in_code_block = False
    current_code_lines: list[str] = []

    for line in lines:
        if in_code_block:
            code_close = _code_close_match(line)
            if code_close:
                current_code_lines.append(line[: code_close.start()])
                rendered_blocks.append(
                    _format_code_block("\n".join(current_code_lines))
                )
                in_code_block = False
                current_code_lines = []
                remaining_line = line[code_close.end() :].strip()
                if remaining_line:
                    rendered_blocks.append(_format_line(remaining_line))
                continue

            current_code_lines.append(line)
            continue

        code_open = _code_open_match(line)
        if code_open:
            if current_table:
                rendered_blocks.append(_format_table(current_table))
                current_table = []
            code_content = code_open.group(1)
            code_close = _code_close_match(code_content)
            if code_close:
                rendered_blocks.append(
                    _format_code_block(code_content[: code_close.start()])
                )
                remaining_line = code_content[code_close.end() :].strip()
                if remaining_line:
                    rendered_blocks.append(_format_line(remaining_line))
                continue

            in_code_block = True
            current_code_lines = [code_content]
            continue

        if _is_jira_table_line(line):
            current_table.append(line)
            continue

        if current_table:
            rendered_blocks.append(_format_table(current_table))
            current_table = []
        rendered_blocks.append(_format_line(line))

    if current_table:
        rendered_blocks.append(_format_table(current_table))

    if in_code_block:
        rendered_blocks.append(_format_code_block("\n".join(current_code_lines)))

    return "".join(rendered_blocks)


def _format_line(line: str) -> str:
    return "".join(_format_line_blocks(line))


def _format_line_blocks(line: str) -> list[str]:
    blocks = []
    cursor = 0
    while cursor < len(line):
        table_start = _find_inline_table_start(line, cursor)
        if table_start is None:
            blocks.append(_format_text_line(line[cursor:]))
            break

        if table_start > cursor:
            blocks.append(_format_text_line(line[cursor:table_start]))

        rows, table_end = _parse_inline_table(line, table_start)
        if not rows:
            blocks.append(_format_text_line(line[table_start:]))
            break

        blocks.append(_format_table_rows(rows))
        cursor = table_end

    return blocks or [_format_text_line("")]


def _format_text_line(line: str) -> str:
    if not line.strip():
        return ""
    content = _format_inline(line.strip())
    return f'<div class="issue-comment-line">{content}</div>'


def _is_jira_table_line(line: str) -> bool:
    stripped = line.strip()
    return (stripped.startswith("||") and stripped.endswith("||")) or (
        stripped.startswith("|") and stripped.endswith("|")
    )


def _format_table(lines: list[str]) -> str:
    rows = []
    for line in lines:
        header = line.strip().startswith("||")
        tag = "th" if header else "td"
        cells = "".join(
            f"<{tag}>{_format_inline(cell.strip())}</{tag}>"
            for cell in _split_jira_table_row(line, header)
        )
        rows.append(f"<tr>{cells}</tr>")
    return f'<table class="issue-comment-table">{"".join(rows)}</table>'


def _format_table_rows(rows: list[list[str]]) -> str:
    rendered_rows = []
    for row in rows:
        cells = "".join(f"<td>{_format_inline(cell.strip())}</td>" for cell in row)
        rendered_rows.append(f"<tr>{cells}</tr>")
    return f'<table class="issue-comment-table">{"".join(rendered_rows)}</table>'


def _format_code_block(code: str) -> str:
    return (
        '<div class="issue-comment-code-block">'
        f"<pre><code>{_html(_restore_code_macro_newlines(code).strip())}</code></pre>"
        "</div>"
    )


def _split_jira_table_row(line: str, header: bool) -> list[str]:
    stripped = line.strip()
    if header:
        content = stripped[2:-2]
        delimiter = "||"
    else:
        content = stripped[1:-1]
        delimiter = "|"

    cells = []
    current = []
    bracket_depth = 0
    in_code = False
    index = 0
    while index < len(content):
        if in_code:
            if content.lower().startswith("{code}", index):
                current.append(content[index : index + len("{code}")])
                index += len("{code}")
                in_code = False
                continue
            current.append(content[index])
            index += 1
            continue

        code_open_match = _code_open_at(content, index)
        if code_open_match:
            current.append(code_open_match.group(0))
            index += len(code_open_match.group(0))
            in_code = True
            continue

        char = content[index]
        if char == "[":
            bracket_depth += 1
        elif char == "]" and bracket_depth:
            bracket_depth -= 1

        if bracket_depth == 0 and content.startswith(delimiter, index):
            cells.append("".join(current))
            current = []
            index += len(delimiter)
            continue

        current.append(char)
        index += 1

    cells.append("".join(current))
    return cells


def _find_inline_table_start(line: str, start: int) -> int | None:
    index = start
    while index < len(line):
        code_open = _code_open_at(line, index)
        if code_open:
            code_close = _code_close_match(line[index + code_open.end() :])
            if not code_close:
                return None
            index += code_open.end() + code_close.end()
            continue

        if line[index] == "[":
            closing_bracket = line.find("]", index + 1)
            if closing_bracket == -1:
                return None
            index = closing_bracket + 1
            continue

        if line[index] == "|" and not line.startswith("||", index):
            rows, _ = _parse_inline_table(line, index)
            if rows:
                return index

        index += 1
    return None


def _parse_inline_table(line: str, start: int) -> tuple[list[list[str]], int]:
    rows = []
    index = start
    while index < len(line):
        while index < len(line) and line[index].isspace():
            index += 1

        if index >= len(line) or line[index] != "|" or line.startswith("||", index):
            break

        row, row_end = _parse_inline_table_row(line, index)
        if not row:
            break

        rows.append(row)
        index = row_end

    return rows, index


def _parse_inline_table_row(line: str, start: int) -> tuple[list[str], int]:
    first_cell, first_end = _read_inline_table_cell(line, start + 1)
    if first_end is None:
        return [], start

    second_cell, second_end = _read_inline_table_cell(line, first_end + 1)
    if second_end is None:
        return [], start

    return [first_cell, second_cell], second_end + 1


def _read_inline_table_cell(line: str, start: int) -> tuple[str, int | None]:
    current = []
    bracket_depth = 0
    index = start
    while index < len(line):
        code_open = _code_open_at(line, index)
        if code_open:
            code_close = _code_close_match(line[index + code_open.end() :])
            if not code_close:
                current.append(line[index:])
                return "".join(current), len(line)
            code_end = index + code_open.end() + code_close.end()
            current.append(line[index:code_end])
            index = code_end
            continue

        char = line[index]
        if char == "[":
            bracket_depth += 1
        elif char == "]" and bracket_depth:
            bracket_depth -= 1

        if char == "|" and bracket_depth == 0:
            return "".join(current), index

        current.append(char)
        index += 1

    return "".join(current), None


def _format_inline(text: str) -> str:
    code_pattern = re.compile(r"\{code(?:\s*:[^}]*)?}(.*?)\{code}", re.IGNORECASE)
    parts = []
    cursor = 0
    for match in code_pattern.finditer(text):
        parts.append(_format_links(text[cursor : match.start()]))
        code = _restore_code_macro_newlines(match.group(1)).strip()
        parts.append(f'<code class="issue-comment-code">{_html(code)}</code>')
        cursor = match.end()
    parts.append(_format_links(text[cursor:]))
    return "".join(parts)


def _format_links(text: str) -> str:
    link_pattern = re.compile(
        r"\[([^\]|]+)\|(https?://[^\]\s]+)]|\[([^\]]+)]\((https?://[^)\s]+)\)"
    )
    parts = []
    cursor = 0
    for match in link_pattern.finditer(text):
        parts.append(_format_emphasis(text[cursor : match.start()]))
        label_text = match.group(1) or match.group(3)
        url_text = match.group(2) or match.group(4)
        label = _format_emphasis(label_text)
        url = _html_attr(url_text)
        parts.append(f'<a href="{url}">{label}</a>')
        cursor = match.end()
    parts.append(_format_emphasis(text[cursor:]))
    return "".join(parts)


def _format_emphasis(text: str) -> str:
    escaped = _html(text)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return re.sub(r"\*([^*]+)\*", r"<strong>\1</strong>", escaped)


def _code_open_match(line: str) -> re.Match[str] | None:
    return re.match(r"^\s*\{code(?:\s*:[^}]*)?}(.*)$", line, re.IGNORECASE)


def _code_close_match(line: str) -> re.Match[str] | None:
    return re.search(r"\{code}", line, re.IGNORECASE)


def _code_open_at(text: str, index: int) -> re.Match[str] | None:
    return re.match(r"\s*\{code(?:\s*:[^}]*)?}", text[index:], re.IGNORECASE)


def _preserve_code_macro_newlines(body: str) -> str:
    code_pattern = re.compile(
        r"\{code(?:\s*:[^}]*)?}.*?\{code}",
        re.IGNORECASE | re.DOTALL,
    )
    return code_pattern.sub(
        lambda match: (
            match.group(0)
            .replace("\r\n", "\n")
            .replace(
                "\n",
                COMMENT_CODE_NEWLINE,
            )
        ),
        body,
    )


def _restore_code_macro_newlines(value: str) -> str:
    return value.replace(COMMENT_CODE_NEWLINE, "\n")


def _html(value: object) -> str:
    return html.escape(str(value), quote=False)


def _html_attr(value: object) -> str:
    return html.escape(str(value), quote=True)
