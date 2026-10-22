from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views # Ye zaroori hai

urlpatterns = [
    path('admin/', admin.site.urls),
    # App khulye hi login page aaye
    path('', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('pos/', include('products.urls')), 
    
]