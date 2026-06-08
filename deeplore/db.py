import aiosqlite
import asyncio
import json
import logging
import sqlite3

logger = logging.getLogger(__name__)

class VaultDB:
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._pool = []
        self._pool_size = 5
        self._lock = asyncio.Lock()

    async def init_pool(self):
        async with self._lock:
            for _ in range(self._pool_size):
                conn = await self._create_connection()
                self._pool.append(conn)

    async def _create_connection(self):
        conn = await aiosqlite.connect(self.db_path)
        # Performance pragmas
        await conn.execute("PRAGMA journal_mode=WAL;")
        await conn.execute("PRAGMA synchronous=NORMAL;")
        await conn.execute("PRAGMA cache_size=-64000;") # 64MB cache
        await conn.execute("PRAGMA temp_store=MEMORY;")

        # Initialize schema
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                title TEXT,
                keys TEXT,
                content TEXT,
                hash TEXT NOT NULL,
                metadata TEXT,
                last_updated REAL
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_entries_filename ON entries (filename);")
        await conn.commit()
        return conn

    async def get_connection(self):
        async with self._lock:
            if self._pool:
                return self._pool.pop()
            return await self._create_connection()

    async def release_connection(self, conn):
        async with self._lock:
            if len(self._pool) < self._pool_size:
                self._pool.append(conn)
            else:
                await conn.close()

    async def close(self):
        async with self._lock:
            for conn in self._pool:
                await conn.close()
            self._pool.clear()

    async def get_entry_hash(self, filename: str) -> str:
        conn = await self.get_connection()
        try:
            async with conn.execute("SELECT hash FROM entries WHERE filename = ?", (filename,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None
        finally:
            await self.release_connection(conn)

    async def get_all_hashes(self) -> dict:
        conn = await self.get_connection()
        hashes = {}
        try:
            async with conn.execute("SELECT filename, hash FROM entries") as cursor:
                async for row in cursor:
                    hashes[row[0]] = row[1]
            return hashes
        finally:
            await self.release_connection(conn)

    async def upsert_entries(self, entries: list):
        conn = await self.get_connection()
        try:
            await conn.execute("BEGIN TRANSACTION")
            await conn.executemany("""
                INSERT INTO entries (id, filename, title, keys, content, hash, metadata, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    filename=excluded.filename,
                    title=excluded.title,
                    keys=excluded.keys,
                    content=excluded.content,
                    hash=excluded.hash,
                    metadata=excluded.metadata,
                    last_updated=excluded.last_updated
            """, [
                (
                    e['id'],
                    e['filename'],
                    e.get('title', ''),
                    json.dumps(e.get('keys', [])),
                    e.get('content', ''),
                    e['hash'],
                    json.dumps(e.get('metadata', {})),
                    e.get('last_updated', 0)
                ) for e in entries
            ])
            await conn.commit()
        except Exception as e:
            await conn.rollback()
            logger.error(f"Error upserting entries: {e}")
            raise
        finally:
            await self.release_connection(conn)

    async def delete_entries(self, filenames: list):
        if not filenames:
            return
        conn = await self.get_connection()
        try:
            await conn.execute("BEGIN TRANSACTION")
            # Chunking for SQLite limits if necessary, but ok for now
            placeholders = ",".join("?" for _ in filenames)
            await conn.execute(f"DELETE FROM entries WHERE filename IN ({placeholders})", filenames)
            await conn.commit()
        except Exception as e:
            await conn.rollback()
            logger.error(f"Error deleting entries: {e}")
            raise
        finally:
            await self.release_connection(conn)

    async def get_all_entries(self) -> list:
        conn = await self.get_connection()
        try:
            async with conn.execute("SELECT id, filename, title, keys, content, hash, metadata, last_updated FROM entries") as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        'id': row[0],
                        'filename': row[1],
                        'title': row[2],
                        'keys': json.loads(row[3]) if row[3] else [],
                        'content': row[4],
                        'hash': row[5],
                        'metadata': json.loads(row[6]) if row[6] else {},
                        'last_updated': row[7]
                    }
                    for row in rows
                ]
        finally:
            await self.release_connection(conn)
