from rest_framework import serializers

from .models import Scene, SceneRun


class SceneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Scene
        fields = ['id', 'title', 'spec', 'package_dir', 'created_at', 'updated_at']
        read_only_fields = ['id', 'package_dir', 'created_at', 'updated_at']


class SceneRunSerializer(serializers.ModelSerializer):
    scene_title = serializers.SerializerMethodField()

    def get_scene_title(self, obj):
        if obj.scene_id:
            return obj.scene.title
        return obj.scratch_title or '(scratch run)'

    class Meta:
        model = SceneRun
        fields = [
            'id', 'run_id', 'scene', 'scene_title', 'status', 'output',
            'returncode', 'started_at', 'finished_at', 'dismissed_at', 'created_at',
        ]
        read_only_fields = fields
