from django import forms
from .models import Book, BookPageAnswer, BookCover, BookDedication
from .cover_designs import TEMPLATE_CHOICES

class BookForm(forms.ModelForm):
    # Include fields for the cover directly here for simpler UI or handle separately
    template = forms.ChoiceField(
        choices=TEMPLATE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_template'}),
        label="Стиль оформления"
    )

    class Meta:
        model = Book
        fields = ['title', 'author', 'dedication', 'subtitle']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название книги', 'id': 'id_title'}),
            'author': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Автор', 'id': 'id_author'}),
            'subtitle': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Подзаголовок', 'id': 'id_subtitle'}),
            'dedication': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'dedication': 'Кому посвящается'
        }

class BookPageForm(forms.ModelForm):
    class Meta:
        model = BookPageAnswer
        fields = ['answer', 'image']
        widgets = {
            'answer': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Ваш ответ...', 'id': 'id_answer'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control', 'id': 'id_image'}),
        }

    def clean_answer(self):
        answer = self.cleaned_data.get('answer')
        if answer:
            word_count = len(answer.split())
            if word_count > 250:
                raise forms.ValidationError(f"Превышен лимит слов! Максимум 250 слов (сейчас {word_count}).")
        return answer
