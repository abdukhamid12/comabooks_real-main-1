from django.contrib.auth.views import LoginView
from .forms import CustomLoginForm

class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = CustomLoginForm

    def get_success_url(self):
        from django.urls import reverse
        return self.get_redirect_url() or reverse('management_home' if self.request.user.is_staff else 'dashboard')
