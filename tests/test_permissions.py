from core.enums import HelliRole, PlatformRole
from core.permissions import (
    ROLE_RANK,
    Permission,
    derive_role,
    is_global_owner,
    role_has_permission,
)


def test_derive_role_from_platform_role():
    assert derive_role(PlatformRole.CREATOR.value) is HelliRole.OWNER
    assert derive_role(PlatformRole.ADMIN.value) is HelliRole.ADMIN


def test_no_role_has_no_permission():
    for permission in Permission:
        assert not role_has_permission(None, permission)


def test_moderator_can_moderate_but_not_manage():
    assert role_has_permission(HelliRole.MODERATOR, Permission.MODERATE_USERS)
    assert not role_has_permission(HelliRole.MODERATOR, Permission.MANAGE_SETTINGS)
    assert not role_has_permission(HelliRole.MODERATOR, Permission.MANAGE_ROLES)


def test_admin_cannot_manage_roles_but_owner_can():
    assert role_has_permission(HelliRole.ADMIN, Permission.MANAGE_SETTINGS)
    assert not role_has_permission(HelliRole.ADMIN, Permission.MANAGE_ROLES)
    assert role_has_permission(HelliRole.OWNER, Permission.MANAGE_ROLES)


def test_role_rank_order():
    assert ROLE_RANK[HelliRole.MODERATOR] < ROLE_RANK[HelliRole.ADMIN] < ROLE_RANK[HelliRole.OWNER]


def test_global_owner():
    assert is_global_owner(5, {5, 6})
    assert not is_global_owner(7, {5, 6})
    assert not is_global_owner(7, frozenset())
