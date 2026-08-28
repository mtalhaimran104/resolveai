from django import forms

from .models import KnowledgeArticle


class KnowledgeArticleForm(forms.ModelForm):
    class Meta:
        model = KnowledgeArticle
        fields = [
            "title", "slug", "summary", "body", "category", "tags",
            "status", "is_public", "is_ai_indexed", "publish_date",
        ]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "form-control", "minlength": 8,
                "placeholder": "e.g. How to Reset Your Account Password",
            }),
            "slug": forms.TextInput(attrs={
                "class": "form-control", "pattern": "[a-z0-9-]+",
                "placeholder": "how-to-reset-your-account-password",
            }),
            "summary": forms.Textarea(attrs={
                "class": "form-control", "rows": 2, "maxlength": 220,
                "placeholder": "One or two sentences shown in search results and article lists.",
            }),
            "body": forms.Textarea(attrs={"class": "form-control", "rows": 12}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "tags": forms.TextInput(attrs={
                "class": "form-control", "placeholder": "password, account, login",
            }),
            "status": forms.Select(attrs={"class": "form-select"}),
            "is_public": forms.CheckboxInput(attrs={"class": "form-check-input", "role": "switch"}),
            "is_ai_indexed": forms.CheckboxInput(attrs={"class": "form-check-input", "role": "switch"}),
            "publish_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        }








# from django import forms

# from .models import KnowledgeArticle


# class KnowledgeArticleForm(forms.ModelForm):
#     class Meta:
#         model = KnowledgeArticle
#         fields = [
#             "title", "summary", "body", "category", "tags",
#             "status", "is_public", "is_ai_indexed", "publish_date",
#         ]
#         widgets = {
#             "title": forms.TextInput(attrs={
#                 "class": "form-control", "minlength": 8,
#                 "placeholder": "e.g. How to Reset Your Account Password",
#             }),
#             "summary": forms.Textarea(attrs={
#                 "class": "form-control", "rows": 2, "maxlength": 220,
#                 "placeholder": "One or two sentences shown in search results and article lists.",
#             }),
#             "body": forms.Textarea(attrs={"class": "form-control", "rows": 12}),
#             "category": forms.Select(attrs={"class": "form-select"}),
#             "tags": forms.TextInput(attrs={
#                 "class": "form-control", "placeholder": "password, account, login",
#             }),
#             "status": forms.Select(attrs={"class": "form-select"}),
#             "is_public": forms.CheckboxInput(attrs={"class": "form-check-input", "role": "switch"}),
#             "is_ai_indexed": forms.CheckboxInput(attrs={"class": "form-check-input", "role": "switch"}),
#             "publish_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
#         }
