from rest_framework import serializers

from .models import Resource


class ResourceSerializer(serializers.ModelSerializer):
    address = serializers.ReadOnlyField()
    size_human = serializers.SerializerMethodField()

    class Meta:
        model = Resource
        fields = [
            'id', 'slug', 'slug_aliases', 'extension', 'address',
            'scope', 'scene',
            'display_name', 'description', 'resource_type', 'tags', 'mime_type',
            'size_bytes', 'size_human', 'sha256',
            'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'address', 'mime_type', 'size_bytes', 'sha256',
            'created_by', 'created_at', 'updated_at',
        ]

    def get_size_human(self, obj) -> str:
        n = obj.size_bytes
        for unit in ('B', 'KB', 'MB', 'GB'):
            if n < 1024:
                return f'{n:.0f} {unit}'
            n /= 1024
        return f'{n:.1f} TB'
