"""Who is allowed to do what. Two roles: Owner and Staff (Django groups)."""

OWNER_GROUP = "Owner"
STAFF_GROUP = "Staff"


def is_owner(user):
    """The owner can void payments and manage plans and staff accounts."""
    return user.is_superuser or user.groups.filter(name=OWNER_GROUP).exists()
