from compliance.access_control import has_permission_for_roles


def test_rbac_matrix_basic():
    assert has_permission_for_roles(["viewer"], "case:read")
    assert not has_permission_for_roles(["viewer"], "submit")
    assert has_permission_for_roles(["ops_submitter"], "submit")
    assert has_permission_for_roles(["admin"], "config:write")
