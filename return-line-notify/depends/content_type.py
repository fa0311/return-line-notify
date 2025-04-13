from fastapi import Request


def parse_content_type_header(header: str) -> tuple[str, dict[str, str]]:
    parts = [part.strip() for part in header.split(";")]
    mime = parts[0]
    params = {}
    for param in parts[1:]:
        if "=" in param:
            k, v = param.split("=", 1)
            params[k.strip()] = v.strip()
    return mime, params


def content_type(request: Request) -> str:
    main, params = parse_content_type_header(request.headers["content-type"])
    return main
