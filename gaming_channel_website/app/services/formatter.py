import re
import html

def format_post_content(raw_text: str) -> str:
    """Safely converts markdown-like text to sanitized semantic HTML."""
    if not raw_text:
        return ""

    # Escape HTML to prevent XSS injection
    safe_text = html.escape(raw_text)

    # Process block by block
    lines = safe_text.splitlines()
    html_lines = []
    in_list = False

    for line in lines:
        stripped = line.strip()
        
        # Unordered list item
        if stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            item_content = stripped[2:]
            item_content = parse_inline_markdown(item_content)
            html_lines.append(f"<li>{item_content}</li>")
            continue
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False

        if not stripped:
            continue

        # Headings
        if stripped.startswith("### "):
            header_text = parse_inline_markdown(stripped[4:])
            html_lines.append(f"<h3>{header_text}</h3>")
        elif stripped.startswith("## "):
            header_text = parse_inline_markdown(stripped[3:])
            html_lines.append(f"<h2>{header_text}</h2>")
        elif stripped.startswith("# "):
            header_text = parse_inline_markdown(stripped[2:])
            html_lines.append(f"<h2>{header_text}</h2>")
        # Blockquote
        elif stripped.startswith("&gt; "):
            quote_text = parse_inline_markdown(stripped[5:])
            html_lines.append(f"<blockquote><p>{quote_text}</p></blockquote>")
        # Standard paragraph
        else:
            para_text = parse_inline_markdown(stripped)
            html_lines.append(f"<p>{para_text}</p>")

    if in_list:
        html_lines.append("</ul>")

    return "\n".join(html_lines)

def parse_inline_markdown(text: str) -> str:
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    def link_repl(match):
        label = match.group(1)
        url = match.group(2).strip()
        if url.startswith("http://") or url.startswith("https://") or url.startswith("/"):
            return f'<a href="{url}" target="_blank" rel="noopener noreferrer">{label}</a>'
        return label
    text = re.sub(r'\[(.*?)\]\((.*?)\)', link_repl, text)
    return text
