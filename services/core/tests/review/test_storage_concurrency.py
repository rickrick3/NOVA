"""Blob reference counts must survive interleaved writers; collection must spare fresh files."""

from nova_core.storage.models import Blob
from nova_core.storage.service import BlobService


def service(session, settings, clock) -> BlobService:
    return BlobService(session, settings.data_dir / "blobs", clock, settings.max_blob_bytes)


async def test_interleaved_puts_do_not_lose_a_reference(app, settings, clock):
    factory = app.state.session_factory
    async with factory() as first:
        ref = await service(first, settings, clock).put(b"shared", "text/plain")
        await first.commit()

    async with factory() as one, factory() as two:
        # Both sessions read the row before either writes. The rows are kept referenced:
        # a session only remembers objects that something else still holds.
        stale = [await one.get(Blob, ref.sha256), await two.get(Blob, ref.sha256)]
        assert [row.ref_count for row in stale] == [1, 1]
        await service(one, settings, clock).put(b"shared", "text/plain")
        await one.commit()
        await service(two, settings, clock).put(b"shared", "text/plain")
        await two.commit()

    async with factory() as check:
        assert (await check.get(Blob, ref.sha256)).ref_count == 3


async def test_interleaved_releases_do_not_resurrect_a_reference(app, settings, clock):
    factory = app.state.session_factory
    async with factory() as first:
        blobs = service(first, settings, clock)
        ref = await blobs.put(b"shared", "text/plain")
        await blobs.put(b"shared", "text/plain")
        await blobs.put(b"shared", "text/plain")
        await first.commit()

    async with factory() as one, factory() as two:
        stale = [await one.get(Blob, ref.sha256), await two.get(Blob, ref.sha256)]
        assert [row.ref_count for row in stale] == [3, 3]
        await service(one, settings, clock).release(ref.sha256)
        await one.commit()
        await service(two, settings, clock).release(ref.sha256)
        await two.commit()

    async with factory() as check:
        assert (await check.get(Blob, ref.sha256)).ref_count == 1


async def test_collection_spares_files_younger_than_the_grace_period(session, settings, clock):
    blobs = service(session, settings, clock)
    await blobs.put(b"being written by another process", "text/plain")
    await session.rollback()
    assert await blobs.collect_garbage(min_age_seconds=300) == 0
    assert len([p for p in blobs.root.rglob("*") if p.is_file()]) == 1
    assert await blobs.collect_garbage() == 1
