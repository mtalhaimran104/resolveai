from django import forms
from .models import Ticket, TicketComment, TicketAttachment


class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["subject", "description"]
        widgets = {
            "subject": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Brief summary of the issue",
            }),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 5,
                "placeholder": "Describe the issue in detail",
            }),
        }


class TicketCommentForm(forms.ModelForm):
    class Meta:
        model = TicketComment
        fields = ["message"]
        widgets = {
            "message": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Write a reply…",
                "required": True,
            }),
        }


class TicketAttachmentForm(forms.ModelForm):
    file = forms.FileField(
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "multiple": False}),
    )

    class Meta:
        model = TicketAttachment
        fields = ["file"]

    def clean_file(self):
        f = self.cleaned_data["file"]
        max_size = 10 * 1024 * 1024  # 10 MB
        if f.size > max_size:
            raise forms.ValidationError("File must be smaller than 10 MB.")
        return f