from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from decimal import Decimal
# 1. Pehle Category
class Category(models.Model):
    name = models.CharField(max_length=100)
    status = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True) 

    def __str__(self):
        return self.name

# 2. Phir Unit
class Unit(models.Model):
    name = models.CharField(max_length=100)
    status = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    def __str__(self):
        return self.name

# 3. Phir Supplier (Ye zaroori hai PurchaseInvoice se pehle)
class Supplier(models.Model):
    name = models.CharField(max_length=200)
    contact_number = models.CharField(max_length=15, null=True, blank=True)
    address = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name

# 4. Phir Product
class Product(models.Model):
    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=True, blank=True)
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, null=True, blank=True)
    barcode = models.CharField(max_length=50, unique=True, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    stock_quantity = models.IntegerField(default=0)
    status = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    def __str__(self):
        return self.name

# 5. Phir PurchaseInvoice (Kyunke isay Supplier aur Product chahiye)
class PurchaseInvoice(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    invoice_number = models.CharField(max_length=100, unique=True)
    purchase_date = models.DateField()
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Inv: {self.invoice_number} - {self.supplier.name}"
class ProductPriceHistory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='price_history')
    old_price = models.DecimalField(max_digits=10, decimal_places=2)
    new_price = models.DecimalField(max_digits=10, decimal_places=2)
    change_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product.name}: {self.old_price} -> {self.new_price}"
class Sale(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE) # Ab error nahi aayega
    invoice_no = models.CharField(max_length=20, unique=True)
    customer_mobile = models.CharField(max_length=15, null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_hold = models.BooleanField(default=False)
class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
class SaleReturn(models.Model):
    original_sale = models.ForeignKey(Sale, on_delete=models.CASCADE)
    return_date = models.DateTimeField(auto_now_add=True)
    total_returned_amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Return for {self.original_sale.invoice_no}"

class SaleReturnItem(models.Model):
    sale_return = models.ForeignKey(SaleReturn, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

class InventoryCustomer(models.Model):
    name = models.CharField(max_length=250)
    mobile = models.CharField(max_length=15, unique=True)
    opening_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_purchased = models.DecimalField(max_digits=12, decimal_places=2, default=0.00) # Total Bill
    total_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)      # Received Amount
    total_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)   # Outstanding Amount
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        # 1. Crash se bachne ke liye pehle sab ko Decimal me convert kiya
        opening = Decimal(str(self.opening_balance))
        purchased = Decimal(str(self.total_purchased))
        paid = Decimal(str(self.total_paid))
        
        # 2. Sahi Accounting Formula: (Puraani Raqam + Naya Bill) - Mili Hui Raqam
        self.total_balance = (opening + purchased) - paid
        
        # 3. Django ka original save method call kiya
        super(InventoryCustomer, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - Outstanding: {self.total_balance}"
class InventoryProduct(models.Model):
    name = models.CharField(max_length=200)
    category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True, blank=True) # Naya field
    barcode = models.CharField(max_length=100, unique=True)
    expiry_date = models.DateField(null=True, blank=True)
    stock = models.IntegerField(default=0)
    retail_price = models.DecimalField(max_digits=10, decimal_places=2) # 200
    tp_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0) # 5%
    is_active = models.BooleanField(default=True)
    @property
    def trade_price(self):
        # Calculation: 200 - (200 * 5 / 100) = 190
        discount = (self.retail_price * self.tp_percent) / 100
        return self.retail_price - discount

    def __str__(self):
        return self.name

  # 1. Inventory ki Sales ka Main Table
class InventorySale(models.Model):
    customer = models.ForeignKey('InventoryCustomer', on_delete=models.CASCADE)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateTimeField(auto_now_add=True)
    invoice_no = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return f"Inv-Sale {self.invoice_no}"

class CashPayment(models.Model):
    # 'on_experimental_id' ko remove kar dein, ye ghalat tha.
    customer = models.ForeignKey(InventoryCustomer, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateTimeField(auto_now_add=True)
    remarks = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.customer.name} - {self.amount}"
# 2. Inventory Sale ke Items (Jo cheezain sell huin)
class InventorySaleItem(models.Model):
    sale = models.ForeignKey(InventorySale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('InventoryProduct', on_delete=models.CASCADE) # Aapka Inventory wala model
    quantity = models.PositiveIntegerField()
    price_at_sale = models.DecimalField(max_digits=10, decimal_places=2)

# 3. Inventory ki Returns ka Table
class InventoryReturn(models.Model):
    sale_item = models.ForeignKey(InventorySaleItem, on_delete=models.CASCADE)
    return_qty = models.PositiveIntegerField()
    return_date = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(null=True, blank=True)

class InventoryTransaction(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    customer = models.ForeignKey(InventoryCustomer, on_delete=models.CASCADE) # Ya InventoryCustomer
    qty = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product.name} - {self.qty}"

class PurchaseItem(models.Model):
    invoice = models.ForeignKey(PurchaseInvoice, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.purchase_price
        # Stock update logic
        self.product.stock_quantity += self.quantity
        self.product.save()
        super().save(*args, **kwargs)