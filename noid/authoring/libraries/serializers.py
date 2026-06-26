from rest_framework import serializers

from .models import ComponentCollection


class ComponentCollectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComponentCollection
        fields = ['id', 'name', 'pip_package', 'modules', 'enabled', 'description', 'updated_at']
        read_only_fields = ['id', 'updated_at']
