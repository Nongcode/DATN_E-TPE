import os
import django
import random

# Thiết lập môi trường Django để script có thể tương tác với Database
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'etek_core.settings')
django.setup()

from store.models import Category, Product
from faker import Faker

fake = Faker('vi_VN') # Sử dụng ngôn ngữ Tiếng Việt

def seed_categories_and_products():
    print("Đang xóa dữ liệu cũ...")
    Category.objects.all().delete()
    Product.objects.all().delete()

    print("Đang tạo Danh mục...")
    categories = ['Cảm biến ô tô', 'Phụ tùng máy', 'Phụ kiện ô tô', 'Dầu nhớt & Phụ gia']
    category_objs = []
    for cat_name in categories:
        cat = Category.objects.create(name=cat_name, description=fake.text(max_nb_chars=100))
        category_objs.append(cat)

    print("Đang tạo 15 Sản phẩm ảo...")
    for _ in range(15):
        Product.objects.create(
            category=random.choice(category_objs), # Chọn ngẫu nhiên 1 danh mục
            name=f"{fake.word().capitalize()} ETEK {random.randint(100, 999)}",
            description=fake.paragraph(nb_sentences=3),
            price=round(random.uniform(100000, 5000000), -3), # Giá từ 100k đến 5 triệu (làm tròn)
            quantity=random.randint(0, 50), # Số lượng ngẫu nhiên, có cả = 0 để sau này test Agent
            is_active=True
        )
    print("✅ Đã tạo dữ liệu thành công!")

if __name__ == '__main__':
    seed_categories_and_products()