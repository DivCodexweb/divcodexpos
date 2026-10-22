from django.contrib import admin
from .models import Category, Unit, Supplier, Product, PurchaseInvoice, PurchaseItem

# Invoice ke andar hi items dikhane ke liye
class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 1

@admin.register(PurchaseInvoice)
class PurchaseInvoiceAdmin(admin.ModelAdmin):
    inlines = [PurchaseItemInline]
    list_display = ['invoice_number', 'supplier', 'purchase_date', 'total_amount']

admin.site.register(Category)
admin.site.register(Unit)
admin.site.register(Supplier)
admin.site.register(Product)