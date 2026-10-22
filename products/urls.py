from django.urls import path
from . import views

urlpatterns = [
    path('pos/', views.pos_screen, name='pos_screen'),
    path('settings/', views.settings_view, name='settings_view'),
    path('purchase/', views.purchase_view, name='purchase_view'),
    path('update-prices/', views.update_prices_view, name='update_prices_view'),
    path('print-barcode/', views.print_barcode_view, name='print_barcode'),
    path('pos-sales/', views.pos_sales_view, name='pos_sales'),
    path('process-sale/', views.process_sale, name='process_sale'),
    path('hold-sales/', views.hold_sales_list, name='hold_sales_list'),
    path('my-sales/', views.sales_list_view, name='sales_list'), 
    path('reprint-invoice/<int:sale_id>/', views.reprint_invoice, name='reprint_invoice'), 
    path('return-product/', views.return_page_view, name='return_page'),
    path('get-invoice-details/', views.get_invoice_details, name='get_invoice_details'), 
    path('process-return/', views.process_return, name='process_return'), 
    path('manage-users/', views.manage_users, name='manage_users'),
    path('inventory/stock/', views.add_inventory_stock, name='add_inventory_stock'),
    path('inventory/ledger/', views.customer_ledger_list, name='customer_ledger_list'),
    path('inventory/process-sale/', views.process_inventory_sale, name='process_inventory_sale'),
    path('inventory/pos/', views.inventory_pos_screen, name='inventory_pos_screen'),
path('inventory/sale-submit/', views.process_inventory_sale, name='process_inventory_sale'),
path('inventory/recovery/', views.customer_payment_receive, name='customer_payment_receive'),
path('inventory/customer-stats/<int:customer_id>/', views.get_customer_stats, name='get_customer_stats'),
path('inventory/stock-entry/', views.inventory_stock_entry, name='inventory_stock_entry'),
path('inventory/product-delete/<int:product_id>/', views.delete_product, name='delete_product'),
    path('inventory/product-toggle/<int:product_id>/', views.toggle_product_status, name='toggle_product_status'),
path('process-inventory-sale/', views.process_inventory_sale, name='process_inventory_sale'),
path('customer/details/<int:customer_id>/', views.customer_details, name='customer_details'),
# Aapki urls.py mein ye line honi chahiye
path('inventory/receipt-print/<int:payment_id>/', views.receipt_print_view, name='receipt_print_view'),
# Shuru se 'pos/' ko delete kar dein kyunki main urls.py isko automatically attach kar rhi hai
path('inventory/inventory_invoice_print/<str:invoice_no>/', views.print_inventory_invoice, name='print_inventory_invoice'),
path('inventory/inventory_invoice_duplicate/<str:invoice_no>/', views.inventory_invoice_duplicate, name='inventory_invoice_duplicate'),
]