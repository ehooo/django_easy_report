from django import forms


class SendEmailForm(forms.Form):
    send_to = forms.EmailField()
