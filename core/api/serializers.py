from rest_framework import serializers

from core.models import (
    Competency,
    Student,
    TeacherAssignment,
)


class CompetencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Competency
        fields = ["id", "description", "sort_order"]


class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = ["id", "first_name", "other_names", "full_name", "unique_id"]


class CompetencyScoreSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    competency_id = serializers.IntegerField()
    score = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, allow_null=True
    )

    def validate_score(self, value):
        if value is not None and (value < 0 or value > 20):
            raise serializers.ValidationError("Score must be between 0 and 20")
        return value


class TeacherAssignmentSerializer(serializers.ModelSerializer):
    school_class = serializers.StringRelatedField()
    subject = serializers.StringRelatedField()
    class_id = serializers.IntegerField(source="school_class_id")
    subject_id = serializers.IntegerField()

    class Meta:
        model = TeacherAssignment
        fields = ["class_id", "subject_id", "school_class", "subject", "is_class_master"]
