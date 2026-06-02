"""Project serializer.

Note what is **not** writable: ``organization`` is never accepted from the
client (it's stamped server-side from the active org), and ``created_by`` is set
to the requesting user. This is half of the isolation invariant — the client
cannot choose which tenant a project belongs to.
"""

from __future__ import annotations

from rest_framework import serializers

from projects.models import Project


class ProjectSerializer(serializers.ModelSerializer):
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Project
        fields = ["id", "name", "description", "created_by", "created_at"]
        read_only_fields = ["id", "created_by", "created_at"]
