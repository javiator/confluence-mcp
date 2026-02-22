import re

def robust_sanitize_confluence_xhtml(body: str) -> str:
    if not body:
        return body

    # Fix 0: Strip Confluence-generated 'invalidmacro' placeholders COMPLETELY
    body = re.sub(
        r'<ac:structured-macro ac:name="invalidmacro"[^>]*/>',
        '',
        body
    )
    body = re.sub(
        r'<ac:structured-macro ac:name="invalidmacro"[^>]*>.*?</ac:structured-macro>',
        '',
        body,
        flags=re.DOTALL
    )

    # Fix 0.5: Strip <result> tags if the LLM wrapped the whole thing
    body = re.sub(r'^<result>(.*?)</result>$', r'\1', body.strip(), flags=re.DOTALL)

    # Fix 1: <ac:parameter> missing ac:name
    body = re.sub(
        r'<ac:parameter>(.*?)</ac:parameter>',
        r'<ac:parameter ac:name="language">\1</ac:parameter>',
        body
    )

    # Fix 2: <ac:structured-macro> missing ac:name
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
        new_body = re.sub(
            r'(<ac:structured-macro(?![^>]*ac:name=)[^>]*>)(.*?)(</ac:structured-macro>)',
            repair_macro,
            body,
            flags=re.DOTALL
        )
        if new_body == body:
            modified = False
        body = new_body

    return body

# Input from the logs
log_input = '<result><ac:structured-macro><ac:parameter>bash</ac:parameter><ac:plain-text-body>\nsudo docker stop $(sudo docker ps -a -q)\nsudo docker rm $(sudo docker ps -a -q)\n</ac:plain-text-body></ac:structured-macro></result>'

output = robust_sanitize_confluence_xhtml(log_input)
print("OUTPUT:")
print(output)
