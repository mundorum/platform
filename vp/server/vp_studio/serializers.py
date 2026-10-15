from rest_framework import serializers

from . import casedoc
from .models import Case


class CaseListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Case
        fields = ('id', 'title', 'revision', 'status', 'published_revision', 'updated_at')


class CaseSerializer(serializers.ModelSerializer):
    # Sent back on update: the revision the editor started from. A mismatch
    # means the case was saved elsewhere in the meantime (409, see views).
    base_revision = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = Case
        fields = ('id', 'title', 'document', 'revision', 'base_revision', 'status',
                  'published_revision', 'published_at', 'created_at', 'updated_at')
        read_only_fields = ('title', 'revision', 'published_revision', 'published_at',
                            'created_at', 'updated_at')

    def validate_document(self, value):
        try:
            casedoc.validate_document(value)
        except casedoc.DocumentError as exc:
            raise serializers.ValidationError(str(exc))
        return value
