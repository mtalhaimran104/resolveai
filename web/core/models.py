"""
Building blocks that every other ResolveAI app reuses.

Nothing here creates a table. `TimeStampedModel` is an *abstract* model:
Django copies its fields into any model that inherits from it instead of
creating a `core_timestampedmodel` table of its own.

Almost every table in the ResolveAI schema needs `created_at` and
`updated_at`, so they are defined once here rather than copy-pasted into
each model.
"""

from django.db import models


class TimeStampedModel(models.Model):
    """Adds `created_at` / `updated_at` columns to a model.

    - `auto_now_add=True` sets the value once, when the row is inserted.
    - `auto_now=True` overwrites the value on every `save()`.

    Note: both are applied by the Django ORM, not by MySQL. Rows written by
    raw SQL (or by a bulk update) will not get them, which is fine for this
    project because Django owns all writes.
    """

    created_at = models.DateTimeField(auto_now_add=True, db_comment="Row creation time")
    updated_at = models.DateTimeField(auto_now=True, db_comment="Last modification time")

    class Meta:
        abstract = True
