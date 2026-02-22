import re
from bs4 import BeautifulSoup

def robust_sanitize_confluence_xhtml(body: str) -> str:
    if not body:
        return body
    body = re.sub(r'<ac:structured-macro ac:name="invalidmacro"[^>]*/>', '', body)
    body = re.sub(r'<ac:structured-macro ac:name="invalidmacro"[^>]*>.*?</ac:structured-macro>', '', body, flags=re.DOTALL)
    body = re.sub(r'^<result>(.*?)</result>$', r'\1', body.strip(), flags=re.DOTALL)
    body = re.sub(r'<ac:parameter>(.*?)</ac:parameter>', r'<ac:parameter ac:name="language">\1</ac:parameter>', body)
    
    def repair_macro(match):
        start_tag = match.group(1)
        inner_content = match.group(2)
        end_tag = match.group(3)
        if 'ac:name=' in start_tag:
            return match.group(0)
        if '<ac:plain-text-body' in inner_content:
            new_start = start_tag.replace('<ac:structured-macro', '<ac:structured-macro ac:name="code"')
        elif '<ac:rich-text-body' in inner_content:
            new_start = start_tag.replace('<ac:structured-macro', '<ac:structured-macro ac:name="info"')
        else:
            new_start = start_tag.replace('<ac:structured-macro', '<ac:structured-macro ac:name="info"')
        return f"{new_start}{inner_content}{end_tag}"

    modified = True
    while modified:
        new_body = re.sub(r'(<ac:structured-macro(?![^>]*ac:name=)[^>]*>)(.*?)(</ac:structured-macro>)', repair_macro, body, flags=re.DOTALL)
        if new_body == body:
            modified = False
        body = new_body
    return body

def clean_html(html_content: str) -> str:
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    for script_or_style in soup(["script", "style"]):
        script_or_style.decompose()
    return soup.get_text(separator="\n").strip()

# Test with CDATA
body = '<li>Update: <ac:structured-macro ac:name="code"><ac:plain-text-body><![CDATA[sudo apt update]]></ac:plain-text-body></ac:structured-macro></li>'
sanitized = robust_sanitize_confluence_xhtml(body)
text = clean_html(sanitized)

print('ORIGINAL:', body)
print('CLEAN TEXT:', text)
