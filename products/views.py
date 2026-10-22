import json
import decimal
from decimal import Decimal
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Category, Unit, Product,SaleReturn,InventoryProduct,InventorySale,CashPayment,InventorySaleItem, Supplier, Sale, SaleItem,InventoryCustomer,InventoryProduct, SaleReturn, SaleReturnItem, PurchaseInvoice, PurchaseItem, ProductPriceHistory
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum
from datetime import date
from operator import attrgetter
from django.views.decorators.clickjacking import xframe_options_exempt
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.core.serializers.json import DjangoJSONEncoder
from datetime import date, datetime
from django.contrib.auth.models import User, Group
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from itertools import chain
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import permission_required

@xframe_options_exempt  # Webhook/Iframe printing security fix
def inventory_invoice_duplicate(request, invoice_no):
    # 1. Invoice main details fetch karein
    sale = get_object_or_404(InventorySale, invoice_no=invoice_no)
    
    # 2. Is sale ke saare products items fetch karein (related_name='items' ki wajah se)
    items = sale.items.all() 
    
    context = {
        'sale': sale,
        'items': items
    }
    
    return render(request, 'inventory/inventory_invoice_duplicate.html', context)

@login_required
@permission_required('products.view_sale', raise_exception=True)
def pos_screen(request):
    products = Product.objects.filter(status=True)
    return render(request, 'products/pos_view.html', {'products': products})

@login_required
@permission_required('products.add_sale', raise_exception=True)
def process_sale(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            with transaction.atomic():
                # Safe Sequence Logic
                last_sale = Sale.objects.all().order_by('id').last()
                if not last_sale:
                    new_invoice_no = "1001"
                else:
                    if last_sale.invoice_no.isdigit():
                        new_invoice_no = str(int(last_sale.invoice_no) + 1)
                    else:
                        new_invoice_no = str(last_sale.id + 1001)

                sale = Sale.objects.create(
                    user=request.user,
                    invoice_no=new_invoice_no,
                    customer_mobile=data.get('customer_mobile') or "",
                    subtotal=data.get('subtotal') or 0,
                    discount_amount=data.get('discount') or 0, # Fix for Decimal Error
                    total_amount=data.get('total') or 0,
                    is_hold=data.get('is_hold', False)
                )
                
                for item in data.get('items'):
                    product = Product.objects.get(id=item['id'])
                    qty = int(item['qty'])
                    
                    if product.stock_quantity >= qty:
                        product.stock_quantity -= qty
                        product.save()
                        SaleItem.objects.create(
                            sale=sale, product=product, quantity=qty,
                            unit_price=item['price'], subtotal=float(qty)*float(item['price'])
                        )
                    else:
                        transaction.set_rollback(True)
                        return JsonResponse({'status': 'error', 'message': f'Stock out for {product.name}'})
                
                return JsonResponse({'status': 'success', 'sale_id': sale.id})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

@login_required
def print_barcode_view(request):
    # Abhi ke liye sirf template render karein
    products = Product.objects.filter(status=True)
    return render(request, 'products/print_barcode.html', {'products': products})

@login_required
def pos_sales_view(request):
    products = Product.objects.all()
    products_json = json.dumps(list(products.values('id', 'name', 'barcode', 'price')), cls=DjangoJSONEncoder)
    
    last_sale = Sale.objects.all().order_by('id').last()
    if not last_sale:
        next_invoice = "1001"
    else:
        if last_sale.invoice_no.isdigit():
            next_invoice = str(int(last_sale.invoice_no) + 1)
        else:
            next_invoice = str(last_sale.id + 1001)

    load_sale_id = request.GET.get('load_sale')
    sale_data_json = "[]"
    
    if load_sale_id:
        try:
            sale = Sale.objects.get(id=load_sale_id, user=request.user)
            items_list = []
            for item in sale.items.all():
                p = item.product
                p.stock_quantity += item.quantity
                p.save()
                items_list.append({
                    'id': item.product.id,
                    'name': item.product.name,
                    'price': float(item.unit_price),
                    'qty': item.quantity
                })
            sale_data_json = json.dumps(items_list)
            sale.delete() 
        except Sale.DoesNotExist:
            pass

    return render(request, 'products/pos_sales.html', {
        'products_json': products_json,
        'sale_data_json': sale_data_json,
        'invoice_no': next_invoice 
    })

@login_required
def reprint_invoice(request, sale_id):
    try:
        sale = Sale.objects.get(id=sale_id, user=request.user)
        return render(request, 'products/invoice_print.html', {'sale': sale})
    except Sale.DoesNotExist:
        return HttpResponse("Invoice nahi mili!", status=404)

# --- PURCHASE MANAGEMENT ---
@login_required
@permission_required('products.add_purchaseinvoice', raise_exception=True)
def purchase_view(request):
    if 'temp_items' not in request.session:
        request.session['temp_items'] = []

    if request.method == "POST":
        if 'add_to_list' in request.POST:
            prod_id = request.POST.get('product')
            qty_raw = request.POST.get('quantity')
            price_raw = request.POST.get('purchase_price')
            try:
                qty = int(qty_raw) if qty_raw and qty_raw.strip() else 0
                price = float(price_raw) if price_raw and price_raw.strip() else 0.0
                if prod_id and qty > 0:
                    product = Product.objects.get(id=prod_id)
                    item = {
                        'product_id': prod_id,
                        'product_name': product.name,
                        'qty': qty,
                        'p_price': price,
                        'total': qty * price
                    }
                    temp_list = request.session['temp_items']
                    temp_list.append(item)
                    request.session['temp_items'] = temp_list
                    request.session.modified = True
            except (ValueError, Product.DoesNotExist):
                pass

        elif 'finish_purchase' in request.POST:
            supplier_id = request.POST.get('supplier')
            inv_no = request.POST.get('invoice_no')
            temp_list = request.session.get('temp_items', [])
            if supplier_id and inv_no and temp_list:
                with transaction.atomic():
                    invoice = PurchaseInvoice.objects.create(
                        supplier_id=supplier_id,
                        invoice_number=inv_no,
                        purchase_date=timezone.now()
                    )
                    for item in temp_list:
                        PurchaseItem.objects.create(
                            invoice=invoice, product_id=item['product_id'],
                            quantity=item['qty'], purchase_price=item['p_price'],
                            total_price=item['total']
                        )
                    request.session['temp_items'] = []
                    request.session.modified = True
                return redirect('purchase_view')

        elif 'clear_draft' in request.POST:
            request.session['temp_items'] = []
            request.session.modified = True

    temp_list = request.session.get('temp_items', [])
    context = {
        'products': Product.objects.filter(status=True),
        'suppliers': Supplier.objects.all(),
        'temp_items': temp_list,
        'grand_total': sum(item['total'] for item in temp_list),
        'purchases': PurchaseInvoice.objects.all().order_by('-id')[:5],
    }
    return render(request, 'products/purchase.html', context)

@login_required
@permission_required('products.view_sale', raise_exception=True)
def sales_list_view(request):
    today = timezone.now().date()
    # Pehle variables ko default values dein
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if request.user.is_superuser:
        sales = Sale.objects.all()
    else:
        sales = Sale.objects.filter(user=request.user)

    # Ab filter check karein
    if start_date and end_date:
        sales = sales.filter(date__date__range=[start_date, end_date])
    else:
        sales = sales.filter(date__date=today)
        # Template ko dikhane ke liye wapis default set karein
        start_date = today.strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')

    return render(request, 'products/sales_list.html', {
        'sales': sales,
        'start_date': start_date,
        'end_date': end_date
    })

@login_required
def hold_sales_list(request):
    draft_sales = Sale.objects.filter(is_hold=True).order_by('-date')
    return render(request, 'products/hold_sales_list.html', {'draft_sales': draft_sales})

@login_required
def get_invoice_details(request):
    invoice_no = request.GET.get('invoice_no')
    try:
        sale = Sale.objects.get(invoice_no=invoice_no)
        items = SaleItem.objects.filter(sale=sale).values('product__id', 'product__name', 'product__barcode', 'quantity', 'price')
        return JsonResponse({
            'success': True,
            'sale_id': sale.id,
            'total': sale.total_amount,
            'items': list(items)
        })
    except Sale.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Invoice not found!'})

@login_required
@permission_required('products.change_product', raise_exception=True)
def update_prices_view(request):
    selected_product_id = request.GET.get('filter_product')
    if request.method == "POST":
        prod_id = request.POST.get('product')
        price_raw = request.POST.get('new_price')
        if price_raw and price_raw.strip() and prod_id:
            try:
                new_price = float(price_raw)
                product = Product.objects.get(id=prod_id)
                old_price = float(product.price)
                if old_price != new_price:
                    ProductPriceHistory.objects.create(product=product, old_price=old_price, new_price=new_price)
                    product.price = new_price
                    product.save()
            except (Product.DoesNotExist, ValueError):
                pass
        return redirect('update_prices_view')
    
    history = ProductPriceHistory.objects.all().order_by('-change_date')
    if selected_product_id:
        history = history.filter(product_id=selected_product_id)
    
    context = {
        'products': Product.objects.filter(status=True),
        'history': history[:10],
        'selected_product_id': selected_product_id,
    }
    return render(request, 'products/update_prices.html', context)

def inventory_pos_view(request):
    # Purane customers ki jagah InventoryCustomer fetch karein
    inventory_customers = InventoryCustomer.objects.all()
    inventory_products = InventoryProduct.objects.all()
    
    context = {
        'customers': inventory_customers, # Variable name 'customers' hi rakhein taake HTML zyada change na karni paray
        'products': inventory_products,
    }
    return render(request, 'your_template.html', context)

@login_required
@permission_required('products.add_salereturn', raise_exception=True)
def return_page_view(request):
    return render(request, 'products/return_page.html')

@login_required
def get_invoice_details(request):
    invoice_no = request.GET.get('invoice_no')
    try:
        sale = Sale.objects.get(invoice_no=invoice_no)
        from .models import SaleItem, SaleReturnItem # Return items ka model lazmi ho
        
        items_data = []
        sale_items = SaleItem.objects.filter(sale=sale)

        for item in sale_items:
            # Check karein ke is product ki kitni qty pehle return ho chuki hai
            already_returned = SaleReturnItem.objects.filter(
                sale_return__original_sale=sale, 
                product=item.product
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            remaining_qty = item.quantity - already_returned

            # Sirf wo items bhejein jo abhi return ho sakte hain (qty > 0)
            if remaining_qty > 0:
                items_data.append({
                    'product__id': item.product.id,
                    'product__name': item.product.name,
                    'product__barcode': item.product.barcode,
                    'quantity': remaining_qty, # Ab yahan sirf baqi bachi qty jayegi
                    'unit_price': float(item.unit_price)
                })

        return JsonResponse({
            'success': True,
            'sale_id': sale.id,
            'subtotal': float(sale.subtotal),
            'discount_amount': float(sale.discount_amount),
            'total': float(sale.total_amount),
            'items': items_data
        })
    except Sale.DoesNotExist:
        # 404 status code dena zaroori hai
        return JsonResponse({'success': False, 'message': 'Invild Invoice No'}, status=404)

@login_required
@transaction.atomic
@permission_required('products.add_salereturn', raise_exception=True)
def process_return(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            sale_id = data.get('sale_id')
            returned_items = data.get('items')
            total_return_amount = data.get('total_return_amount')
            reason = data.get('reason')

            sale = Sale.objects.get(id=sale_id)
            sale_return = SaleReturn.objects.create(
                original_sale=sale,
                total_returned_amount=total_return_amount,
                reason=reason
            )

            for item in returned_items:
                product_id = item['product_id']
                qty_to_return = int(item['qty'])
                unit_price = item['price']

                if qty_to_return > 0:
                    product = Product.objects.get(id=product_id)

                    # Return Item record karein
                    SaleReturnItem.objects.create(
                        sale_return=sale_return,
                        product=product,
                        quantity=qty_to_return,
                        price=unit_price
                    )

                    # FIX: 'stock' ki jagah 'stock_quantity' use karein
                    product.stock_quantity += item.quantity 
                    product.save()

            return JsonResponse({'success': True, 'message': 'Return successful and stock updated!'})

        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    return JsonResponse({'success': False, 'message': 'Invalid request'})

@login_required
def manage_users(request):
    # Sirf admin hi users manage kar sakta hai
    if not request.user.is_superuser:
        return HttpResponse("Aapko is page ki ijazat nahi hai.", status=403)

    users = User.objects.all().prefetch_related('groups')
    groups = Group.objects.all()

    if request.method == "POST":
        # Naya User Banane ke liye
        if 'create_user' in request.POST:
            username = request.POST.get('username')
            pass_1 = request.POST.get('password')
            if User.objects.filter(username=username).exists():
                messages.error(request, "Username pehle se maujood hai!")
            else:
                user = User.objects.create_user(username=username, password=pass_1)
                messages.success(request, f"User {username} ban gaya hai!")
        
        # Rights/Group Update karne ke liye
        elif 'update_rights' in request.POST:
            target_user_id = request.POST.get('user_id')
            group_id = request.POST.get('group_id')
            target_user = User.objects.get(id=target_user_id)
            group = Group.objects.get(id=group_id)
            
            target_user.groups.clear() # Purane rights khatam
            target_user.groups.add(group) # Naya group (Cashier/Manager) assign
            messages.success(request, f"{target_user.username} ke rights update ho gaye!")

        return redirect('manage_users')

    return render(request, 'products/manage_users.html', {
        'users': users,
        'groups': groups
    })


@login_required
def add_inventory_stock(request):
    if request.method == "POST":
        # Form se data nikalna
        name = request.POST.get('name')
        category_id = request.POST.get('category')
        barcode = request.POST.get('barcode')
        stock = request.POST.get('stock')
        price = request.POST.get('price')
        tp_percent = request.POST.get('tp_percent')
        expiry_date = request.POST.get('expiry_date') 

        # --- EXPIRY DATE FIX ---
        valid_expiry = None
        if expiry_date and expiry_date.strip():
            valid_expiry = expiry_date

        try:
            # Category find karein
            category = Category.objects.get(id=category_id)
            
            # Product create karein
            InventoryProduct.objects.create(
                name=name,
                category=category,
                barcode=barcode,
                stock=int(stock or 0),
                retail_price=Decimal(str(price or 0)),
                tp_percent=Decimal(str(tp_percent or 0)),
                expiry_date=valid_expiry 
            )
            
            messages.success(request, f"Product '{name}' kamyabi se add ho gaya!")
            # POST successful hone ke baad redirect lazmi hai
            return redirect('add_inventory_stock') 
            
        except Category.DoesNotExist:
            messages.error(request, "Error: Muntakhib karda category nahi mili.")
            # Error ke baad bhi redirect karein taake function return None na kare
            return redirect('add_inventory_stock')
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            # Her exception ke baad redirect lazmi hai
            return redirect('add_inventory_stock')

    # --- GET Request Logic (Function ke end mein lazmi return render hona chahiye) ---
    products = InventoryProduct.objects.all().order_by('-id')
    categories = Category.objects.all()
    
    context = {
        'products': products,
        'categories': categories,
        'today': date.today() 
    }
    
    return render(request, 'inventory/add_stock.html', context)
@login_required
def delete_product(request, product_id):
    product = get_object_or_404(InventoryProduct, id=product_id)
    
    # ID se check karein taake Product instance ka error na aaye
    if InventorySaleItem.objects.filter(product_id=product.id).exists():
        messages.error(request, f"'{product.name}' delete nahi ho sakta kyunke iski sale history maujood hai.")
    else:
        product.delete()
        messages.success(request, "Product delete kar di gayi.")
    
    return redirect('add_inventory_stock')

@login_required
@transaction.atomic
def process_inventory_sale(request):
    if request.method != "POST":
        return JsonResponse({'status': 'error', 'message': 'Invalid Request Method'})

    try:
        data = json.loads(request.body)
        customer_id = data.get('customer_id')
        items = data.get('items')
        
        if not customer_id or not items:
            return JsonResponse({'status': 'error', 'message': 'Customer or items missing!'})

        # DB operations inside atomic block
        with transaction.atomic():
            # 1. Fetch Customer
            customer = get_object_or_404(InventoryCustomer, id=customer_id)
            
            # 2. Main Sale Record Create
            timestamp = datetime.now().strftime('%y%m%d%H%M%S')
            inv_sale = InventorySale.objects.create(
                customer=customer,
                total_amount=decimal.Decimal('0.00'),
                invoice_no=f"INV-{timestamp}"
            )

            total_bill = decimal.Decimal('0.00')
            processed_items_list = []  # Array response ke liye product list collect karega

            # 3. Items process karein
            for item in items:
                # select_for_update() to prevent race conditions
                product = InventoryProduct.objects.select_for_update().get(id=item['id']) 
                qty = int(item['qty'])
                
                # Stock validation
                if product.stock < qty:
                    return JsonResponse({
                        'status': 'error', 
                        'message': f'Product "{product.name}" ka stock kam hai! Available: {product.stock}'
                    })

                # Fallback rate handling
                rate_val = item.get('rate')
                unit_price = decimal.Decimal(str(rate_val)) if rate_val else decimal.Decimal(str(product.trade_price))
                
                item_total = unit_price * qty
                total_bill += item_total

                # InventorySaleItem save karein
                InventorySaleItem.objects.create(
                    sale=inv_sale,
                    product=product,
                    quantity=qty,
                    price_at_sale=unit_price 
                )

                # Append product details to array for final response
                processed_items_list.append({
                    'product_id': product.id,
                    'product_name': product.name,
                    'quantity': qty,
                    'rate': float(unit_price),
                    'total_rs': float(item_total)
                })

                # Stock update
                product.stock -= qty
                product.save()

            # 4. Final Sale Bill Update
            inv_sale.total_amount = total_bill
            inv_sale.save()

            # 5. Customer Ledger Balance Update
            old_purchased = decimal.Decimal(str(customer.total_purchased or 0))
            old_balance = decimal.Decimal(str(customer.total_balance or 0))

            customer.total_purchased = old_purchased + total_bill
            customer.total_balance = old_balance + total_bill
            customer.save()

            # UPDATED RESPONSE: Customer profile, products array aur Rs keys inject kar di hain
            return JsonResponse({
                'status': 'success', 
                'message': 'Sale Processed Successfully!',
                'invoice_no': inv_sale.invoice_no,
                'customer_name': customer.name,            # Yeh key model column ke hisab se rename kar sakte hain (e.g., customer.first_name)
                'customer_number': customer.mobile,         # Model field 'phone' ya 'contact' ke mutabiq check karlein
                'products': processed_items_list,         # Invoice product details list
                'total_bill_rs': float(total_bill),        # Total Invoice Rs
                'new_balance': float(customer.total_balance)
            })
        
    except InventoryProduct.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Koi aik product database mein nahi mili!'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'System Error: {str(e)}'})

@login_required
def customer_ledger_list(request):
    if request.method == "POST" and 'opening_balance' in request.POST:
        name = request.POST.get('name')
        mobile = request.POST.get('mobile')
        op_bal = request.POST.get('opening_balance', 0)
        
        # Sahi fields ke saath create karein taake balance start se hi show ho
        InventoryCustomer.objects.create(
            name=name, 
            mobile=mobile, 
            opening_balance=op_bal,
            total_purchased=op_bal, # Opening balance ko shuruati purchase maana jata hai
            total_balance=op_bal    # Shuru mein balance bhi wahi hoga
        )
        return redirect('customer_ledger_list')
        
    # Data fetch karein
    customers = InventoryCustomer.objects.all().order_by('name')
    
    # Dashboard Cards ki calculation
    # 1. Total Udhaar (Sirf wo jin ka balance positive hai)
    total_receivable = sum(c.total_balance for c in customers if c.total_balance > 0)
    
    # 2. Active Accounts
    active_count = customers.filter(is_active=True).count()
    
    context = {
        'customers': customers,
        'total_receivable': total_receivable,
        'active_count': active_count,
    }
    
    return render(request, 'inventory/ledger.html', context)
@login_required
def inventory_pos_screen(request):
    products = InventoryProduct.objects.filter(stock__gt=0)
    customers = InventoryCustomer.objects.all()
    return render(request, 'inventory/pos_screen.html', {
        'products': products,
        'customers': customers
    })



@login_required
@transaction.atomic
def customer_payment_receive(request):
    if request.method == "POST":
        customer_id = request.POST.get('customer_id')
        amount_str = request.POST.get('amount', '0')
        remarks = request.POST.get('remarks', 'Cash Received')
        
        customer = get_object_or_404(InventoryCustomer, id=customer_id)
        amount_received = decimal.Decimal(str(amount_str))

        if amount_received > 0:
            # 1. Customer ka total update karein
            customer.total_paid += amount_received
            customer.save()
            
            # 2. History table mein entry dalain
            CashPayment.objects.create(
                customer=customer,
                amount=amount_received,
                remarks=remarks
            )
            
            return JsonResponse({'status': 'success'})
            
    customers = InventoryCustomer.objects.all().order_by('name')
    return render(request, 'inventory/payment_receive.html', {'customers': customers})
@login_required
def get_customer_stats(request, customer_id):
    customer = get_object_or_404(InventoryCustomer, id=customer_id)
    return JsonResponse({
        'total_purchased': float(customer.total_purchased), # <-- Sahi spelling
        'total_paid': float(customer.total_paid),
        'outstanding': float(customer.total_balance)
    })
@login_required
def inventory_stock_entry(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            items = data.get('items', [])
            
            with transaction.atomic():
                for item in items:
                    product = InventoryProduct.objects.get(id=item['id'])
                    
                    # 1. Stock update (Plus operation)
                    product.stock += int(item.get('qty_added', 0))
                    
                    # 2. Price aur TP update (Decimal safety ke sath)
                    product.retail_price = Decimal(str(item.get('retail_price', product.retail_price)))
                    product.tp_percent = Decimal(str(item.get('tp_percent', product.tp_percent)))
                    
                    # 3. EXPIRY UPDATE FIX
                    new_expiry = item.get('expiry_date')
                    if new_expiry and new_expiry.strip():
                        product.expiry_date = new_expiry
                    # Note: Agar user ne voucher mein date nahi dali, 
                    # to purani date hi barkarar rahegi (None nahi hogi).

                    product.save()
                    
            return JsonResponse({'status': 'success', 'message': 'Stock and Expiry successfully updated!'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

    # GET request logic
    products = InventoryProduct.objects.all().order_by('name')
    return render(request, 'inventory/stock_entry.html', {'products': products})
@login_required
def delete_product(request, product_id):
    product = get_object_or_404(InventoryProduct, id=product_id)
    
    # Ab hum sirf Inventory ki apni Sale Items check kar rahe hain
    if InventorySaleItem.objects.filter(product=product).exists():
        messages.error(request, f"Ye product '{product.name}' Inventory Sales mein use ho chuki hai, isliye delete nahi ho sakti. Sirf Inactive kar sakte hain.")
    else:
        product.delete()
        messages.success(request, "Product kamyabi se delete ho gayi.")
        
    return redirect('add_inventory_stock')

def toggle_product_status(request, product_id):
    # 'Product' ki jagah wo model use karein jo table 'products_inventoryproduct' se juda hai
    product = get_object_or_404(InventoryProduct, id=product_id) 
    
    product.is_active = not product.is_active
    product.save()
    
    return redirect('add_inventory_stock')



def receipt_print_view(request, payment_id):
    # Database se payment record uthaein
    payment = get_object_or_404(CashPayment, id=payment_id)
    return render(request, 'inventory/payment_receipt.html', {'payment': payment})

def customer_details(request, customer_id):
    # 1. Pehle customer ka object lein
    customer = get_object_or_404(InventoryCustomer, id=customer_id)
    
    # 2. Sales fetch karein 
    sales = InventorySale.objects.filter(customer=customer_id)
    
    # 3. Payments fetch karein
    payments = CashPayment.objects.filter(customer=customer_id)
    
    # 4. Dono ko mila kar date ke mutabiq sort karein
    history_raw = sorted(chain(sales, payments), key=attrgetter('date'))
    
    # 5. Running Balance calculate karein
    history = []
    current_bal = 0 
    
    for item in history_raw:
        # Check karein ke ye Sale hai ya Payment
        is_sale = hasattr(item, 'invoice_no')
        
        # Sahi ID aur Amount uthaein
        # Database se id field ko lazmi pakrein taake template mein buttons ko mil sakay
        t_id = item.id 
        amount = float(item.total_amount) if is_sale else float(item.amount)
        
        if is_sale:
            current_bal += amount
            debit, credit = amount, 0
            desc = f"Invoice #{item.invoice_no}"
            tag = "Inventory Sale"
        else:
            current_bal -= amount
            debit, credit = 0, amount
            desc = item.remarks if item.remarks else "Cash Received - Account Update"
            tag = "Cash Payment"
            
        # History list mein ID shamil karein
        history.append({
            'id': t_id,          # <--- Ye line missing thi, ab ID template mein jayegi
            'date': item.date,
            'description': desc,
            'type': tag,
            'debit': debit,
            'credit': credit,
            'balance': current_bal
        })

    # Newest transactions top par lane ke liye reverse karein
    history.reverse()

    return render(request, 'inventory/customer_details.html', {
        'customer': customer,
        'history': history
    })

def print_inventory_invoice(request, invoice_no):
    # Database se invoice nikali
    sale = get_object_or_404(InventorySale, invoice_no=invoice_no)
    
    # FIX: Folder path 'products/' lagana zaroori hai jaisa aapke VS Code me dikh raha hai
    return render(request, 'inventory/inventory_invoice_print.html', {'sale': sale})


@login_required
@permission_required('products.add_product', raise_exception=True)
def settings_view(request):
    if request.method == "POST":
        if 'add_category' in request.POST:
            Category.objects.create(name=request.POST.get('cat_name'))
        elif 'add_unit' in request.POST:
            Unit.objects.create(name=request.POST.get('unit_name'))
        elif 'add_product' in request.POST:
            Product.objects.create(
                name=request.POST.get('prod_name'), category_id=request.POST.get('prod_cat'),
                unit_id=request.POST.get('prod_unit'), price=request.POST.get('prod_price'),
                barcode=request.POST.get('prod_barcode')
            )
        elif 'add_supplier' in request.POST:
            Supplier.objects.create(
                name=request.POST.get('sup_name'), 
                contact_number=request.POST.get('sup_contact'), 
                address=request.POST.get('sup_address')
            )
        return redirect('settings_view')

    context = {
        'categories': Category.objects.all(),
        'units': Unit.objects.all(),
        'products': Product.objects.all(),
        'suppliers': Supplier.objects.all(),
    }
    return render(request, 'products/settings.html', context)