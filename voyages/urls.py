from django.urls import path

from . import views

urlpatterns = [
    path('', views.voyage_list, name='rekap'),
    path('ekspor.csv', views.export_csv, name='ekspor_csv'),
    path('voyage/baru/', views.voyage_create, name='voyage_create'),
    path('voyage/<int:pk>/', views.voyage_detail, name='voyage_detail'),
    path('voyage/<int:pk>/ubah/', views.voyage_edit, name='voyage_edit'),
    path('voyage/<int:pk>/selesaikan/', views.voyage_complete, name='voyage_complete'),
    path('voyage/<int:pk>/buka-kunci/', views.voyage_unlock, name='voyage_unlock'),
    path('voyage/<int:pk>/kegiatan/tambah/', views.activity_add, name='activity_add'),
    path('kegiatan/<int:pk>/ubah/', views.activity_edit, name='activity_edit'),
    path('kegiatan/<int:pk>/hapus/', views.activity_delete, name='activity_delete'),
    path('kegiatan/<int:pk>/pulihkan/', views.activity_restore, name='activity_restore'),
]
