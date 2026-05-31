from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("script/<int:pk>/", views.script_detail, name="script_detail"),
    path("script/<int:pk>/note/", views.save_note, name="save_note"),
    path("script/<int:pk>/regenerate/", views.regenerate, name="regenerate"),
    path("stories/", views.stories, name="stories"),
    path("stories/<int:pk>/json/", views.story_detail_json, name="story_detail_json"),
    path("trends/", views.trends, name="trends"),
    path("trends/refresh/", views.refresh_trends_view, name="refresh_trends"),
    path("trends/<int:pk>/generate/", views.generate_from_trend, name="generate_from_trend"),
]
