import hashlib

import pytest

from nova_core.storage.models import Blob
from nova_core.storage.service import BlobNotFoundError, BlobService, BlobTooLargeError


@pytest.fixture
def blobs(session, settings, clock) -> BlobService:
    return BlobService(session, settings.data_dir / "blobs", clock, settings.max_blob_bytes)


def stored_files(service: BlobService) -> list:
    return [p for p in service.root.rglob("*") if p.is_file()]


async def test_same_content_is_stored_once_and_counted_twice(blobs, session):
    a = await blobs.put(b"hello", "text/plain")
    b = await blobs.put(b"hello", "text/plain")
    await session.commit()
    assert a.sha256 == b.sha256 == hashlib.sha256(b"hello").hexdigest()
    assert (a.size, a.media_type) == (5, "text/plain")
    assert len(stored_files(blobs)) == 1
    assert (await session.get(Blob, a.sha256)).ref_count == 2


async def test_open_returns_the_stored_bytes(blobs, session):
    ref = await blobs.put(b"hello", "text/plain")
    await session.commit()
    assert await blobs.open(ref.sha256) == b"hello"


async def test_file_disappears_only_when_the_last_reference_is_released(blobs, session):
    ref = await blobs.put(b"hello", "text/plain")
    await blobs.put(b"hello", "text/plain")
    await blobs.release(ref.sha256)
    await session.commit()
    assert await blobs.collect_garbage() == 0
    assert len(stored_files(blobs)) == 1

    await blobs.release(ref.sha256)
    await session.commit()
    assert await blobs.collect_garbage() == 1
    assert stored_files(blobs) == []
    assert await session.get(Blob, ref.sha256) is None


async def test_rolled_back_put_leaves_no_row_and_its_file_is_collected(blobs, session):
    ref = await blobs.put(b"orphan", "text/plain")
    await session.rollback()
    assert await session.get(Blob, ref.sha256) is None
    assert await blobs.collect_garbage() == 1


async def test_unknown_blob_is_reported(blobs):
    missing = "0" * 64
    with pytest.raises(BlobNotFoundError):
        await blobs.open(missing)
    with pytest.raises(BlobNotFoundError):
        await blobs.release(missing)


@pytest.mark.parametrize("key", ["../../etc/passwd", "ABC", "g" * 64, "A" * 64])
async def test_malformed_keys_are_rejected_before_touching_the_disk(blobs, key):
    with pytest.raises(ValueError):
        await blobs.open(key)


async def test_oversized_content_is_refused_and_nothing_is_written(session, settings, clock):
    small = BlobService(session, settings.data_dir / "blobs", clock, max_bytes=4)
    with pytest.raises(BlobTooLargeError):
        await small.put(b"12345", "text/plain")
    assert stored_files(small) == []
