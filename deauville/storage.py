import json
import os
import sys
import tempfile
from pathlib import Path

from deauville.errors import FestivalError, StorageError
from deauville.festival import Festival

ROOT = Path(__file__).resolve().parent.parent
if not (ROOT / "web").is_dir():
    ROOT = Path(sys.prefix) / "share" / "deauville"
DEFAULT_DATA = ROOT / "data" / "festival.json"


class JsonStorage:
    def __init__(self, path: str | Path = DEFAULT_DATA):
        self.path = Path(path)

    def load(self) -> Festival:
        try:
            with self.path.open(encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, ValueError) as error:
            raise StorageError(
                f"Cannot read festival data from {self.path}: {error}"
            ) from None
        try:
            return Festival.from_dict(data)
        except FestivalError as error:
            raise StorageError(
                f"Invalid festival data in {self.path}: {error}"
            ) from None

    def save(self, festival: Festival) -> None:
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent, delete=False
            ) as file:
                temporary = Path(file.name)
                json.dump(festival.to_dict(), file, ensure_ascii=False, indent=2)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            temporary.replace(self.path)
        except OSError as error:
            raise StorageError(
                f"Cannot save festival data to {self.path}: {error}"
            ) from None
        finally:
            if temporary is not None and temporary.exists():
                try:
                    temporary.unlink()
                except OSError:
                    pass
