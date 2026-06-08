import pytest
import time
import asyncio
from deeplore.db import VaultDB
from deeplore.bm25 import BM25Engine
from deeplore.sync import sync_vault

def generate_mock_data(num_entries=5000):
    files = []
    # Pre-generate some repeating words to make content realistic enough for BM25
    words = ["magic", "sword", "dragon", "knight", "castle", "forest", "king", "queen", "dark", "light"]

    for i in range(num_entries):
        # Determine content distribution to simulate real vault
        word_idx = i % len(words)
        content = f"""---
title: "Entry {i}"
keys: ["{words[word_idx]}", "test", "entry{i}"]
---
# Entry {i}
This is the content for entry {i}. It talks about a {words[word_idx]} and other things.
{" ".join([words[(i+j)%len(words)] for j in range(20)])}
"""
        files.append({
            'filename': f'entry_{i}.md',
            'content': content
        })
    return files

@pytest.mark.asyncio
async def test_db_benchmark():
    # Setup
    db = VaultDB(":memory:")
    await db.init_pool()
    mock_files = generate_mock_data(5000)

    # Simple sync function using dictionary lookup for O(1) reads
    mock_file_dict = {f['filename']: f['content'] for f in mock_files}
    def mock_read_file(filename):
        return mock_file_dict.get(filename, "")

    print(f"\n--- Benchmarking DB Insertion (5000 entries) ---")

    # Measure Sync/Insertion time
    start_time = time.time()
    stats = await sync_vault(db, mock_files, mock_read_file)
    insertion_time = time.time() - start_time

    print(f"Insertion Time: {insertion_time:.4f} seconds")
    print(f"Insertion Rate: {5000/insertion_time:.2f} entries/sec")
    assert stats['added'] == 5000

    # Test incremental sync
    print(f"\n--- Benchmarking DB Incremental Sync (5000 unchanged) ---")
    start_time = time.time()
    stats2 = await sync_vault(db, mock_files, mock_read_file)
    incremental_time = time.time() - start_time

    print(f"Incremental Sync Time: {incremental_time:.4f} seconds")
    assert stats2['unchanged'] == 5000
    assert stats2['added'] == 0

    # Load all entries for BM25
    start_time = time.time()
    entries = await db.get_all_entries()
    load_time = time.time() - start_time
    print(f"Load All Time: {load_time:.4f} seconds")

    # Benchmarking BM25
    print(f"\n--- Benchmarking BM25 Indexing (5000 entries) ---")
    engine = BM25Engine()

    start_time = time.time()
    engine.build_index(entries)
    index_time = time.time() - start_time

    print(f"BM25 Build Time: {index_time:.4f} seconds")

    print(f"\n--- Benchmarking BM25 Querying (1000 queries) ---")
    queries = ["magic sword", "dragon knight", "king castle", "dark forest", "light queen"] * 200

    start_time = time.time()
    for q in queries:
        engine.search(q, limit=10)
    query_time = time.time() - start_time

    print(f"Query Time (1000 queries): {query_time:.4f} seconds")
    print(f"Query Rate: {1000/query_time:.2f} queries/sec")

    await db.close()
