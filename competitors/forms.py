from django import forms

from competitors.models import Competitor


class AddCompetitorForm(forms.ModelForm):
    class Meta:
        model = Competitor
        fields = ("name", "url", "description", "is_active")
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "maxlength": 100}),
            "url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://example.com"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_url(self) -> str:
        return self.cleaned_data["url"].strip()
