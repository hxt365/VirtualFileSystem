from django.urls import path

from . import views

app_name = 'filesystem'

urlpatterns = [
    path('cd/', views.CdAPIView.as_view(), name='cd'),
    path('cr/', views.CrAPIView.as_view(), name='cr'),
    path('cat/', views.CatAPIView.as_view(), name='cat'),
    path('ls/', views.LsAPIView.as_view(), name='ls'),
    path('find/', views.FindAPIView.as_view(), name='find'),
    path('up/', views.UpAPIView.as_view(), name='up'),
    path('mv/', views.MvAPIView.as_view(), name='mv'),
    path('rm/', views.RmAPIView.as_view(), name='rm'),
]
