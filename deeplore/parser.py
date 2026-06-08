import re
import yaml
import logging

logger = logging.getLogger(__name__)

def parse_vault_file(content: str) -> dict:
    """
    Parses a vault markdown file, extracting YAML frontmatter and body.
    Handles malformed YAML robustly.
    """
    result = {
        'frontmatter': {},
        'body': content,
        'title': '',
        'keys': []
    }

    # Strip BOM if present
    if content.startswith('\ufeff'):
        content = content[1:]

    # Match frontmatter: ^---\n(.*?)\n---\n(.*)
    # Using regex to separate frontmatter and body
    match = re.match(r'^---\r?\n(.*?)\r?\n---[ \t]*\r?\n?(.*)', content, re.DOTALL)

    if match:
        yaml_text = match.group(1)
        body = match.group(2)
        result['body'] = body

        try:
            # Parse YAML safely
            parsed_yaml = yaml.safe_load(yaml_text)
            if isinstance(parsed_yaml, dict):
                result['frontmatter'] = parsed_yaml

                # Extract common fields directly
                if 'title' in parsed_yaml:
                    result['title'] = str(parsed_yaml['title'])

                if 'keys' in parsed_yaml:
                    keys_data = parsed_yaml['keys']
                    if isinstance(keys_data, list):
                        result['keys'] = [str(k) for k in keys_data if k]
                    elif isinstance(keys_data, str):
                        result['keys'] = [k.strip() for k in keys_data.split(',') if k.strip()]
        except yaml.YAMLError as e:
            logger.warning(f"Malformed YAML frontmatter: {e}")
            # If YAML fails to parse entirely, we still have the body separated
            # Could attempt a manual fallback parser here if needed for specific cases

    # Try to extract title from H1 if not in frontmatter
    if not result['title']:
        h1_match = re.search(r'^#\s+(.+)$', result['body'], re.MULTILINE)
        if h1_match:
            result['title'] = h1_match.group(1).strip()

    return result
