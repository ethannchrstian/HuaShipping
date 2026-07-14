from django.urls import path

from . import views

urlpatterns = [
    path('', views.voyage_list, name='rekap'),
    path('laporan/', views.laporan, name='laporan'),
    path('ekspor.csv', views.export_csv, name='ekspor_csv'),
    path('voyage/baru/', views.voyage_create, name='voyage_create'),
    path('voyage/<int:pk>/', views.voyage_detail, name='voyage_detail'),
    path('voyage/<int:pk>/ubah/', views.voyage_edit, name='voyage_edit'),
    path('voyage/<int:pk>/cetak/', views.voyage_cetak, name='voyage_cetak'),
    path('voyage/<int:pk>/selesaikan/', views.voyage_complete, name='voyage_complete'),
    path('voyage/<int:pk>/buka-kunci/', views.voyage_unlock, name='voyage_unlock'),
    path('voyage/<int:pk>/hapus/', views.voyage_delete, name='voyage_delete'),
    path('armada/', views.armada, name='armada'),
    path('armada/<int:pk>/riwayat/', views.armada_riwayat, name='armada_riwayat'),
    path('data/', views.data_master, name='data_master'),
    path('data/<str:jenis>/baru/', views.master_edit, name='master_create'),
    path('data/<str:jenis>/<int:pk>/ubah/', views.master_edit, name='master_edit'),
    path('voyage/<int:pk>/kegiatan/tambah/', views.activity_add, name='activity_add'),
    path('kegiatan/<int:pk>/ubah/', views.activity_edit, name='activity_edit'),
    path('kegiatan/<int:pk>/hapus/', views.activity_delete, name='activity_delete'),
    path('kegiatan/<int:pk>/pulihkan/', views.activity_restore, name='activity_restore'),
    path('kegiatan/<int:pk>/urungkan/', views.activity_undo_add, name='activity_undo_add'),
]
