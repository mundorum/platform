from rest_framework import serializers

from .models import Scene, SceneRun


class SceneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Scene
        fields = ['id', 'title', 'spec', 'package_dir', 'created_at', 'updated_at']
        read_only_fields = ['id', 'package_dir', 'created_at', 'updated_at']


class SceneRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = SceneRun
        fields = [
            'id', 'scene', 'status', 'output', 'returncode',
            'started_at', 'finished_at', 'created_at',
        ]
        read_only_fields = fields
