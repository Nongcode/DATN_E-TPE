from django.urls import path

from . import views


app_name = "store"

urlpatterns = [
    path("", views.home, name="home"),
    path("dang-nhap/", views.login_view, name="login"),
    path("dang-ky/", views.register_view, name="register"),
    path("dang-xuat/", views.logout_view, name="logout"),
    path("tin-tuc/", views.news_list, name="news_list"),
    path("tin-tuc/<slug:identifier>/", views.news_detail, name="news_detail"),
    path("lien-he/", views.contact, name="contact"),
    path("san-pham/", views.product_list, name="product_list"),
    path("san-pham/<int:pk>/", views.product_detail, name="product_detail"),
    path("san-pham/<int:pk>/them-vao-gio/", views.add_to_cart, name="add_to_cart"),
    path("gio-hang/", views.cart_detail, name="cart_detail"),
    path("gio-hang/<int:item_id>/cap-nhat/", views.update_cart_item, name="update_cart_item"),
    path("gio-hang/<int:item_id>/go/", views.remove_cart_item, name="remove_cart_item"),
]
