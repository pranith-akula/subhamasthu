"""
Tests for UserService.
"""

import pytest
import uuid
from unittest.mock import AsyncMock, patch
from sqlalchemy import select

from app.models.user import User
from app.services.user_service import UserService
from app.fsm.states import ConversationState


@pytest.mark.asyncio
async def test_get_or_create_user_new(db):
    """Test creating a new user."""
    service = UserService(db)
    phone = "919999999999"
    name = "Test User"
    
    user = await service.get_or_create_user(phone, name)
    
    assert user.id is not None
    assert user.phone == phone
    assert user.name == name
    assert user.state == ConversationState.NEW.value
    
    # Verify in DB
    result = await db.execute(select(User).where(User.phone == phone))
    db_user = result.scalar_one()
    assert db_user.id == user.id


@pytest.mark.asyncio
async def test_get_or_create_user_existing(db):
    """Test retrieving an existing user."""
    service = UserService(db)
    phone = "918888888888"
    
    # Create first
    created = await service.get_or_create_user(phone)
    created_id = created.id
    
    # Retrieve
    retrieved = await service.get_or_create_user(phone)
    
    assert retrieved.id == created_id


@pytest.mark.asyncio
async def test_is_duplicate_message_redis_hit(db):
    """Test duplicate check when Redis has key."""
    service = UserService(db)
    user_id = uuid.uuid4()
    msg_id = "msg_123"
    
    # Mock Redis
    mock_redis = AsyncMock()
    mock_redis.exists.return_value = True
    
    with patch("app.redis.RedisClient.get_client", return_value=mock_redis):
        # We also need to patch get_redis wrapper if used, 
        # but UserService imports it inside function.
        # Ideally we patch where it is defined.
        with patch("app.redis.get_redis", new=AsyncMock(return_value=mock_redis)):
            is_dup = await service.is_duplicate_message(user_id, msg_id)
            
    assert is_dup is True
    mock_redis.exists.assert_called_once()


@pytest.mark.asyncio
async def test_is_duplicate_message_redis_miss(db):
    """Test duplicate check when Redis misses."""
    service = UserService(db)
    user_id = uuid.uuid4()
    msg_id = "msg_456"
    
    # Needs a user in DB for Conversation logic
    user = User(id=user_id, phone="123", state="NEW")
    db.add(user)
    # create conversation
    from app.models.conversation import Conversation
    conv = Conversation(user_id=user_id)
    db.add(conv)
    await db.commit()
    
    # Mock Redis
    mock_redis = AsyncMock()
    mock_redis.exists.return_value = False
    
    with patch("app.redis.get_redis", new=AsyncMock(return_value=mock_redis)):
        is_dup = await service.is_duplicate_message(user_id, msg_id)
        
    assert is_dup is False
    mock_redis.setex.assert_called_once()  # Should set cache
    
    # Verify DB updated
    result = await db.execute(select(Conversation).where(Conversation.user_id == user_id))
    updated_conv = result.scalar_one()
    assert updated_conv.last_inbound_msg_id == msg_id
