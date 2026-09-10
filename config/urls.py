from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("create/", views.create_book, name="create_book"),
    path("book/<int:book_id>/edit/", views.edit_pages, name="edit_pages"),
    path("book/<int:book_id>/add_page/", views.add_page, name="add_page"),
    path("book/<int:book_id>/generate_pdf/", views.generate_pdf, name="generate_pdf"),
    path("book/<int:book_id>/finish/", views.finish_book, name="finish_book"),
    path("book/<int:book_id>/delete/", views.delete_book, name="delete_book"),
    path('ai/enhance-answer/', views.enhance_answer_ajax, name='enhance_answer_ajax'),
]
