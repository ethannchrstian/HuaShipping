from django.urls import path

from . import views

urlpatterns = [
    path('', views.voyage_list, name='rekap'),
    path('voyage/<int:pk>/', views.voyage_detail, name='voyage_detail'),
    path('voyage/<int:pk>/kegiatan/tambah/', views.activity_add, name='activity_add'),
]
