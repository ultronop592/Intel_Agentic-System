from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.forms import ProfileForm, SignupForm


def signup_view(request: HttpRequest) -> HttpResponse:
    """Register a new user and sign them in immediately."""
    if request.user.is_authenticated:
        return redirect("competitors:dashboard")

    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Your account has been created.")
        return redirect("competitors:dashboard")
    return render(request, "accounts/signup.html", {"form": form})


def login_view(request: HttpRequest) -> HttpResponse:
    """Authenticate a user using Django's built-in session auth."""
    if request.user.is_authenticated:
        return redirect("competitors:dashboard")

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            login(request, form.get_user())
            messages.success(request, "Welcome back.")
            next_url = request.GET.get("next") or request.POST.get("next")
            return redirect(next_url or reverse("competitors:dashboard"))
        messages.error(request, "Please check your username and password.")
    return render(request, "accounts/login.html", {"form": form, "next": request.GET.get("next", "")})


@require_POST
def logout_view(request: HttpRequest) -> HttpResponse:
    """Log the user out through a CSRF-protected POST request."""
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect("accounts:login")


@login_required
def profile_view(request: HttpRequest) -> HttpResponse:
    """Display and update the authenticated user's profile settings."""
    profile = request.user.profile
    form = ProfileForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form})


@login_required
@require_POST
def delete_account_view(request: HttpRequest) -> HttpResponse:
    """Delete the current authenticated user account."""
    user = get_object_or_404(User, pk=request.user.pk)
    logout(request)
    user.delete()
    messages.success(request, "Your account has been deleted.")
    return redirect("landing")
