from ume.models.user_group import create_user_group
import uuid
import pytest


def test_create_user_group_generates_id_and_defaults_members():
    group = create_user_group(name="Admins")
    # Ensure generated ID is valid UUID
    uuid.UUID(group.group_id)
    assert group.name == "Admins"
    assert group.members == []


def test_create_user_group_accepts_members_and_id():
    members = ["alice", "bob"]
    custom_id = "custom-id"
    group = create_user_group(name="Team", members=members, group_id=custom_id)
    assert group.group_id == custom_id
    assert group.members == members


def test_create_user_group_invalid_uuid():
    group = create_user_group(name="Admins", group_id="not-a-uuid")
    with pytest.raises(ValueError):
        uuid.UUID(group.group_id)


def test_create_user_group_duplicate_id():
    custom_id = "dup-id"
    group1 = create_user_group(name="Group1", group_id=custom_id)
    group2 = create_user_group(name="Group2", group_id=custom_id)
    assert group1.group_id == group2.group_id == custom_id
    assert group1 is not group2
