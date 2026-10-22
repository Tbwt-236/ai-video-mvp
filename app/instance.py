"""One running studio per data directory, using OS locks released on process exit."""
import os
from pathlib import Path


class StudioInUse(RuntimeError):
    pass


class StudioLock:
    def __init__(self, directory):
        self.directory=Path(directory)
        self.handle=None

    def __enter__(self):
        self.directory.mkdir(parents=True,exist_ok=True)
        handle=(self.directory/".studio.lock").open("a+b")
        try:
            handle.seek(0)
            if os.name=="nt":
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(),fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise StudioInUse("这个作品目录已有工作台在运行，请使用原来的窗口；如需独立工作台，请设置不同的 VIDEO_DATA_DIR。") from exc
        self.handle=handle
        return self

    def __exit__(self,*args):
        handle,self.handle=self.handle,None
        if handle is None:return
        try:
            handle.seek(0)
            if os.name=="nt":
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(),fcntl.LOCK_UN)
        finally:
            handle.close()
