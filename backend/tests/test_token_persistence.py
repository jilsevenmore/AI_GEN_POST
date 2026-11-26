import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime, timezone

from app.services.publisher import BufferPublisher, persist_refreshed_channel_tokens


@pytest.mark.asyncio
async def test_persist_refreshed_channel_tokens_matches_decrypted_siblings(monkeypatch):
    from cryptography.fernet import Fernet
    from app.services import publisher as publisher_module

    pub = BufferPublisher(encryption_key=Fernet.generate_key())
    monkeypatch.setattr(publisher_module, "get_publisher", lambda: pub)

    company_id = uuid4()
    old_plain = "buffer_old_access_token"
    new_plain = "buffer_new_access_token"

    # Fernet produces different ciphertexts for the same plaintext token
    fb_old_enc = pub._encrypt(old_plain)
    ig_old_enc = pub._encrypt(old_plain)
    assert fb_old_enc != ig_old_enc

    fb_new_enc = pub._encrypt(new_plain)
    new_refresh_enc = pub._encrypt("buffer_new_refresh")

    fb_channel = SimpleNamespace(
        id=uuid4(),
        company_id=company_id,
        access_token_encrypted=fb_new_enc,
        refresh_token_encrypted=new_refresh_enc,
        token_expires_at=datetime.now(timezone.utc),
    )
    ig_channel = SimpleNamespace(
        id=uuid4(),
        company_id=company_id,
        access_token_encrypted=ig_old_enc,
        refresh_token_encrypted=pub._encrypt("old_refresh"),
        token_expires_at=datetime.now(timezone.utc),
    )

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [fb_channel, ig_channel]
    mock_select_result = MagicMock()
    mock_select_result.scalars.return_value = mock_scalars

    mock_db = AsyncMock()
    mock_db.execute.side_effect = [mock_select_result, MagicMock()]

    await persist_refreshed_channel_tokens(mock_db, fb_channel, fb_old_enc)

    assert mock_db.execute.call_count == 2
    update_stmt = mock_db.execute.call_args_list[1].args[0]
    compiled_params = update_stmt.compile().params
    # Both fb_channel.id and ig_channel.id must be included in the WHERE IN clause
    in_ids = next(v for v in compiled_params.values() if isinstance(v, (list, tuple)))
    assert set(in_ids) == {fb_channel.id, ig_channel.id}
