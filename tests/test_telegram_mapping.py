from enum import Enum
from types import SimpleNamespace as NS

from platforms.telegram.mapping import (
    admin_info_from,
    bot_status_from,
    chat_ref_from,
    member_status_from,
    status_value,
    user_ref_from,
)


class FakeStatus(str, Enum):
    CREATOR = "creator"
    ADMINISTRATOR = "administrator"
    MEMBER = "member"
    RESTRICTED = "restricted"
    LEFT = "left"
    KICKED = "kicked"


def _user(id=1, **kw):
    return NS(id=id, username=kw.get("username"), first_name=kw.get("first_name", "علی"),
              last_name=None, language_code="fa", is_bot=kw.get("is_bot", False))


def test_status_value_handles_enum_and_plain_string():
    assert status_value(NS(status=FakeStatus.MEMBER)) == "member"
    assert status_value(NS(status="left")) == "left"


def test_user_ref():
    ref = user_ref_from(_user(42, username="ali"))
    assert (ref.platform, ref.external_id, ref.username, ref.is_bot) == ("telegram", 42, "ali", False)


def test_chat_ref():
    chat = NS(id=-1001234, title="گروه", username=None, type=FakeStatus.MEMBER)
    ref = chat_ref_from(chat)
    assert (ref.platform, ref.external_id, ref.title) == ("telegram", -1001234, "گروه")


def test_admin_info_for_creator_has_all_permissions():
    info = admin_info_from(NS(status=FakeStatus.CREATOR, user=_user()))
    assert info.platform_role == "creator"
    assert info.permissions and all(info.permissions.values())


def test_admin_info_for_administrator_copies_flags():
    member = NS(status=FakeStatus.ADMINISTRATOR, user=_user(),
                can_delete_messages=True, can_restrict_members=False)
    info = admin_info_from(member)
    assert info.platform_role == "admin"
    assert info.permissions["can_delete_messages"] is True
    assert info.permissions["can_restrict_members"] is False
    assert info.permissions["can_pin_messages"] is False


def test_admin_info_for_plain_member_is_none():
    assert admin_info_from(NS(status=FakeStatus.MEMBER, user=_user())) is None


def test_bot_status_variants():
    assert bot_status_from(NS(status=FakeStatus.MEMBER)).missing_permissions == ("is_admin",)
    partial = bot_status_from(NS(status=FakeStatus.ADMINISTRATOR, can_delete_messages=True,
                                 can_restrict_members=False))
    assert partial.missing_permissions == ("can_restrict_members",)
    assert bot_status_from(NS(status=FakeStatus.CREATOR)).missing_permissions == ()


def test_member_status_mapping():
    for status, expected in [
        (FakeStatus.CREATOR, "member"),
        (FakeStatus.ADMINISTRATOR, "member"),
        (FakeStatus.MEMBER, "member"),
        (FakeStatus.LEFT, "left"),
        (FakeStatus.KICKED, "banned"),
    ]:
        assert member_status_from(NS(status=status)) == expected


def test_restricted_member_depends_on_is_member_flag():
    assert member_status_from(NS(status=FakeStatus.RESTRICTED, is_member=True)) == "member"
    assert member_status_from(NS(status=FakeStatus.RESTRICTED, is_member=False)) == "left"
