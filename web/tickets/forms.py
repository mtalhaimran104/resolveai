from django import forms

from .models import Ticket, TicketComment, TicketAttachment
from classification.models import TicketCategory
from organization.models import Department


class TicketForm(forms.ModelForm):

    department = forms.ModelChoiceField(
        queryset=Department.objects.filter(
            is_active=True
        ).order_by("name"),
        required=False,
        empty_label="Choose department...",
        widget=forms.Select(
            attrs={
                "class": "form-select",
                "id": "ticketDepartment",
            }
        ),
    )

    category = forms.ModelChoiceField(
        queryset=TicketCategory.objects.filter(
            is_active=True
        ).select_related(
            "department"
        ).order_by("name"),
        required=False,
        empty_label="Choose category...",
        widget=forms.Select(
            attrs={
                "class": "form-select",
                "id": "ticketCategory",
            }
        ),
    )

    priority = forms.ChoiceField(
        choices=Ticket.Priority.choices,
        required=False,
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    class Meta:
        model = Ticket
        fields = [
            "subject",
            "department",
            "category",
            "priority",
            "description",
        ]

        widgets = {
            "subject": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Brief summary of the issue",
                }
            ),

            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": "Describe the issue in detail",
                }
            ),
        }


class TicketCommentForm(forms.ModelForm):

    class Meta:
        model = TicketComment
        fields = ["message"]

        widgets = {
            "message": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Write a reply…",
                    "required": True,
                }
            ),
        }


class TicketAttachmentForm(forms.ModelForm):

    file = forms.FileField(
        widget=forms.ClearableFileInput(
            attrs={
                "class": "form-control",
                "multiple": False,
            }
        ),
    )

    class Meta:
        model = TicketAttachment
        fields = ["file"]

    def clean_file(self):
        f = self.cleaned_data["file"]
        max_size = 10 * 1024 * 1024

        if f.size > max_size:
            raise forms.ValidationError(
                "File must be smaller than 10 MB."
            )

        return f