import re

def escapeRegex(s: str) -> str:
    # JS escapeRegex might not escape space.
    # We will use re.escape but watch out for how JS does it if there are specific cases.
    # Common JS escapeRegex implementation:
    # return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return re.sub(r'([.*+?^${}()|\[\]\\])', r'\\\1', s)

def trackerKey(entry) -> str:
    vs = getattr(entry, 'vaultSource', '')
    if vs is None:
        vs = ''
    return f"{vs}:{entry.title}"
