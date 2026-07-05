from django.db import models
from django.core.exceptions import ValidationError
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

    name = models.CharField(max_length=255, unique=True, verbose_name="Tên danh mục")
    slug = models.SlugField(max_length=255, unique=True, null=True, blank=True, verbose_name="Đường dẫn tĩnh (Slug)")
    image = models.ImageField(upload_to='categories/', null=True, blank=True, verbose_name="Hình ảnh đính kèm")
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', verbose_name="Danh mục cha")
    
    # --- TRƯỜNG TRẠNG THÁI MỚI ---
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='visible', verbose_name="Trạng thái")
    
    description = models.TextField(null=True, blank=True, verbose_name="Mô tả")

    class Meta:
        verbose_name = 'Danh mục'
        verbose_name_plural = '01. Danh mục sản phẩm'

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
    brand = models.CharField(max_length=120, null=True, blank=True, verbose_name="Thương hiệu")
    manufacturer = models.CharField(max_length=255, null=True, blank=True, verbose_name="Hãng sản xuất")
    compatible_car_brands = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Hãng xe tương thích",
        help_text="Nhập nhiều hãng xe bằng dấu phẩy, ví dụ: Toyota, Honda, Ford.",
    )
    compatible_car_models = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Dòng xe tương thích",
        help_text="Nhập nhiều dòng xe bằng dấu phẩy, ví dụ: Vios, City, Ranger.",
    )
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
        verbose_name_plural = '02. Quản lý sản phẩm'

# ==========================================
# 2b. BẢNG ẢNH CHI TIẾT SẢN PHẨM (Gallery)
# ==========================================
class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images', verbose_name="Sản phẩm")
    image = models.ImageField(upload_to='products/gallery/', verbose_name="Ảnh chi tiết")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ảnh chi tiết sản phẩm'
        verbose_name_plural = '02b. Ảnh chi tiết sản phẩm'

    def __str__(self):
        return f"Ảnh chi tiết của {self.product.name} ({self.id})"

# ==========================================
# 3. BẢNG KHO HÀNG (Inventories)
# ==========================================
class Inventory(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='inventory', verbose_name="Sản phẩm")
    quantity = models.IntegerField(default=0, verbose_name="Số lượng tồn kho thực tế")
    low_stock_threshold = models.IntegerField(default=20, verbose_name="Ngưỡng cảnh báo (Mặc định: 20)")
    last_updated = models.DateTimeField(auto_now=True, verbose_name="Lần cập nhật cuối")

    class Meta:
        verbose_name = 'Kho hàng'
        verbose_name_plural = '03. Quản lý Kho hàng'

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
    phone_number = models.CharField(max_length=15, unique=True, verbose_name="S\u1ed1 \u0111i\u1ec7n tho\u1ea1i")
    address = models.CharField(max_length=255, verbose_name="Địa chỉ giao hàng")
    
    # TRƯỜNG QUAN TRỌNG CHO AGENT CHĂM SÓC KHÁCH HÀNG:
    date_of_birth = models.DateField(null=True, blank=True, verbose_name="Ngày sinh")

    def __str__(self):
        return self.full_name or self.user.username

    class Meta:
        verbose_name = 'Khách hàng'
        verbose_name_plural = '04. Danh mục khách hàng'

# ==========================================
# 5. BẢNG GIỎ HÀNG VÀ CHI TIẾT GIỎ HÀNG
# ==========================================
class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Khách vãng lai/Đăng nhập")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Giỏ hàng'
        verbose_name_plural = '05. Quản lý Giỏ hàng'

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
        verbose_name_plural = '06. Quản lý mã giảm giá'

# ==========================================
# 7. BẢNG ĐƠN HÀNG VÀ CHI TIẾT ĐƠN HÀNG
# ==========================================
class Order(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Chờ xử lý'),
        ('Confirmed', 'Đã lên đơn'),
        ('Shipping', 'Đang vận chuyển'),
        ('Shipped', 'Đã giao hàng'),
        ('Cancelled', 'Đã hủy'),
    )
    CANCELLATION_LOCKED_STATUSES = ('Confirmed', 'Shipping', 'Shipped')

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    voucher = models.ForeignKey(Voucher, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Voucher áp dụng")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Tổng tiền")
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Pending', verbose_name="Trạng thái đơn")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày đặt hàng")

    def clean(self):
        super().clean()
        if not self.pk or self.status != 'Cancelled':
            return

        previous_status = type(self).objects.filter(pk=self.pk).values_list('status', flat=True).first()
        if previous_status in self.CANCELLATION_LOCKED_STATUSES:
            raise ValidationError({
                'status': 'Đơn hàng đã lên đơn nên không thể hủy.'
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Đơn hàng #{self.id} - {self.customer.user.username}"

    class Meta:
        verbose_name = 'Đơn hàng'
        verbose_name_plural = '07. Quản lý đơn hàng'

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Giá lúc mua")
    quantity = models.IntegerField(default=1, verbose_name="Số lượng mua")

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

# ==========================================
# 8. B?NG Y?U C?U T? V?N
# ==========================================
# 8. B?NG Y?U C?U T? V?N
# ==========================================
# 8. BẢNG YÊU CẦU TƯ VẤN
# ==========================================
class ConsultationRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Chờ tư vấn'),
        ('contacted', 'Đã liên hệ'),
        ('converted', 'Đã lên đơn'),
        ('cancelled', 'Đã hủy'),
    )
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='consultation_requests', verbose_name="Khách hàng")
    name = models.CharField(max_length=255, verbose_name="Họ và tên")
    phone = models.CharField(max_length=20, verbose_name="Số điện thoại")
    email = models.EmailField(null=True, blank=True, verbose_name="Email")
    vehicle = models.CharField(max_length=120, null=True, blank=True, verbose_name="Dòng xe")
    message = models.TextField(null=True, blank=True, verbose_name="Nội dung tư vấn")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Trạng thái")
    products = models.ManyToManyField(Product, through='ConsultationRequestItem', related_name='consultation_requests', blank=True, verbose_name="Sản phẩm cần tư vấn")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày gửi yêu cầu")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Lần cập nhật cuối")

    def __str__(self):
        return f"Yêu cầu tư vấn #{self.id} - {self.name}"

    class Meta:
        verbose_name = 'Yêu cầu tư vấn'
        verbose_name_plural = '11. Yêu cầu tư vấn'
        ordering = ('-created_at',)


class ConsultationRequestItem(models.Model):
    consultation_request = models.ForeignKey(ConsultationRequest, on_delete=models.CASCADE, related_name='items', verbose_name="Yêu cầu tư vấn")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Sản phẩm")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Số lượng quan tâm")

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

    class Meta:
        verbose_name = 'Sản phẩm trong yêu cầu tư vấn'
        verbose_name_plural = 'Sản phẩm trong yêu cầu tư vấn'
        unique_together = ('consultation_request', 'product')


# ==========================================
class Blog(models.Model):
    title = models.CharField(max_length=255, verbose_name="Tiêu đề bài viết kỹ thuật/khuyến mãi")
    content = models.TextField(verbose_name="Nội dung bài viết")
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Người đăng bài")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Bài viết'
        verbose_name_plural = '08. Tin tức & Khuyến mãi'

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
        verbose_name_plural = '09. Nhật ký AI Gợi ý'

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
        verbose_name_plural = '10. Tác vụ tự động'

    def __str__(self):
        return f"[{self.get_status_display()}] {self.get_task_type_display()}"

