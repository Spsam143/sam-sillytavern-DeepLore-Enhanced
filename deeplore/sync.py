import hashlib
import time
import logging
import asyncio
from typing import List, Dict, Any, Callable
from .db import VaultDB
# Import deferred to avoid circular dependency / missing module during sync setup
# from .parser import parse_vault_file

logger = logging.getLogger(__name__)

async def sync_vault(
    db: VaultDB,
    files: List[Dict[str, Any]],
    read_file_func: Callable[[str], str]
) -> Dict[str, Any]:
    """
    Incrementally syncs the vault by hashing files and only updating modified ones.

    Args:
        db: VaultDB instance.
        files: List of dicts with 'filename' and 'mtime' (or just content to hash if mtime unreliable).
        read_file_func: Async or sync function to read file content given a filename.

    Returns:
        Dict with stats about the sync process.
    """
    from .parser import parse_vault_file

    start_time = time.time()
    stats = {
        "added": 0,
        "updated": 0,
        "deleted": 0,
        "unchanged": 0,
        "failed": 0
    }

    # Get existing hashes from DB
    existing_hashes = await db.get_all_hashes()

    current_filenames = set()
    entries_to_upsert = []

    for file_info in files:
        filename = file_info['filename']
        current_filenames.add(filename)

        try:
            # Handle both async and sync read_file_func
            if asyncio.iscoroutinefunction(read_file_func):
                content = await read_file_func(filename)
            else:
                content = read_file_func(filename)

            # Calculate SHA256 hash of the content
            file_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

            # Check if file has changed
            if filename in existing_hashes and existing_hashes[filename] == file_hash:
                stats["unchanged"] += 1
                continue

            # File is new or changed, parse it
            parsed_data = parse_vault_file(content)

            # Create entry for DB
            entry = {
                'id': f"vault:{filename}", # Unique ID
                'filename': filename,
                'title': parsed_data.get('title', filename.split('/')[-1].replace('.md', '')),
                'keys': parsed_data.get('keys', []),
                'content': parsed_data.get('body', ''),
                'hash': file_hash,
                'metadata': parsed_data.get('frontmatter', {}),
                'last_updated': time.time()
            }

            entries_to_upsert.append(entry)

            if filename in existing_hashes:
                stats["updated"] += 1
            else:
                stats["added"] += 1

        except Exception as e:
            logger.error(f"Error processing file {filename}: {e}")
            stats["failed"] += 1

    # Process deletions (files in DB but not in current file list)
    deleted_filenames = list(set(existing_hashes.keys()) - current_filenames)
    if deleted_filenames:
        await db.delete_entries(deleted_filenames)
        stats["deleted"] = len(deleted_filenames)

    # Upsert new/modified entries
    if entries_to_upsert:
        # We can chunk this if needed, but aiosqlite executemany handles large lists well
        await db.upsert_entries(entries_to_upsert)

    stats["duration_ms"] = (time.time() - start_time) * 1000
    return stats
