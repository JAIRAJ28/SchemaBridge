import asyncio
from pathlib import Path


class LocalStorage:
    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    async def save(self, *, object_key: str, content: bytes) -> str:
        safe_name = Path(object_key).name
        path = self.root / safe_name
        await asyncio.to_thread(path.write_bytes, content)
        return safe_name

    async def read(self, object_key: str) -> bytes:
        path = self.root / Path(object_key).name
        return await asyncio.to_thread(path.read_bytes)
