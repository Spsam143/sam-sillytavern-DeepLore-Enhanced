import re

SENSITIVE_KEY_RE = re.compile(
    r'(api[_-]?key|apikey|access[_-]?token|secret|password|passwd|authorization|'
    r'auth[_-]?header|bearer|x[_-]?api[_-]?key|obsidianapikey|proxy[_-]?key|cookie|'
    r'session|refresh[_-]?token|oauth[_-]?token|private[_-]?key|client[_-]?id|'
    r'app[_-]?key|encryption[_-]?key|master[_-]?key|helicone[_-]?auth|cf[_-]?access|'
    r'credential|webhook)',
    re.IGNORECASE
)

class ScrubberContext:
    def __init__(self):
        self.ip = {}
        self.ipv6 = {}
        self.email = {}
        self.host = {}
        self.user_path = {}
        self.title = {}
        self.stats = {
            'ips': 0,
            'ipv6s': 0,
            'emails': 0,
            'hosts': 0,
            'userPaths': 0,
            'titles': 0,
            'bearerTokens': 0,
            'urlTokens': 0,
            'openaiKeys': 0,
            'longTokens': 0,
            'sensitiveFields': 0,
        }

def pseudonym(map_obj, real, prefix):
    p = map_obj.get(real)
    if not p:
        p = f"<{prefix}-{len(map_obj) + 1}>"
        map_obj[real] = p
    return p

def _bearer_fn(m, ctx):
    ctx.stats['bearerTokens'] += 1
    # m.group(1) is the "Bearer " part
    return f"{m.group(1)}<token>"

def _url_token_fn(m, ctx):
    ctx.stats['urlTokens'] += 1
    return f"{m.group(1)}<token>"

def _openai_key_fn(m, ctx):
    ctx.stats['openaiKeys'] += 1
    return "<openai-key>"

def _ipv4_fn(m, ctx):
    ctx.stats['ips'] += 1
    ip_str = m.group(0)

    port_match = re.search(r':(\d{1,5})$', ip_str)
    port = port_match.group(1) if port_match else None

    ip_part = re.sub(r':\d+$', '', ip_str)
    octets = ip_part.split('.')
    prefix = f"{octets[0]}.{octets[1]}"
    suffix = f"{octets[2]}.{octets[3]}"
    masked = pseudonym(ctx.ip, suffix, 'host')
    alias = f"{prefix}.{masked}"
    return f"{alias}:{port}" if port else alias

def _ipv6_fn(m, ctx):
    ctx.stats['ipv6s'] += 1
    return pseudonym(ctx.ipv6, m.group(0), 'ipv6')

def _email_fn(m, ctx):
    ctx.stats['emails'] += 1
    return pseudonym(ctx.email, m.group(0).lower(), 'email')

def _user_path_win_fn(m, ctx):
    ctx.stats['userPaths'] += 1
    prefix = m.group(1)
    name = m.group(2)
    return f"{prefix}{pseudonym(ctx.user_path, name.lower(), 'user')}"

def _user_path_unix_fn(m, ctx):
    ctx.stats['userPaths'] += 1
    prefix = m.group(1)
    name = m.group(2)
    return f"{prefix}{pseudonym(ctx.user_path, name.lower(), 'user')}"

def _host_fn(m, ctx):
    scheme = m.group(1)
    host = m.group(2)
    if host == 'localhost' or host.startswith('<ip'):
        return f"{scheme}{host}"
    ctx.stats['hosts'] += 1
    return f"{scheme}{pseudonym(ctx.host, host.lower(), 'host')}"

def _long_token_fn(m, ctx):
    ctx.stats['longTokens'] += 1
    return "<long-token>"

PATTERNS = [
    {
        're': re.compile(r'(Bearer\s+)[A-Za-z0-9._\-+/=]{8,}', re.IGNORECASE),
        'fn': _bearer_fn
    },
    {
        're': re.compile(r'([?&](?:key|token|access_token|api_key|auth|secret|password|jwt|bearer|authorization|oauth_token)=)[^&\s"\']+', re.IGNORECASE),
        'fn': _url_token_fn
    },
    {
        're': re.compile(r'\bsk[-_][A-Za-z0-9_\-]{20,}\b'),
        'fn': _openai_key_fn
    },
    {
        're': re.compile(r'\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)(?::(\d{1,5}))?\b'),
        'fn': _ipv4_fn
    },
    {
        're': re.compile(r'\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b'),
        'fn': _ipv6_fn
    },
    {
        're': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),
        'fn': _email_fn
    },
    {
        're': re.compile(r'([A-Za-z]:\\Users\\)([^\\\/\s"\']+)'),
        'fn': _user_path_win_fn
    },
    {
        're': re.compile(r'(\/(?:home|Users)\/)([^\/\s"\']+)'),
        'fn': _user_path_unix_fn
    },
    {
        're': re.compile(r'(https?:\/\/)([A-Za-z0-9][A-Za-z0-9.\-]*)(?=[/:?#]|$)'),
        'fn': _host_fn
    },
    {
        're': re.compile(r'\b[A-Za-z0-9_\-]{32,}\b'),
        'fn': _long_token_fn
    }
]

def scrub_string(s, ctx=None):
    if not isinstance(s, str) or not s:
        return s
    if ctx is None:
        ctx = ScrubberContext()

    try:
        out = s
        for pattern in PATTERNS:
            def repl(m, fn=pattern['fn']):
                return fn(m, ctx)
            out = pattern['re'].sub(repl, out)
        return out
    except Exception:
        return s

def scrub_deep(value, ctx=None, seen=None):
    if ctx is None:
        ctx = ScrubberContext()
    if seen is None:
        seen = set()

    try:
        if value is None:
            return value

        t = type(value)
        if t is str:
            return scrub_string(value, ctx)
        if t in (int, float, bool):
            return value

        if callable(value):
            return f"[fn {getattr(value, '__name__', 'anon')}]"

        if isinstance(value, Exception):
            return {
                '__type__': 'Error',
                'name': value.__class__.__name__,
                'message': scrub_string(str(value), ctx),
            }

        obj_id = id(value)
        if obj_id in seen:
            return '[circular]'

        seen.add(obj_id)

        if isinstance(value, list) or isinstance(value, tuple) or isinstance(value, set):
            # Tuples/sets will be converted to lists, which is typical for JSON/serialization
            return [scrub_deep(v, ctx, seen) for v in value]

        if isinstance(value, dict):
            out = {}
            for k, v in value.items():
                k_str = str(k)
                if SENSITIVE_KEY_RE.search(k_str):
                    ctx.stats['sensitiveFields'] += 1
                    out[k_str] = '<redacted>'
                else:
                    out[k_str] = scrub_deep(v, ctx, seen)
            return out

        # For object instances
        if hasattr(value, '__dict__'):
            out = {}
            for k, v in value.__dict__.items():
                if SENSITIVE_KEY_RE.search(k):
                    ctx.stats['sensitiveFields'] += 1
                    out[k] = '<redacted>'
                else:
                    out[k] = scrub_deep(v, ctx, seen)
            return out

        return value
    except Exception:
        return '[scrub failed]'
