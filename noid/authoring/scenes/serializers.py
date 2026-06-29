from rest_framework import serializers

from .models import Scene, SceneRun


class SceneSerializer(serializers.ModelSerializer):
    owner_name = serializers.SerializerMethodField()

    def get_owner_name(self, obj):
        if obj.owner:
            return obj.owner.get_full_name() or obj.owner.email or ''
        return ''

    class Meta:
        model = Scene
        fields = [
            'id', 'title', 'spec', 'layout', 'package_dir',
            'is_public', 'owner_name', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'package_dir', 'owner_name', 'created_at', 'updated_at']


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
