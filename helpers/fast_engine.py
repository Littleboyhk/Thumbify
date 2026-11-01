import os
import math
import asyncio
import functools
import inspect
from pathlib import Path
from hydrogram import raw, utils
from hydrogram.file_id import FileId, FileType, ThumbnailSource
from hydrogram.session import Session, Auth
from hydrogram.errors import AuthBytesInvalid

CHUNK_SIZE = 1024 * 1024  # 1 MB
CONCURRENT_DOWNLOAD_WORKERS = 6
CONCURRENT_UPLOAD_WORKERS = 8

async def get_media_session(client, dc_id: int):
    """Retrieve or create a media session for a given Telegram DC."""
    session = client.media_sessions.get(dc_id)
    if not session:
        auth_key = (
            await Auth(client, dc_id, await client.storage.test_mode()).create()
            if dc_id != await client.storage.dc_id()
            else await client.storage.auth_key()
        )
        session = client.media_sessions[dc_id] = Session(
            client, dc_id, auth_key, await client.storage.test_mode(), is_media=True
        )
        await session.start()

        if dc_id != await client.storage.dc_id():
            for _ in range(3):
                exported_auth = await client.invoke(
                    raw.functions.auth.ExportAuthorization(dc_id=dc_id)
                )
                try:
                    await session.invoke(
                        raw.functions.auth.ImportAuthorization(
                            id=exported_auth.id, bytes=exported_auth.bytes
                        )
                    )
                    break
                except AuthBytesInvalid:
                    continue
            else:
                raise AuthBytesInvalid
    return session

async def fast_download_media(
    client,
    message,
    file_name: str,
    progress=None,
    progress_args=()
) -> str | None:
    """
    Downloads media using concurrent parallel chunk requests for maximum speed.
    Falls back to client.download_media if file is small (< 10MB) or specialized (CDN).
    """
    media = message.document or message.video or message.audio
    if not media:
        return await client.download_media(message, file_name=file_name, progress=progress, progress_args=progress_args)

    file_size = getattr(media, "file_size", 0)
    # For small files, standard download is already instantaneous
    if file_size < 10 * 1024 * 1024:
        return await client.download_media(message, file_name=file_name, progress=progress, progress_args=progress_args)

    file_id_obj = FileId.decode(media.file_id)
    file_type = file_id_obj.file_type

    if file_type == FileType.PHOTO:
        location = raw.types.InputPhotoFileLocation(
            id=file_id_obj.media_id,
            access_hash=file_id_obj.access_hash,
            file_reference=file_id_obj.file_reference,
            thumb_size=file_id_obj.thumbnail_size,
        )
    else:
        location = raw.types.InputDocumentFileLocation(
            id=file_id_obj.media_id,
            access_hash=file_id_obj.access_hash,
            file_reference=file_id_obj.file_reference,
            thumb_size=file_id_obj.thumbnail_size,
        )

    dc_id = file_id_obj.dc_id
    try:
        session = await get_media_session(client, dc_id)
    except Exception:
        # Fallback to standard download if session initialization fails
        return await client.download_media(message, file_name=file_name, progress=progress, progress_args=progress_args)

    total_chunks = math.ceil(file_size / CHUNK_SIZE)
    temp_file_path = f"{file_name}.part"

    # Pre-allocate file on disk
    os.makedirs(os.path.dirname(file_name) or ".", exist_ok=True)
    with open(temp_file_path, "wb") as f:
        f.seek(file_size - 1)
        f.write(b"\0")

    file_lock = asyncio.Lock()
    downloaded_bytes = 0
    queue = asyncio.Queue()

    for i in range(total_chunks):
        queue.put_nowait(i)

    async def worker():
        nonlocal downloaded_bytes
        while not queue.empty():
            try:
                chunk_index = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            offset_bytes = chunk_index * CHUNK_SIZE
            try:
                r = await session.invoke(
                    raw.functions.upload.GetFile(
                        location=location,
                        offset=offset_bytes,
                        limit=CHUNK_SIZE
                    ),
                    sleep_threshold=30
                )
            except Exception:
                # Re-queue on failure and retry once
                await queue.put(chunk_index)
                await asyncio.sleep(1)
                continue

            if isinstance(r, raw.types.upload.File):
                chunk_data = r.bytes
                async with file_lock:
                    with open(temp_file_path, "r+b") as f:
                        f.seek(offset_bytes)
                        f.write(chunk_data)
                    downloaded_bytes += len(chunk_data)

                if progress:
                    try:
                        func = functools.partial(
                            progress,
                            min(downloaded_bytes, file_size),
                            file_size,
                            *progress_args,
                        )
                        if inspect.iscoroutinefunction(progress):
                            await func()
                        else:
                            await client.loop.run_in_executor(client.executor, func)
                    except Exception:
                        pass
            elif isinstance(r, raw.types.upload.FileCdnRedirect):
                # CDN files handled by standard downloader
                raise ValueError("CDN redirect encountered")

    # Launch parallel workers
    worker_count = min(CONCURRENT_DOWNLOAD_WORKERS, total_chunks)
    try:
        await asyncio.gather(*[worker() for _ in range(worker_count)])
    except Exception:
        # In case of any unexpected issues, clean temp and fallback to standard download
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except OSError:
                pass
        return await client.download_media(message, file_name=file_name, progress=progress, progress_args=progress_args)

    # Rename temp part file to final file name
    if os.path.exists(file_name):
        try:
            os.remove(file_name)
        except OSError:
            pass
    os.replace(temp_file_path, file_name)
    return file_name


def patch_hydrogram_upload():
    """
    Patches Hydrogram's Client.save_file to allow true parallel multi-worker uploads.
    Increases queue depth and worker count so parts upload concurrently.
    """
    from hydrogram.client import Client
    import io
    from pathlib import PurePath
    from hashlib import md5

    original_save_file = Client.save_file

    async def fast_save_file(
        self,
        path,
        file_id=None,
        file_part=0,
        progress=None,
        progress_args=(),
    ):
        async with self.save_file_semaphore:
            if path is None:
                return None

            queue = asyncio.Queue(16)

            async def worker(session):
                while True:
                    data = await queue.get()
                    if data is None:
                        return
                    try:
                        await session.invoke(data)
                    except Exception:
                        pass

            part_size = 512 * 1024

            if isinstance(path, (str, PurePath)):
                fp = Path(path).open("rb")
            elif isinstance(path, io.IOBase):
                fp = path
            else:
                raise ValueError("Invalid file. Expected a file path as string or a binary file pointer")

            fp.seek(0, io.SEEK_END)
            file_size = fp.tell()
            if file_size == 0:
                raise ValueError("File size equals to 0 B")

            file_name = getattr(fp, "name", "file.jpg")
            fp.seek(0)

            file_size_limit_mib = 4000 if getattr(getattr(self, "me", None), "is_premium", False) else 2000
            if file_size > file_size_limit_mib * 1024 * 1024:
                raise ValueError(f"Can't upload files bigger than {file_size_limit_mib} MiB")

            file_total_parts = int(math.ceil(file_size / part_size))
            is_big = file_size > 10 * 1024 * 1024
            workers_count = CONCURRENT_UPLOAD_WORKERS if is_big else 1
            is_missing_part = file_id is not None
            file_id = file_id or self.rnd_id()
            md5_sum = md5() if not is_big and not is_missing_part else None

            session = Session(
                self,
                await self.storage.dc_id(),
                await self.storage.auth_key(),
                await self.storage.test_mode(),
                is_media=True,
            )
            workers = [self.loop.create_task(worker(session)) for _ in range(workers_count)]

            try:
                await session.start()
                fp.seek(part_size * file_part)

                while True:
                    chunk = fp.read(part_size)
                    if not chunk:
                        if not is_big and not is_missing_part:
                            md5_sum = "".join([f"{i:x}".zfill(2) for i in md5_sum.digest()])
                        break

                    if is_big:
                        rpc = raw.functions.upload.SaveBigFilePart(
                            file_id=file_id,
                            file_part=file_part,
                            file_total_parts=file_total_parts,
                            bytes=chunk,
                        )
                    else:
                        rpc = raw.functions.upload.SaveFilePart(
                            file_id=file_id, file_part=file_part, bytes=chunk
                        )

                    await queue.put(rpc)

                    if is_missing_part:
                        return None

                    if not is_big and not is_missing_part:
                        md5_sum.update(chunk)

                    file_part += 1

                    if progress:
                        func = functools.partial(
                            progress,
                            min(file_part * part_size, file_size),
                            file_size,
                            *progress_args,
                        )
                        if inspect.iscoroutinefunction(progress):
                            await func()
                        else:
                            await self.loop.run_in_executor(self.executor, func)
            finally:
                for _ in workers:
                    await queue.put(None)
                await asyncio.gather(*workers)
                await session.stop()
                if isinstance(path, (str, PurePath)):
                    fp.close()

            if is_big:
                return raw.types.InputFileBig(
                    id=file_id,
                    parts=file_total_parts,
                    name=file_name,
                )
            return raw.types.InputFile(
                id=file_id,
                parts=file_total_parts,
                name=file_name,
                md5_checksum=md5_sum,
            )

    Client.save_file = fast_save_file

