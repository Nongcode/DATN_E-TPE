from django.db import models
from django.contrib.auth.models import User # Kế thừa bảng User mặc định của Django
from django.utils import timezone

# ==========================================
# 1. BẢNG DANH MỤC SẢN PHẨM
# ==========================================
class Category(models.Model):
    # --- Định nghĩa 3 trạng thái cho Combo box ---
    STATUS_CHOICES = (
        ('visible', 'Hiển thị'),
        ('hidden', 'Ẩn'),
        ('out_of_stock', 'Hết hàng'),
    )

    name = models.CharField(max_length=255, verbose_name="Tên danh mục")
    slug = models.SlugField(max_length=255, unique=True, null=True, blank=True, verbose_name="Đường dẫn tĩnh (Slug)")
    image = models.ImageField(upload_to='categories/', null=True, blank=True, verbose_name="Hình ảnh đính kèm")
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', verbose_name="Danh mục cha")
    
    # --- TRƯỜNG TRẠNG THÁI MỚI ---
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='visible', verbose_name="Trạng thái")
    
    description = models.TextField(null=True, blank=True, verbose_name="Mô tả")

    class Meta:
        verbose_name = 'Danh mục'
        verbose_name_plural = '1. Danh mục sản phẩm'

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} -> {self.name}"
        return self.name
    
# ==========================================
# 2. BẢNG SẢN PHẨM (Thiết bị ô tô ETEK)
# ==========================================
class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products', verbose_name="Danh mục")
    name = models.CharField(max_length=255, verbose_name="Tên thiết bị ô tô")
    slug = models.SlugField(max_length=255, unique=True, null=True, blank=True, verbose_name="Đường dẫn thân thiện")
    sku = models.CharField(max_length=50, unique=True, null=True, blank=True, verbose_name="Mã quản lý kho (SKU)")
    description = models.TextField(verbose_name="Mô tả chi tiết thông số (Dùng vector hóa)")
    price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Giá bán hiện tại")
    image = models.ImageField(upload_to='products/', null=True, blank=True, verbose_name="Ảnh sản phẩm")
    
    # TRƯỜNG QUAN TRỌNG CHO AGENT QUẢN LÝ KHO:
    is_active = models.BooleanField(default=True, verbose_name="Đang hiển thị trên Web")
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.sku}] {self.name}"

    class Meta:
        verbose_name = 'Sản phẩm'
        verbose_name_plural = '2. Quản lý sản phẩm'

# ==========================================
# 3. BẢNG KHO HÀNG (Inventories)
# ==========================================
class Inventory(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='inventory', verbose_name="Sản phẩm")
    quantity = models.IntegerField(default=0, verbose_name="Số lượng tồn kho thực tế")
    low_stock_threshold = models.IntegerField(default=5, verbose_name="Ngưỡng cảnh báo (Mặc định: 5)")
    last_updated = models.DateTimeField(auto_now=True, verbose_name="Lần cập nhật cuối")

    class Meta:
        verbose_name = 'Kho hàng'
        verbose_name_plural = '3. Quản lý Kho hàng'

    def __str__(self):
        return f"Kho: {self.product.name} - Tồn: {self.quantity}"

# ==========================================
# 4. BẢNG KHÁCH HÀNG (Mở rộng từ User của Django)
# ==========================================
class Customer(models.Model):
    # Liên kết 1-1 với tài khoản đăng nhập của Django
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
    full_name = models.CharField(max_length=255, null=True, blank=True, verbose_name="Họ và tên")
    email = models.EmailField(unique=True, null=True, blank=True, verbose_name="Email nhận thông báo")
    phone_number = models.CharField(max_length=15, verbose_name="Số điện thoại")
    address = models.CharField(max_length=255, verbose_name="Địa chỉ giao hàng")
    
    # TRƯỜNG QUAN TRỌNG CHO AGENT CHĂM SÓC KHÁCH HÀNG:
    date_of_birth = models.DateField(null=True, blank=True, verbose_name="Ngày sinh")

    def __str__(self):
        return self.full_name or self.user.username

    class Meta:
        verbose_name = 'Khách hàng'
        verbose_name_plural = '4. Danh mục khách hàng'

# ==========================================
# 5. BẢNG GIỎ HÀNG VÀ CHI TIẾT GIỎ HÀNG
# ==========================================
class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Khách vãng lai/Đăng nhập")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Giỏ hàng'
        verbose_name_plural = '5. Quản lý Giỏ hàng'

    def __str__(self):
        return f"Giỏ hàng #{self.id}"

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1, verbose_name="Số lượng chọn mua")

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

# ==========================================
# 6. BẢNG MÃ GIẢM GIÁ (Voucher sinh nhật)
# ==========================================
class Voucher(models.Model):
    code = models.CharField(max_length=20, unique=True, verbose_name="Mã giảm giá")
    # Voucher này dành riêng cho ai?
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, verbose_name="Khách hàng sở hữu")
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Số tiền giảm")
    
    # TRƯỜNG QUAN TRỌNG CHO THỜI HẠN 2 NGÀY:
    valid_until = models.DateTimeField(verbose_name="Hạn sử dụng")
    is_used = models.BooleanField(default=False, verbose_name="Đã sử dụng chưa?")

    def __str__(self):
        return f"{self.code} - Khách: {self.customer.user.username}"

    class Meta:
        verbose_name = 'Mã giảm giá'
        verbose_name_plural = '6. Quản lý mã giảm giá'

# ==========================================
# 7. BẢNG ĐƠN HÀNG VÀ CHI TIẾT ĐƠN HÀNG
# ==========================================
class Order(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Chờ xử lý'),
        ('Shipped', 'Đã giao hàng'),
        ('Cancelled', 'Đã hủy'),
    )
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    voucher = models.ForeignKey(Voucher, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Voucher áp dụng")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Tổng tiền")
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Pending', verbose_name="Trạng thái đơn")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày đặt hàng")

    def __str__(self):
        return f"Đơn hàng #{self.id} - {self.customer.user.username}"

    class Meta:
        verbose_name = 'Đơn hàng'
        verbose_name_plural = '7. Quản lý đơn hàng'

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Giá lúc mua")
    quantity = models.IntegerField(default=1, verbose_name="Số lượng mua")

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

# ==========================================
# 8. BẢNG BÀI VIẾT / TIN TỨC (Blogs)
# ==========================================
class Blog(models.Model):
    title = models.CharField(max_length=255, verbose_name="Tiêu đề bài viết kỹ thuật/khuyến mãi")
    content = models.TextField(verbose_name="Nội dung bài viết")
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Người đăng bài")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Bài viết'
        verbose_name_plural = '8. Tin tức & Khuyến mãi'

    def __str__(self):
        return self.title

# ==========================================
# 9. BẢNG NHẬT KÝ GỢI Ý (Recommendation Logs)
# ==========================================
class RecommendationLog(models.Model):
    INTERACTION_CHOICES = (
        ('view', 'Xem sản phẩm'),
        ('click', 'Click vào gợi ý'),
        ('add_to_cart', 'Thêm vào giỏ hàng'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Người dùng nhận gợi ý")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Sản phẩm gợi ý")
    interaction_type = models.CharField(max_length=50, choices=INTERACTION_CHOICES, verbose_name="Loại tương tác")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Nhật ký gợi ý'
        verbose_name_plural = '9. Nhật ký AI Gợi ý'

# ==========================================
# 10. BẢNG TÁC VỤ TỰ ĐỘNG (Scheduled Tasks)
# ==========================================
class ScheduledTask(models.Model):
    TASK_CHOICES = (
        ('lock_stock', 'Kiểm soát & Ẩn hết hàng'),
        ('birthday_mail', 'Gửi email chúc mừng sinh nhật'),
        ('auto_hide', 'Tự động ẩn sản phẩm không kinh doanh'),
    )
    STATUS_CHOICES = (
        ('pending', 'Chờ xử lý'),
        ('success', 'Thành công'),
        ('failed', 'Thất bại'),
    )
    task_type = models.CharField(max_length=50, choices=TASK_CHOICES, verbose_name="Loại tác vụ")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Trạng thái thực hiện")
    execution_log = models.TextField(null=True, blank=True, verbose_name="Chi tiết lỗi / Số lượng thành công")
    run_at = models.DateTimeField(verbose_name="Thời điểm kích hoạt")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Tác vụ Tự động'
        verbose_name_plural = '10. Tác vụ Background'

    def __str__(self):
        return f"[{self.get_status_display()}] {self.get_task_type_display()}"