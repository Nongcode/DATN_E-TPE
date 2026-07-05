from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Customer


PASSWORD_VALIDATION_MESSAGES = {
    "password_too_short": "Mật khẩu quá ngắn. Mật khẩu phải chứa ít nhất %(min_length)d ký tự.",
    "password_too_common": "Mật khẩu này quá phổ biến.",
    "password_entirely_numeric": "Mật khẩu không được hoàn toàn là số.",
    "password_too_similar": "Mật khẩu không được quá giống với thông tin cá nhân của bạn.",
}


class StoreLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Tên đăng nhập",
        widget=forms.TextInput(attrs={"placeholder": "Nhập tên đăng nhập"}),
    )
    password = forms.CharField(
        label="Mật khẩu",
        widget=forms.PasswordInput(attrs={"placeholder": "Nhập mật khẩu"}),
    )


class StoreRegistrationForm(UserCreationForm):
    error_messages = {
        **UserCreationForm.error_messages,
        "password_mismatch": "Hai mật khẩu xác nhận không khớp.",
    }

    full_name = forms.CharField(
        label="Họ và tên",
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": "Nguyễn Văn A"}),
    )
    phone_number = forms.CharField(
        label="Số điện thoại",
        max_length=15,
        widget=forms.TextInput(attrs={"placeholder": "0889584290"}),
    )
    email = forms.EmailField(
        label="Email",
        required=False,
        widget=forms.EmailInput(attrs={"placeholder": "email@example.com"}),
    )
    date_of_birth = forms.DateField(
        label="Ngày sinh",
        required=True,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    address = forms.CharField(
        label="Địa chỉ",
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": "Địa chỉ nhận hàng hoặc khu vực sinh sống"}),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "full_name", "phone_number", "email", "date_of_birth", "address")
        labels = {"username": "Tên đăng nhập"}
        widgets = {
            "username": forms.TextInput(attrs={"placeholder": "Tạo tên đăng nhập"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = "Mật khẩu"
        self.fields["password1"].widget.attrs.update({"placeholder": "Tạo mật khẩu"})
        self.fields["password1"].help_text = (
            "Mật khẩu không được quá giống thông tin cá nhân, "
            "phải có ít nhất 8 ký tự, không quá phổ biến và không hoàn toàn là số."
        )
        self.fields["password2"].label = "Xác nhận mật khẩu"
        self.fields["password2"].widget.attrs.update({"placeholder": "Nhập lại mật khẩu"})
        self.fields["password2"].help_text = "Nhập lại mật khẩu để xác nhận."

    def validate_password_for_user(self, user, password_field_name="password2"):
        password = self.cleaned_data.get(password_field_name)
        if not password:
            return
        try:
            password_validation.validate_password(password, user)
        except ValidationError as error:
            mapped_errors = []
            for validation_error in error.error_list:
                message = PASSWORD_VALIDATION_MESSAGES.get(validation_error.code)
                if message:
                    mapped_errors.append(
                        ValidationError(
                            message,
                            code=validation_error.code,
                            params=validation_error.params,
                        )
                    )
                else:
                    mapped_errors.append(validation_error)
            self.add_error(password_field_name, ValidationError(mapped_errors))

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        if email and (
            User.objects.filter(email__iexact=email).exists()
            or Customer.objects.filter(email__iexact=email).exists()
        ):
            raise forms.ValidationError("Email này đã được sử dụng.")
        return email

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get("phone_number", "").strip()
        if Customer.objects.filter(phone_number=phone_number).exists():
            raise forms.ValidationError("Số điện thoại này đã được sử dụng.")
        return phone_number

    def clean_date_of_birth(self):
        date_of_birth = self.cleaned_data.get("date_of_birth")
        if date_of_birth and date_of_birth > timezone.localdate():
            raise forms.ValidationError("Ngày sinh không được lớn hơn ngày hiện tại.")
        return date_of_birth

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data.get("email") or ""
        full_name = self.cleaned_data["full_name"].strip()
        user.first_name = full_name
        if commit:
            user.save()
            Customer.objects.create(
                user=user,
                full_name=full_name,
                email=self.cleaned_data.get("email") or None,
                phone_number=self.cleaned_data["phone_number"].strip(),
                address=self.cleaned_data.get("address", "").strip(),
                date_of_birth=self.cleaned_data.get("date_of_birth"),
            )
        return user
