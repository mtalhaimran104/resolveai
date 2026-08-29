from django import forms

from .models import KnowledgeArticle


class KnowledgeArticleForm(forms.ModelForm):
    class Meta:
        model = KnowledgeArticle
        fields = [
            "title", "slug", "excerpt", "content", "category",
            "status", "is_public", "published_at",
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
            "excerpt": forms.Textarea(attrs={
                "class": "form-control", "rows": 2, "maxlength": 220,
                "placeholder": "One or two sentences shown in search results and article lists.",
            }),
            "content": forms.Textarea(attrs={"class": "form-control", "rows": 12}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "is_public": forms.CheckboxInput(attrs={"class": "form-check-input", "role": "switch"}),
            "published_at": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        }








# from django import forms

# from .models import KnowledgeArticle


# class KnowledgeArticleForm(forms.ModelForm):
#     class Meta:
#         model = KnowledgeArticle
#         fields = [
#             "title", "excerpt", "content", "category",
#             "status", "is_public", "published_at",
#         ]
#         widgets = {
#             "title": forms.TextInput(attrs={
#                 "class": "form-control", "minlength": 8,
#                 "placeholder": "e.g. How to Reset Your Account Password",
#             }),
#             "excerpt": forms.Textarea(attrs={
#                 "class": "form-control", "rows": 2, "maxlength": 220,
#                 "placeholder": "One or two sentences shown in search results and article lists.",
#             }),
#             "content": forms.Textarea(attrs={"class": "form-control", "rows": 12}),
#             "category": forms.Select(attrs={"class": "form-select"}),
#             "tags": forms.TextInput(attrs={
#                 "class": "form-control", "placeholder": "password, account, login",
#             }),
#             "status": forms.Select(attrs={"class": "form-select"}),
#             "is_public": forms.CheckboxInput(attrs={"class": "form-check-input", "role": "switch"}),
# #             "published_at": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
#         }


