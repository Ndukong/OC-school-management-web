from decimal import Decimal

from django import forms
from django.contrib.auth.models import User

from .models import (
    AcademicTerm,
    Competency,
    FeeType,
    PTADueConfig,
    PTARubricHead,
    School,
    SchoolClass,
    Student,
    Subject,
    Teacher,
    UserProfile,
)


class StudentImportForm(forms.Form):
    school = forms.ChoiceField(choices=[], label="School")
    file = forms.FileField(label="Select .xlsx file")
    term = forms.ChoiceField(choices=[], label="Academic Term", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import AcademicTerm, School

        schools = School.objects.all()
        self.fields["school"].choices = [(s.id, s.name_en) for s in schools]
        terms = AcademicTerm.objects.all()
        self.fields["term"].choices = [("", "Auto-detect (current/first)")] + [
            (t.id, str(t)) for t in terms
        ]


class IncomeRecordForm(forms.Form):
    fee_type = forms.ModelChoiceField(queryset=None, label="Fee Type")
    student = forms.ModelChoiceField(
        queryset=None, required=False, label="Student (optional)"
    )
    amount = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )
    date_paid = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    receipt_number = forms.CharField(max_length=50, required=False, label="Receipt #")
    notes = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2}), label="Notes"
    )

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            from .models import FeeType, Student

            self.fields["fee_type"].queryset = FeeType.objects.filter(
                school=school, is_active=True
            )
            self.fields["student"].queryset = Student.objects.filter(
                school=school, is_active=True
            ).order_by("first_name", "other_names")


class ExpenditureRecordForm(forms.Form):
    CATEGORY_CHOICES = [("PTA", "PTA"), ("state", "State")]

    category = forms.ChoiceField(choices=CATEGORY_CHOICES)
    rubric_sub_head = forms.ModelChoiceField(
        queryset=None, required=False, label="Rubric Sub-Head"
    )
    amount = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        label="Description",
    )

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            from .models import PTARubricSubHead

            self.fields["rubric_sub_head"].queryset = PTARubricSubHead.objects.filter(
                rubric_head__school=school
            )


class PunishmentForm(forms.Form):
    student = forms.ModelChoiceField(queryset=None, label="Student")
    hours = forms.DecimalField(max_digits=5, decimal_places=1, min_value=Decimal("0.1"))
    date_given = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, students=None, **kwargs):
        super().__init__(*args, **kwargs)
        if students is not None:
            self.fields["student"].queryset = students


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = [
            "first_name",
            "other_names",
            "sex",
            "unique_id",
            "repeater",
            "date_of_birth",
            "place_of_birth",
            "guardian_name",
            "guardian_contact",
            "guardian_address",
            "division_of_origin",
            "sub_division_of_origin",
            "region_of_origin",
            "father_name",
            "mother_name",
            "parent_contact",
            "photo",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._school = school
        if school:
            self.instance.school = school


class TeacherForm(forms.ModelForm):
    class Meta:
        model = Teacher
        fields = ["first_name", "last_name", "teacher_code", "email", "phone", "signature"]

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._school = school
        if school:
            self.instance.school = school


class TeacherAssignmentForm(forms.Form):
    teacher = forms.ModelChoiceField(queryset=None, label="Teacher")
    school_class = forms.ModelChoiceField(queryset=None, label="Class")
    subject = forms.ModelChoiceField(queryset=None, label="Subject")
    is_class_master = forms.BooleanField(
        required=False, initial=False, label="Class Master"
    )

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields["teacher"].queryset = Teacher.objects.filter(
                school=school, is_active=True
            ).order_by("first_name", "last_name")
            self.fields["school_class"].queryset = SchoolClass.objects.filter(
                school=school
            ).order_by("sort_order")
            self.fields["subject"].queryset = Subject.objects.filter(
                school=school
            ).order_by("sort_order")
        else:
            self.fields["teacher"].queryset = Teacher.objects.none()
            self.fields["school_class"].queryset = SchoolClass.objects.none()
            self.fields["subject"].queryset = Subject.objects.none()


class SchoolForm(forms.ModelForm):
    class Meta:
        model = School
        fields = [
            "name_en",
            "name_fr",
            "logo",
            "seal",
            "matricule",
            "phone",
            "region_en",
            "region_fr",
            "division_en",
            "division_fr",
            "motto_en",
            "motto_fr",
            "letterhead_line3_en",
            "letterhead_line3_fr",
        ]
        widgets = {
            "letterhead_line3_en": forms.TextInput(
                attrs={"placeholder": "Optional extra line (EN)"}
            ),
            "letterhead_line3_fr": forms.TextInput(
                attrs={"placeholder": "Optional extra line (FR)"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get("instance")
        initial_val = instance.periods_per_day if instance and instance.pk else 8
        self.fields["periods_per_day"] = forms.IntegerField(
            min_value=6,
            max_value=10,
            initial=initial_val,
            required=False,
            help_text="Number of teaching periods per day (6–10).",
        )

    def save(self, commit=True):
        instance = super().save(commit=False)
        value = self.cleaned_data.get("periods_per_day")
        if value is not None:
            instance.periods_per_day = value
        if commit:
            instance.save()
        return instance


class SchoolClassForm(forms.ModelForm):
    class Meta:
        model = SchoolClass
        fields = [
            "name",
            "code",
            "stream",
            "cycle",
            "form_level",
            "promotion_mark",
            "dismissal_mark",
            "sort_order",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g., Form 1"}),
            "code": forms.TextInput(attrs={"placeholder": "e.g., F1"}),
            "stream": forms.TextInput(attrs={"placeholder": "e.g., A, B, Industrial"}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._school = school
        if school:
            self.instance.school = school

    def clean(self):
        cleaned = super().clean()
        if not cleaned:
            return cleaned
        code = (cleaned.get("code") or "").strip().upper()
        stream = (cleaned.get("stream") or "").strip()
        cleaned["code"] = code
        cleaned["stream"] = stream
        school = self._school or getattr(self.instance, "school", None)
        if school and code:
            dup = SchoolClass.objects.filter(school=school, code=code, stream=stream)
            if self.instance.pk:
                dup = dup.exclude(pk=self.instance.pk)
            if dup.exists():
                raise forms.ValidationError(
                    f"A class with code '{code}' and stream '{stream or '—'}' "
                    "already exists for this school."
                )
        return cleaned


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ["name", "code", "sort_order"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g., English Language"}),
            "code": forms.TextInput(attrs={"placeholder": "e.g., ENL"}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._school = school
        if school:
            self.instance.school = school

    def clean(self):
        cleaned = super().clean()
        if not cleaned:
            return cleaned
        code = (cleaned.get("code") or "").strip().upper()
        cleaned["code"] = code
        school = self._school or getattr(self.instance, "school", None)
        if school and code:
            dup = Subject.objects.filter(school=school, code=code)
            if self.instance.pk:
                dup = dup.exclude(pk=self.instance.pk)
            if dup.exists():
                raise forms.ValidationError(
                    f"A subject with code '{code}' already exists for this school."
                )
        return cleaned


class ClassSubjectForm(forms.Form):
    school_class = forms.ModelChoiceField(queryset=None, label="Class")
    subject = forms.ModelChoiceField(queryset=None, label="Subject")
    coefficient = forms.IntegerField(min_value=1, max_value=9, initial=1)
    sort_order = forms.IntegerField(initial=0, required=False)

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields["school_class"].queryset = SchoolClass.objects.filter(
                school=school
            ).order_by("sort_order")
            self.fields["subject"].queryset = Subject.objects.filter(
                school=school
            ).order_by("sort_order")
        else:
            self.fields["school_class"].queryset = SchoolClass.objects.none()
            self.fields["subject"].queryset = Subject.objects.none()


class CompetencyForm(forms.ModelForm):
    class Meta:
        model = Competency
        fields = ["subject", "term", "form_level", "description", "sort_order"]
        widgets = {
            "description": forms.Textarea(
                attrs={"rows": 3, "placeholder": "e.g., Write a coherent paragraph"}
            ),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields["subject"].queryset = Subject.objects.filter(
                school=school
            ).order_by("sort_order")
            self.fields["term"].queryset = AcademicTerm.objects.filter(
                school=school
            ).order_by("-year_start", "term_number")
        else:
            self.fields["subject"].queryset = Subject.objects.none()
            self.fields["term"].queryset = AcademicTerm.objects.none()


class AcademicTermForm(forms.ModelForm):
    class Meta:
        model = AcademicTerm
        fields = ["term_number", "year_start", "year_end", "is_current"]
        widgets = {
            "year_start": forms.NumberInput(attrs={"min": 2020, "max": 2035}),
            "year_end": forms.NumberInput(attrs={"min": 2020, "max": 2035}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._school = school
        if school:
            self.instance.school = school

    def clean(self):
        cleaned_data = super().clean()
        year_start = cleaned_data.get("year_start")
        year_end = cleaned_data.get("year_end")
        if year_start and year_end and year_end != year_start + 1:
            raise forms.ValidationError(
                "Year end must be exactly one year after year start."
            )
        return cleaned_data


class UserEditForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False)
    is_active = forms.BooleanField(required=False, initial=True, label="Active")

    class Meta:
        model = UserProfile
        fields = ["role", "phone", "teacher"]

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._school = school
        self.fields["teacher"].queryset = Teacher.objects.filter(
            school=school, is_active=True
        ).order_by("first_name", "last_name")
        self.fields["teacher"].required = False
        self.fields["teacher"].empty_label = "— No teacher link —"

    def clean(self):
        cleaned_data = super().clean()
        teacher = cleaned_data.get("teacher")
        if teacher and self._school and teacher.school_id != self._school.pk:
            raise forms.ValidationError("Teacher must belong to this school.")
        return cleaned_data


class UserCreateForm(forms.Form):
    ROLE_CHOICES = UserProfile.ROLE_CHOICES

    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False)
    password = forms.CharField(
        widget=forms.PasswordInput, min_length=6, label="Password"
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput, label="Confirm password"
    )
    role = forms.ChoiceField(choices=ROLE_CHOICES)
    teacher = forms.ModelChoiceField(
        queryset=None, required=False, empty_label="— No teacher link —"
    )

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields["teacher"].queryset = Teacher.objects.filter(
                school=school, is_active=True
            ).order_by("first_name", "last_name")
        else:
            self.fields["teacher"].queryset = Teacher.objects.none()

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Username already exists.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")
        if password and password != password_confirm:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data


class PTARubricHeadForm(forms.ModelForm):
    class Meta:
        model = PTARubricHead
        fields = ["name", "code", "sort_order"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g., Infrastructure"}),
            "code": forms.TextInput(attrs={"placeholder": "e.g., INFRA"}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._school = school
        if school:
            self.instance.school = school


class PTARubricSubHeadForm(forms.Form):
    rubric_head = forms.ModelChoiceField(queryset=None, label="Rubric Head")
    name = forms.CharField(max_length=255)
    code = forms.CharField(max_length=10, required=False)

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields["rubric_head"].queryset = PTARubricHead.objects.filter(
                school=school
            ).order_by("sort_order")
        else:
            self.fields["rubric_head"].queryset = PTARubricHead.objects.none()


class PTADueConfigForm(forms.ModelForm):
    class Meta:
        model = PTADueConfig
        fields = ["school_class", "amount"]
        widgets = {
            "amount": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields["school_class"].queryset = SchoolClass.objects.filter(
                school=school
            ).order_by("sort_order")
        else:
            self.fields["school_class"].queryset = SchoolClass.objects.none()


class FeeTypeForm(forms.ModelForm):
    class Meta:
        model = FeeType
        fields = ["name", "category", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g., PTA Dues"}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._school = school
        if school:
            self.instance.school = school
